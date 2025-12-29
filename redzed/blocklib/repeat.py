"""
An event repeater.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['Repeat']

import asyncio
import typing as t

import redzed
from redzed.utils import MsgSync, time_period


class Repeat(redzed.Block):
    """
    Periodically repeat the last received event.
    """

    def __init__(
            self, *args,
            dest: str|redzed.Block, interval: float|str, count: int|None = None,
            **kwargs
            ) -> None:
        self._dest = dest
        self._interval = time_period(interval)
        if count is not None and count < 0:
            # count = 0 (no repeating) is accepted
            raise ValueError("argument 'count' must not be negative")
        self._count = count
        self._sync: MsgSync[tuple[str, redzed.EventData]] = MsgSync()
        self._warning_logged = False
        super().__init__(*args, **kwargs)

    def rz_pre_init(self) -> None:
        """Resolve destination block name."""
        if not isinstance(dest := self.circuit.resolve_name(self._dest), redzed.Block):
            raise TypeError(
                f"{self}: {dest} is not a Block, but a Formula; cannot send events to it.")
        self._dest = dest
        self.circuit.create_service(self._repeater(), name=f"Event repeating task at {self}")

    def rz_init_default(self) -> None:
        self._set_output(0)

    async def _repeater(self) -> t.NoReturn:
        repeating = False
        repeat = 0      # prevent pylint warning
        while True:
            try:
                etype, edata = await self._sync.recv(
                    timeout=self._interval if repeating else None)
                repeat = 0
            except asyncio.TimeoutError:
                repeat += 1

            if repeat > 0:  # skip the original event
                self._set_output(repeat)
                assert isinstance(self._dest, redzed.Block)    # @mypy: name resolved
                self._dest.event(etype, **(edata | {'repeat': repeat}))
            repeating = self._count is None or repeat < self._count

    def _default_event_handler(self, etype: str, edata: redzed.EventData) -> None:
        # send the original event synchronously
        self._set_output(0)
        assert isinstance(self._dest, redzed.Block)    # mypy: name is resolved
        self._dest.event(etype, **(edata | {'repeat': 0}))
        self._sync.send((etype, edata))
