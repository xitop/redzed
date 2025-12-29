"""
Helpers for unit tests.
"""
from __future__ import annotations

import asyncio
import itertools
import time
# import typing as t

import redzed


class EventMemory(redzed.Block):
    """Accept any event. Output the last event."""

    def _default_event_handler(self, etype: str, edata: redzed.EventData) -> None:
        evalue = edata.pop('evalue', redzed.UNDEF)
        self._set_output((etype, evalue, edata) if edata else (etype, evalue))


def strip_ts(storage: dict) -> dict:
    """Strip timestamps from "persistent" storage."""
    return {k:v[0] for k, v in storage.items()}


def add_ts(storage: dict, age: float = 60.0) -> dict:
    """Add timestamps to "persistent" storage."""
    ts = time.time() - age
    return {k:[v, ts] for k, v in storage.items()}


_FILL = object()
_AFMT = ("timestamps: {} is way {} expected {}\n"
         + "(please repeat; timing tests may produce a false negative under high load!)")

def compare_logs(tlog, slog, delta_abs=10, delta_rel=0.15):
    """
    Compare the tlog (TimeLogger's log) with an expected standard slog.

    The allowed negative difference is only 1/10 of the allowed positive
    difference, because due to CPU load and overhead the tlog is
    expected to lag behind the slog, and not to outrun it.

    delta_abs is in milliseconds (10 = +10/-2 ms difference allowed),
    delta_rel is a ratio (0.15 = +15/-3 % difference allowed),
    the timestamp values must pass the combined delta.

    Timestamp 0.0 (expected value) is not checked at all,
    because most false negatives were caused by startup
    delays.
    """
    for (tts, tmsg), (sts, smsg) in itertools.zip_longest(tlog, slog, fillvalue=(_FILL, None)):
        assert tts is not _FILL, f"Missing: {(sts, smsg)}"
        assert sts is not _FILL, f"Extra: {(tts, tmsg)}"
        assert tmsg == smsg, f"data: {(tts, tmsg)} does not match {(sts, smsg)}"
        if sts is None or sts == 0:
            continue
        assert (tts - delta_abs)/sts <= 1.0 + delta_rel, _AFMT.format(tts, "above", sts)
        assert (tts + delta_abs/10)/sts >= 1.0 - delta_rel/10, _AFMT.format(tts, "below", sts)


class TimeLogger(redzed.Block):
    """
    Maintain a log with relative timestamps in milliseconds since start.

    Usage: - logger.log('log entry'), or
           - send a 'log' event with value='log entry'
    """

    def __init__(
            self, *args,
            mstart=False, mstop=False, log_edata=False, triggered_by=None,
            **kwargs
            ):
        self.tlog = []
        self._log_edata = log_edata
        if triggered_by:
            def logger_trigger(log_entry=triggered_by):
                self.log(log_entry)
            redzed.Trigger(logger_trigger)
        self._mstart = mstart   # add a "--start --" mark
        self._mstop = mstop     # -- stop -- mark
        super().__init__(*args, **kwargs)

    def log(self, log_entry):
        self.tlog.append((int(1000*self.circuit.runtime() + 0.5), log_entry))

    def _event_log(self, edata):
        if self._log_edata:
            self.log(edata)
        else:
            self.log(edata.get('evalue', redzed.UNDEF))

    def rz_start(self):
        if self._mstart:
            self.log('--start--')

    def rz_stop(self):
        if self._mstop:
            self.log('--stop--')

    def compare(self, slog, **kwargs):
        """Compare the log with an expected standard."""
        compare_logs(self.tlog, slog, **kwargs)


async def _test_runner(coro=None, sleep=None, timeout=3.0, immediate=False) -> None:
    """A universal circuit tester wrapper."""
    # the *timeout* argument applies to *coro()* only, not to the whole test run
    circuit = redzed.get_circuit()
    if not immediate and not await circuit.reached_state(redzed.CircuitState.RUNNING):
        raise asyncio.CancelledError("Circuit start failed")
    if coro is not None:
        if sleep is not None:
            raise TypeError("coro= and sleep= are mutually exclusive arguments.")
        async with asyncio.timeout(timeout):
            await coro
    else:
        if sleep is None:
            sleep = timeout + 1.0
        sleep -= circuit.runtime()
        if sleep > 0:
            await asyncio.sleep(sleep)
    circuit.shutdown()
    await circuit.reached_state(redzed.CircuitState.CLOSED)


def runtest(*args, **kwargs):
    return redzed.run(_test_runner(*args, **kwargs))


def mini_init(circuit):
    """
    Initialize circuit for testing without requiring asyncio.

    This function attempts to copy the real runner's initialization
    code as close as possible.

    Circuits with asyncio based blocks should be tested
    with the regular runner.
    """
    # pylint: disable=protected-access
    circuit._check_persistent_storage()
    get_items = circuit.get_items
    for blk in get_items(redzed.Block):
        if blk.has_method('rz_pre_init'):
            blk.rz_pre_init()
    for frm in get_items(redzed.Formula):
        frm.rz_pre_init()
    blocks = list(get_items(redzed.Block))
    for blk in blocks:
        if blk.is_undef():
            circuit.init_block_sync(blk)
    for blk in blocks:
        if blk.is_undef():
            raise RuntimeError(f"Block {blk.name} was not initialized")
    for trig in get_items(redzed.Trigger):
        trig.rz_pre_init()
        trig.rz_start()
    for blk in blocks:
        if blk.has_method('rz_start'):
            blk.rz_start()
    circuit._start_ts = time.monotonic()
