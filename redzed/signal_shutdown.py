"""
Stop the runner with a signal.
- - - - - -
Part of the redzed package.
# Docs: https://redzed.readthedocs.io/en/latest/
# Project home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['TerminatingSignal']

import asyncio
from collections.abc import Callable
import logging
import signal
from types import FrameType
import typing as t

from . import circuit

_logger = logging.getLogger(__package__)


class TerminatingSignal:
    """
    A context manager gracefully stopping the runner after signal.
    """

    def __init__(self, signo: int|None) -> None:
        self._signo = signo
        if signo is None:
            return
        self._saved_handler: Callable[[int, FrameType|None], None]|int|None
        self._signame = signal.strsignal(signo) or f"#{signo}"

    def __enter__(self) -> None:
        if self._signo is None:
            return
        self._saved_handler = signal.getsignal(self._signo)
        if self._saved_handler is None:
            _logger.warning(
                "An incompatible handler for signal %s was found; "
                + "Redzed will not catch this signal.",
                self._signame
                )
        else:
            signal.signal(self._signo, self._handler)

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> t.Literal[False]:
        if self._signo is not None and self._saved_handler is not None:
            signal.signal(self._signo, self._saved_handler)
        return False

    def _handler(self, signo: int, frame: FrameType|None) -> None:
        """A signal handler."""
        # - we need the _threadsafe variant of call_soon
        # - get_running loop() and get_circuit() will succeed,
        #   because this handler is active only during edzed.run()
        msg = f"Signal {self._signame!r} caught"
        call_soon = asyncio.get_running_loop().call_soon_threadsafe
        call_soon(_logger.warning, "%s", msg)
        call_soon(circuit.get_circuit().shutdown)
        if callable(self._saved_handler):
            self._saved_handler(signo, frame)
