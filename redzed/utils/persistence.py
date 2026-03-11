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
            datafile: str,
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
        super().__init__()
        self._filepath = pathlib.PurePath(datafile)
        self._sync_time = time_period(sync_time, zero_ok=True)
        if format is None:
            suffix = self._filepath.suffix
            if suffix == '.json':
                format = 'json'
            elif suffix in ['.pkl', '.pickle']:
                format = 'pickle'
        if format not in ['json', 'pickle']:
            raise ValueError("Argument format must be either 'json' or 'pickle'")
        self._format = format
        self._error_cb = error_callback
        self._tmp_file_settings = {
            'dir': self._filepath.parent,
            'prefix': self._filepath.stem,
            'suffix':' .tmp',
            'text': format == 'json',
            }
        self._modified = asyncio.Event()
        self._flush_task: asyncio.Task | None = None
        try:
            # Python 3.15+: use "lazy import"
            # pylint: disable=import-outside-toplevel, global-statement, redefined-outer-name
            if format == 'json':
                global json
                import json
                with open(self._filepath, 'r', encoding='utf-8') as fileobj:
                    data = json.load(fileobj)
            elif format == 'pickle':
                global pickle
                import pickle
                with open(self._filepath, 'rb') as fileobj:
                    data = pickle.load(fileobj)
            else:
                assert False, "not reached"
            # bypass __setitem__, this is not deemed a modification
            self.data.update(data)
        except FileNotFoundError as err:
            _logger.warning("File not found: %s", self._filepath)
            self._callback(err)
        except Exception as err:
            _logger.error("Error loading persistent dict from '%s': %r", self._filepath, err)
            self._callback(err)

    def __setitem__(self, key: str, value: object) -> None:
        super().__setitem__(key, value)
        self.mark_modified()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self.mark_modified()

    def is_modified(self) -> bool:
        return self._modified.is_set()

    def mark_modified(self) -> None:
        if self._sync_time == 0.0:
            self._save_to_file()
            return
        if self._modified.is_set():
            return
        self._modified.set()
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(
                self._flush_service(), name="persistent data sync task")

    def _callback(self, exc: Exception):
        if self._error_cb is None:
            return
        exc.add_note(f"Error occurred in {type(self).__name__}")
        self._error_cb(exc)

    def _save_to_file(self) -> bool:
        """Save data to file. Return True if data was saved successfully."""
        if not self._modified.is_set():
            return True

        try:
            step = 1
            fd, tmp_name = tempfile.mkstemp(
                **self._tmp_file_settings)  # type: ignore[call-overload]
            step = 2
            tmp_file: io.IOBase
            # pylint: disable=undefined-variable
            if self._format == 'json':
                with open(fd, "w", encoding='utf-8') as tmp_file:
                    json.dump(self.data, tmp_file, **SETTINGS_PRETTY)
                    tmp_file.write("\n")
            elif self._format == 'pickle':
                with open(fd, "wb") as tmp_file:
                    pickle.dump(self.data, tmp_file)
            else:
                assert False, "not reached"
            step = 3
            os.replace(tmp_name, self._filepath)
        except Exception as err:
            exc = err
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        else:
            self._modified.clear()
            return True

        if step == 1:
            _logger.error(
                "Could not create a temporary file in '%s': %r",
                self._tmp_file_settings['dir'], exc)
        elif step == 2:
            if isinstance(exc, OSError):
                _logger.error("Error saving data to '%s': %s", tmp_file, exc)
            else:
                _logger.error("Data conversion (%s) error: %r", self._format, exc)
        elif step == 3:
            _logger.error("Error renaming temporary file to '%s': %r", self._filepath, exc)

        self._callback(exc)
        del exc         # break reference cycle
        return False

    async def _flush_service(self):
        """Save data to file after each modification."""
        dmin, dmax = type(self).SAVE_RETRY_DELAYS
        delay = dmin
        try:
            while True:
                await self._modified.wait()
                if self._sync_time > 0.0:
                    await asyncio.sleep(self._sync_time)
                if self._save_to_file():
                    delay = dmin
                else:
                    await asyncio.sleep(delay)
                    delay = min(2*delay, dmax)
                    continue
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
