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
import random
import typing as t

import redzed
from redzed.utils import time_period


class Repeat(redzed.Block):
    """
    Periodically repeat the last received event.
    """

    def __init__(
            self, *args,
            dest: str|redzed.Block, interval: float|str, count: int|None = None,
            jitter_pct: float = 0.0,
            **kwargs
            ) -> None:
        self._dest = dest
        self._default_interval = time_period(interval)
        if count is not None and count < 0:
            # count = 0 (no repeating) is accepted
            raise ValueError("argument 'count' must not be negative")
        self._default_count = count
        if jitter_pct == 0.0:
            self._jitter = None
        else:
            if not 0.0 < jitter_pct <= 50.0:
                raise ValueError(
                    "Argument jitter_pct (percentage) must be between 0 and 50, "
                    + f"got {jitter_pct}")
            self._jitter = (1 - jitter_pct/100.0, 1 + jitter_pct/100.0)
        self._new_event = asyncio.Event()
        # current event
        self._etype: str
        self._edata: redzed.EventData
        self._interval: float
        self._count: int|None
        super().__init__(*args, **kwargs)

    def rz_pre_init(self) -> None:
        """Resolve destination block name."""
        dest = self.circuit.resolve_name(self._dest)
        if isinstance(dest, redzed.Formula):
            raise TypeError(f"{self}: {dest} is a Formula; cannot send events to it.")
        if isinstance(dest, type(self)):
            raise TypeError(f"{self}: {dest} is another Repeat block; this is not allowed")
        self._dest = dest
        self.circuit.create_service(self._repeater(), name=f"Event repeating task at {self}")

    def rz_init_default(self) -> None:
        self._set_output(0)

    async def _repeater(self) -> t.NoReturn:
        repeating = False
        repeat = 0      # prevent pylint warning
        while True:
            try:
                if repeating:
                    interval = self._interval
                    if self._jitter is not None:
                        interval *= random.uniform(*self._jitter)
                else:
                    interval = None
                async with asyncio.timeout(interval):
                    await self._new_event.wait()
            except asyncio.TimeoutError:
                pass
            # getting a timeout does not necessarily mean the event was not set
            if self._new_event.is_set():
                self._new_event.clear()
                repeat = 0
            else:
                repeat += 1

            if repeat > 0:  # skip the original event
                self._set_output(repeat)
                assert isinstance(self._dest, redzed.Block)    # @mypy: name resolved
                self._dest.event(self._etype, **(self._edata | {'repeat': repeat}))
            repeating = self._count is None or repeat < self._count

    def _default_event_handler(self, etype: str, edata: redzed.EventData) -> None:
        # send the original event synchronously
        self._set_output(0)
        assert isinstance(self._dest, redzed.Block)    # mypy: name is resolved
        self._etype = etype
        self._edata = edata
        self._interval = edata.pop('repeat_interval', self._default_interval)
        self._count = edata.pop('repeat_count', self._default_count)
        self._dest.event(etype, **(edata | {'repeat': 0}))
        self._new_event.set()
