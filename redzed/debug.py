"""
Debug levels.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

import logging
import os

from . import circuit

__all__ = ['get_debug_level', 'set_debug_level']

_logger = logging.getLogger(__package__)


def get_level_from_env() -> int|None:
    if (env_level := os.environ.get('REDZED_DEBUG', '')) == '':
        return None
    try:
        level = int(env_level)
    except Exception:
        pass
    else:
        if 0 <= level <= 3:
            return level
    _logger.warning(
        "Envvar 'REDZED_DEBUG' should be: 0 (disabled), 1 (normal), "
        + "2 (verbose) or 3 (verbose with circuit timestamps)")
    _logger.error("Ignoring REDZED_DEBUG='%s'. Please use a correct value.", env_level)
    return None


class _DebugLevel:
    """
    Global debug level.

    The initial level is set according to the environment variable REDZED_DEBUG.
    """

    def __init__(self) -> None:
        if (level := get_level_from_env()) is None:
            level = 0
        self._level = level
        _logger.debug("[Logging] Debug level: %d", level)

    @property
    def level(self) -> int:
        return self._level

    @level.setter
    def level(self, level: int) -> None:
        """Set debug level."""
        if level == self._level:
            return
        if not isinstance(level, int):
            raise TypeError(f"Expected an integer, got {level!r}")
        if not 0 <= level <= 3:
            raise ValueError(f"Debug level must be an integer 0 to 3, but got {level}")
        _logger.debug("[Logging] Debug level: %d -> %d", self._level, level)
        self._level = level


_debug_level = _DebugLevel()


def get_debug_level():
    """Get the debug level."""
    return _debug_level.level


def set_debug_level(level):
    """
    Set the debug level.

    Also make sure debug messages will be logged or printed.
    For this purpose, if there is no handler, add an own stream handler.
    """
    _debug_level.level = level
    if circuit.get_circuit().get_state() in [
            circuit.CircuitState.UNDER_CONSTRUCTION, circuit.CircuitState.CLOSED]:
        return
    if level > 0:
        if not _logger.hasHandlers():
            _logger.addHandler(logging.StreamHandler())
            _logger.propagate = False
        _logger.setLevel(logging.DEBUG)
    else:
        _logger.setLevel(logging.NOTSET if _logger.propagate else logging.INFO)


class _CircuitTimeFilter(logging.Filter):
    """Filter adding timestamsps in debug level 3."""
    def filter(self, record: logging.LogRecord) -> bool:
        if _debug_level.level >= 3 and isinstance(record.msg, str):
            record.msg = f"{circuit.get_circuit().runtime():.03f} {record.msg}"
        return True


_logger.addFilter(_CircuitTimeFilter())
