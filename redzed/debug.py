"""
Debug level.
"""
from __future__ import annotations

__all__ = ['get_debug_level', 'set_debug_level']

import logging
import os

from . import circuit

_logger = logging.getLogger(__package__)
_debug_handler: logging.StreamHandler|None = None


class _CircuitTimeFormatter(logging.Formatter):
    """Formatter for debug level 3."""
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if get_debug_level() >= 3:
            msg = f"{circuit.get_circuit().runtime():.03f} {msg}"
        return msg


class _DebugLevel:
    """
    Global debug level.

    The initial level is set according to the environment variable REDZED_DEBUG.
    """

    def __init__(self) -> None:
        self._level = -1    # make sure the set_level's core will run
        self.set_level(self._get_level_from_env())

    def _get_level_from_env(self) -> int:
        try:
            level = os.environ['REDZED_DEBUG']
        except KeyError:
            return 0
        level = level.strip()
        if not level:
            return 0
        if level in {'0', '1', '2', '3'}:
            return int(level)
        _logger.warning(
            "Envvar 'REDZED_DEBUG' should be: 0 (disabled), 1 (normal), "
            + "2 (verbose) or 3 (verbose with circuit timestamps)")
        _logger.warning("Ignoring REDZED_DEBUG='%s'. Please use a correct value.", level)
        return 0

    def get_level(self) -> int:
        return self._level

    def set_level(self, level: int) -> None:
        """Set debug level."""
        global _debug_handler       # pylint: disable=global-statement

        if not isinstance(level, int):
            raise TypeError(f"Expected an integer, got {level!r}")
        if level == self._level:
            return
        if not 0 <= level <= 3:
            raise ValueError(f"Debug level must be an integer 0 to 3, but got {level}")
        # self._level is -1 on initial call
        if self._level >= 0:
            _logger.debug("Debug level: %d -> %d", self._level, level)
        elif level > 0:
            _logger.debug("Debug level: %d", level)
        self._level = level
        if level == 0:
            if _debug_handler is not None:
                _logger.removeHandler(_debug_handler)
                _debug_handler = None
            _logger.setLevel(logging.WARNING)
        elif not _logger.hasHandlers() and _debug_handler is None:
            _logger.addHandler(_debug_handler := logging.StreamHandler())
            _debug_handler.setFormatter(_CircuitTimeFormatter("%(levelname)s - %(message)s"))
            _logger.setLevel(logging.DEBUG)


_global_debug_level = _DebugLevel()

get_debug_level = _global_debug_level.get_level
set_debug_level = _global_debug_level.set_level
