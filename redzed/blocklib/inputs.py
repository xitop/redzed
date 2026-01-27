"""
A single memory cell blocks for general use.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['Memory', 'MemoryExp', 'DataPoll']

import asyncio
from collections.abc import Callable, Sequence
import time
import typing as t

import redzed
from redzed.utils import is_multiple, time_period
from .fsm import FSM
from .validator import _Validate


class Memory(_Validate, redzed.Block):
    """
    Memory cell with optional value validation.

    Memory is typically used as an input block.
    """

    def _event_store(self, edata: redzed.EventData) -> bool:
        """Validate and store a value."""
        evalue = edata['evalue']
        try:
            validated = self._validate(evalue)
        except Exception:
            if edata.get('suppress', False):
                return False
            raise
        self._set_output(validated)
        return True

    def rz_init(self, init_value: t.Any, /) -> None:
        validated = self._validate(init_value)
        self._set_output(validated)

    def rz_export_state(self) -> t.Any:
        return self.get()

    def rz_restore_state(self, state: t.Any, /) -> None:
        # Do not validate. *state* is already validated and thus possibly preprocessed.
        self._set_output(state)


class MemoryExp(_Validate, FSM):
    """
    Memory cell with an expiration time.
    """

    STATES = ['expired', ['valid', None, 'expired']]

    def __init__(
            self, *args,
            duration: float|str|None,
            expired: t.Any = None,
            **kwargs) -> None:  # kwargs may contain a validator
        super().__init__(*args, t_valid=duration, **kwargs)
        try:
            self._expired = self._validate(expired)
        except Exception as err:
            err.add_note(f"{self}: The validator rejected the 'expired' argument {expired!r}")
            raise

    def _store(self, validated: t.Any) -> None:
        if validated == self._expired:
            self._goto('expired')
        else:
            self.sdata['memory'] = validated
            self._goto('valid')

    def _event_store(self, edata: redzed.EventData) -> bool:
        evalue = edata['evalue']
        validated = self._validate(evalue)
        try:
            validated = self._validate(evalue)
        except Exception:
            if edata.get('suppress', False):
                return False
            raise
        self._store(validated)
        return True

    def rz_init(self, init_value: t.Any, /) -> None:
        validated = self._validate(init_value)
        if validated == self._expired:
            super().rz_init('expired')
        else:
            self.sdata['memory'] = validated
            super().rz_init('valid')

    def enter_expired(self) -> None:
        self.sdata.pop('memory', None)

    def _set_output(self, output: t.Any) -> bool:
        return super()._set_output(
            self.sdata['memory'] if self.state == 'valid' else self._expired)


class DataPoll(redzed.Block):
    """
    A source of sampled or computed values.
    """

    def __init__(
        self, *args,
        func: Callable[[], t.Any],
        interval: float|str,
        retry_interval: None|float|str|Sequence[float|str] = None,
        abort_after_failures: int = 0,
        **kwargs) -> None:
        self._func = func
        self._interval = time_period(interval)
        if retry_interval is None:
            self._r_interval_min = self._r_interval_max = self._interval
        elif is_multiple(retry_interval):
            assert isinstance(retry_interval, Sequence)     # @mypy
            if (ri_len := len(retry_interval)) != 2:
                raise ValueError(
                    "Exponential backoff expects exactly two values [T_min, T_max], "
                    + f"but got {ri_len}")
            self._r_interval_min = time_period(retry_interval[0])
            self._r_interval_max = time_period(retry_interval[1])
            if self._r_interval_max < self._r_interval_min * 2:
                raise ValueError("Exponential backoff requires T_max >= 2*T_min")
        else:
            self._r_interval_min = self._r_interval_max = time_period(retry_interval)
        if any (t <= 0.0 for t in [self._interval, self._r_interval_min, self._r_interval_max]):
            raise ValueError(f"{self} Time intervals must be positive")
        self._abort_after_failures = abort_after_failures
        super().__init__(*args, **kwargs)

    def rz_pre_init(self) -> None:
        self.circuit.create_service(
            self._poller(), name=f"Data polling task at {self}", immediate_start=True)

    async def _poller(self) -> t.NoReturn:
        """Data polling task: repeatedly get a value."""
        await self.circuit.reached_state(redzed.CircuitState.INIT_BLOCKS)
        failures = 0
        while True:
            value = self._func()
            if asyncio.iscoroutine(value):
                start_ts = time.monotonic()
                value = await value
                duration = time.monotonic() - start_ts
            else:
                duration = 0
            if value is redzed.UNDEF:
                failures += 1
                self.log_debug1("Data acquisition failure(s): %d", failures)
                if 0 < self._abort_after_failures <= failures:
                    self.circuit.abort(
                        RuntimeError(f"{self}: No data in {failures} polling cycle(s)"))
                if failures == 1:
                    interval = self._r_interval_min
                elif interval < self._r_interval_max:
                    interval = min(2*interval, self._r_interval_max)
            else:
                failures = 0
                self._set_output(value)
                interval = self._interval
            if duration > 0:
                interval = max(interval - duration, 0.0)
            await asyncio.sleep(interval)
        assert False, "Not reached"

    def rz_init(self, init_value: t.Any, /) -> None:
        self._set_output(init_value)

    def rz_export_state(self) -> t.Any:
        return self.get()

    rz_restore_state = rz_init
