"""
Persistent data with file back-end.
"""

from __future__ import annotations

__all__ = ['PersistentDict']

import asyncio
import collections
from collections.abc import Callable
import io
import logging
import os
import os.path
import pathlib
import tempfile
import time
import typing as t
from types import ModuleType

from .time_utils import time_period

# Python 3.15+: use "lazy import"
json: ModuleType
pickle: ModuleType

_logger = logging.getLogger(__package__)


# Settings for human readable output.
# Same input data produces the same JSON string, because the keys are sorted.
SETTINGS_PRETTY = {
    'indent': 2, 'separators': (', ', ': '),
    'sort_keys': True, 'ensure_ascii': False
    }


class PersistentDict(collections.UserDict):
    # need to subclass the UserDict, not the dict.
    # http://stackoverflow.com/questions/34380356/how-to-detect-dict-modification
    """
    Persistent dictionary with data stored in a file.

    The contents of the dict is written to the file after each dict
    modification, i.e. when an element is deleted, created or a new
    value is stored. CAUTION: Mutating a value in-place is NOT
    a dict modification. If not sure, assign the new value.
    """

    # exponential backoff min and max delays when retrying a failed file save:
    SAVE_RETRY_DELAYS = (1.7, 490.0)

    def __init__(
            self,
            datafile: str | os.PathLike[str],
            # pylint: disable-next=redefined-builtin
            format: t.Literal['json', 'pickle', None] = None,
            *,
            error_callback: Callable[[Exception], object]|None = None,
            sync_time: float|str = 10.0,
            ) -> None:
        """
        Load the dict from the named file.

        If an error occurs during the loading, start with an empty dict.
        """
        # pylint: disable=import-outside-toplevel, redefined-outer-name
        global json, pickle
        super().__init__()
        self._filepath = pathlib.Path(datafile)
        if not self._filepath.is_absolute():
            raise ValueError(f"PersistentDict: '{datafile}' is not an absolute path")
        self._sync_time = time_period(sync_time, zero_ok=True)
        if format is None:
            suffix = self._filepath.suffix
            if suffix == '.json':
                format = 'json'
            elif suffix in ['.pkl', '.pickle']:
                format = 'pickle'
        if format == 'json':
            # Python 3.15+: use "lazy import json, pickle" instead
            import json
        elif format == 'pickle':
            import pickle
        else:
            raise ValueError("Argument format must be either 'json' or 'pickle'")
        self._format = format
        self._error_cb = error_callback
        self._tmp_file_settings = {
            'dir': self._filepath.parent,
            'prefix': self._filepath.stem,
            'suffix':' .tmp',
            'text': format == 'json',
            }
        # caching mode: 'sync_time' > 0:
        #   using '_modified' (asyncio.Event) and '_flush_task' (asyncio.Task)
        # non-caching mode: 'sync_time' == 0:
        #   not using '_modified', nor '_flush_task'
        self._modified = asyncio.Event() if self._sync_time != 0.0 else None
        self._flush_task: asyncio.Task | None = None
        try:
            # accept an empty datafile without loading the contents
            if self._filepath.stat().st_size > 0:
                if format == 'json':
                    with open(self._filepath, 'r', encoding='utf-8') as fileobj:
                        # bypass __setitem__, this is not deemed a modification
                        self.data.update(json.load(fileobj))
                elif format == 'pickle':
                    with open(self._filepath, 'rb') as fileobj:
                        self.data.update(pickle.load(fileobj))
        except Exception as err:
            if isinstance(err, FileNotFoundError):
                _logger.warning("File '%s' is missing", self._filepath)
            else:
                _logger.error("Error loading data from '%s': %r", self._filepath, err)
            self._run_error_callback(err)
            if not isinstance(err, OSError):
                dest_name = str(self._filepath) + time.strftime(".%Y%m%d_%H%M%S~")
                try:
                    # on Posix, this could overwrite existing 'dest_name', but never mind
                    self._filepath.rename(dest_name)
                except OSError:
                    pass
                else:
                    _logger.info(
                        "Offending PersistentDict file renamed to '%s';"
                        + " you may inspect the contents or delete it.", dest_name)

    def __setitem__(self, key: str, value: object) -> None:
        super().__setitem__(key, value)
        self.mark_modified()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self.mark_modified()

    def mark_modified(self) -> None:
        """
        If caching: mark as modified (dirty).
        If not caching: save immediately.
        """
        if self._modified is None:
            self._save_to_file(force=True)
            return
        if self._modified.is_set():
            return
        self._modified.set()
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(
                self._flush_service(), name="PersistentDict sync task")

    def _run_error_callback(self, exc: Exception):
        if self._error_cb is None:
            return
        exc.add_note(f"Error occurred in {type(self).__name__}")
        self._error_cb(exc)

    def _save_to_file(self, force: bool = False) -> None:
        """Save data to file. Clear the _modified event if successful."""
        cache_modified = self._modified is not None and self._modified.is_set()
        if not (force or cache_modified):
            return
        step = 1
        try:
            fd, tmp_name = tempfile.mkstemp(
                **self._tmp_file_settings)  # type: ignore[call-overload]
            step = 2
            tmp_file: io.IOBase
            # pylint: disable=undefined-variable
            if self._format == 'json':
                with open(fd, "w", encoding='utf-8') as tmp_file:
                    json.dump(self.data, tmp_file, **SETTINGS_PRETTY)
                    tmp_file.write("\n")
            else:
                assert self._format == 'pickle'
                with open(fd, "wb") as tmp_file:
                    pickle.dump(self.data, tmp_file)
            step = 3
            os.replace(tmp_name, self._filepath)
        except Exception as err:
            exc = err
            if step >= 2:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
        else:
            if self._modified is not None:
                self._modified.clear()
            return

        # error handling
        if step == 1:
            _logger.error(
                "Could not create a temporary file in '%s': %r",
                self._tmp_file_settings['dir'], exc)
        elif step == 2:
            if isinstance(exc, OSError):
                _logger.error("Error saving data to '%s': %s", tmp_file, exc)
            else:
                _logger.error(
                    "PersistentDict data conversion (%s) error: %r", self._format, exc)
        elif step == 3:
            _logger.error("Error renaming temporary file to '%s': %r", self._filepath, exc)
        self._run_error_callback(exc)
        del exc         # break reference cycle

    async def _flush_service(self):
        """Save data to file after each modification."""
        modified = self._modified
        assert modified is not None
        dmin, dmax = type(self).SAVE_RETRY_DELAYS
        try:
            while True:
                await modified.wait()
                await asyncio.sleep(self._sync_time)
                delay = dmin
                while True:
                    self._save_to_file()
                    if not modified.is_set():
                        break
                    await asyncio.sleep(delay)
                    delay = min(2*delay, dmax)
        except BaseException:
            self._save_to_file()
            raise

    def flush(self) -> None:
        """
        Save the data, cancel the flush task.

        The flush task will be started automatically when
        the data is modified after the flush().
        """
        self._save_to_file()
        if self._flush_task is not None:
            self._flush_task.cancel()
            self._flush_task = None
