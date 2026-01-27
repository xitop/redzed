"""
Call the .rz_cron_event() method of all registered blocks at given times of day.

Blocks acting on given time, date and weekdays are implemented
on top of this low-level service.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

import asyncio
import bisect
from collections import deque
from collections.abc import Collection
import datetime as dt
import typing as t

from .block import Block, EventData
from .debug import get_debug_level
from .utils import SEC_PER_HOUR, SEC_PER_MIN, SEC_PER_DAY

# time tracking settings (in seconds)
_TT_OVERHEAD = 0.001    # asyncio sleep overhead estimation; real value will be measured
_TT_WARNING = 0.2       # timing difference threshold for a warning message
_TT_ERROR = 2.5         # timing difference threshold for a reset

# hourly wake ups for precise time tracking and early detection of DST changes
_SET24H = frozenset(dt.time(hour, 0, 0) for hour in range(24))


def _wait_time(t1: dt.time, t2: dt.time) -> float:
    """
    Return seconds from *t1* to *t2* on a 24 hour clock.

    The result is always between -1 and 23 hours (in seconds).
    Positive values are normal wait times (when *t2* is after *t1*).
    Negative values correspond to delays after a missed event
    (when *t2* is less than 1 hour before *t1*).
    """
    # datetime.time does not support time arithmetic
    diff = (SEC_PER_HOUR*(t2.hour - t1.hour)
        + SEC_PER_MIN*(t2.minute - t1.minute)
        + (t2.second - t1.second)
        + (t2.microsecond - t1.microsecond) / 1_000_000.0)
    if -SEC_PER_HOUR < diff <= 23 * SEC_PER_HOUR:
        return diff
    return diff + SEC_PER_DAY if diff < 0 else diff - SEC_PER_DAY


class Cron(Block):
    """
    Simple cron service.

    Do not use directly in circuits. It has a form of a logic block
    only to allow monitoring through the event interface.
    """

    RZ_RESERVED = True

    def __init__(self, *args, utc: bool, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._utc = bool(utc)
        self._alarms: dict[dt.time, set[Block]] = {tod: set() for tod in _SET24H}
        self._timetable: list[dt.time] = sorted(_SET24H)
            # timetable = sorted list (for bisection) of wake-up times (i.e. _alarms keys)
        self._tt_len = 24
        self._reversed: dict[Block, set[dt.time]] = {}
        self._do_reload = asyncio.Event()

    def rz_start(self) -> None:
        tz = 'UTC' if self._utc else 'local time'
        self.circuit.create_service(self._cron_daemon(), name=f"cron daemon ({tz})")

    def dtnow(self) -> dt.datetime:
        """Return the current date/time."""
        if self._utc:
            # but we need to keep all date/time object timezone naive
            # in order to make them mutually comparable
            return dt.datetime.now(dt.UTC).replace(tzinfo=None)
        return dt.datetime.now()

    def _check_tz(self, time_of_day: dt.time) -> None:
        """Check if the time zone is left unspecified (i.e. object is "naive")."""
        if not isinstance(time_of_day, dt.time):
            raise TypeError(
                f"time_of_day should be a datetime.time object, but got {time_of_day!r}")
        if time_of_day.tzinfo is not None:
            raise ValueError("time_of_day must not contain timezone data")

    def set_schedule(self, blk: Block, times_of_day: Collection[dt.time]) -> None:
        """Add a block to be activated at given times or update its schedule."""
        if not hasattr(blk, 'rz_cron_event'):
            raise TypeError(f"{blk} is not compatible with the cron service")
        for tod in times_of_day:
            self._check_tz(tod)
        self.log_debug2("Got a new schedule for %s", blk)
        times_of_day = set(times_of_day)

        # remove old times of day; it is not necessary to notify the main loop
        old_times = self._reversed.get(blk, set())
        for tod in old_times - times_of_day:
            self._alarms[tod].discard(blk)
        # add new times of day
        do_reload = False
        for tod in times_of_day - old_times:
            if tod in self._alarms:
                self._alarms[tod].add(blk)
            else:
                self._alarms[tod] = {blk}
                # new entry added to timetable; the main loop must be notified
                do_reload = True
        self._reversed[blk] = times_of_day
        if do_reload:
            self._do_reload.set()
        # cleanup
        for tod in [
                tod for tod, blks in self._alarms.items() if tod not in _SET24H and not blks]:
            del self._alarms[tod]

        self._timetable = sorted(self._alarms)
        self._tt_len = len(self._timetable)


    async def _cron_daemon(self) -> t.NoReturn:
        """Recalculate registered blocks according to the schedule."""
        reset_flag = False
        overhead = _TT_OVERHEAD       # an estimate to start with
        measured_overheads: deque[float] = deque(maxlen=8)
        prev_sleeptime: float
        long_sleep: bool
        wakeup: dt.time|None = None

        while True:
            nowdt = self.dtnow()
            nowt = nowdt.time()

            if wakeup is None or self._do_reload.is_set():
                index = bisect.bisect_left(self._timetable, nowt)
                next_wakeup = self._timetable[index % self._tt_len]
                # next_wakeup is new and wakeup was not processed yet,
                # all we need is to select which one comes first.
                if wakeup is None \
                        or next_wakeup != wakeup and _wait_time(next_wakeup, wakeup) > 0:
                    wakeup = next_wakeup
                # else: the current wakeup is confirmed
                self._do_reload.clear()
                self.log_debug1("wake-up time after reload: %s", wakeup)
            else:
                # return the next entry (in circular manner)
                index = bisect.bisect_right(self._timetable, wakeup)
                wakeup = self._timetable[index % self._tt_len]
                self.log_debug1("wake-up time: %s", wakeup)

            # sleep until the wake-up time:
            #   step 0: main sleep
            #       compute the delay until wake-up time and sleep
            #   steps 1 and 2: fine adjustment
            #       check the current time, adjust overhead estimate and
            #           - finish if the time is correct, or
            #           - add a tiny sleep if woken up too early, because
            #             that is not acceptable, or
            #           - do a reset if the time is way off
            #   steps 3 and 4: safety net
            #       like above, just for the case the computer clock
            #       does something unexpected
            for step in range(5):
                sleeptime = _wait_time(nowt, wakeup)    # negative = we are late
                debug2 = get_debug_level() >= 2
                if step == 0:
                    if debug2:
                        self.log_debug("sleep until wake up: %.3f sec", sleeptime)
                else:
                    diff = abs(sleeptime)
                    after = sleeptime <= 0.0
                    if diff > _TT_WARNING:
                        self.log_warning(
                            "expected time: %s, current time: %s, diff: %.1f sec %s",
                            wakeup, nowt, diff, 'after' if after else 'BEFORE')
                    elif debug2:
                        self.log_debug(
                            "iteration %d, diff %.2f ms %s",
                            step, 1000*diff, 'after' if after else 'BEFORE')
                    # prev_sleeptime and long_sleep has been set in previous step
                    # pylint: disable=used-before-assignment
                    if diff > _TT_ERROR or sleeptime > prev_sleeptime or step == 4:
                        # something is wrong with the computer clock
                        reset_flag = True
                        break
                    if long_sleep:
                        saved = overhead
                        measured_overheads.append(overhead - sleeptime)
                        # Using smallest overhead recently measured, because to be late
                        # by a tiny amount is much better than to wake up early by a tiny
                        # amount. The latter case must be corrected by another sleep.
                        overhead = min(measured_overheads)
                        if debug2 and overhead != saved:
                            self.log_debug("estimated overhead >= %.2f ms", 1000*overhead)
                    if after:
                        break
                    if debug2:
                        self.log_debug("additional sleep %.2f ms", 1000*sleeptime)
                prev_sleeptime = sleeptime

                if (long_sleep := sleeptime > overhead):
                    try:
                        async with asyncio.timeout(sleeptime - overhead):
                            await self._do_reload.wait()
                    except TimeoutError:
                        pass    # no reload request
                    else:
                        break   # reload request arrived
                elif sleeptime > 0.0:
                    await asyncio.sleep(sleeptime)
                nowdt = self.dtnow()
                nowt = nowdt.time()
            # --- end for loop ---

            if reset_flag:
                # DST begin/end or other computer clock related reason
                if (not self._utc and nowdt.isoweekday() >= 6
                        and abs(diff - SEC_PER_HOUR) <= _TT_ERROR):
                    self.log_warning("Apparently a DST (summer time) clock change has occured.")
                self.log_warning(
                    "Resetting due to a time tracking problem. "
                    + "Notifying all registered blocks.")
                # .rz_cron_event() may alter the dict we are iterating over
                for blk in list(self._reversed):    # all blocks
                    assert hasattr(blk, 'rz_cron_event')
                    blk.rz_cron_event(nowdt)
                reset_flag = False
                wakeup = None
                continue
            if self._do_reload.is_set():
                continue

            if wakeup not in self._alarms:
                continue    # entry removed in the meantime
            # .rz_cron_event() may alter the set we are iterating over
            block_list = list(self._alarms[wakeup])
            if get_debug_level() >= 1:
                self.log_debug(
                    "Notifying block(s): %s", ", ".join(blk.name for blk in block_list))
            for blk in block_list:
                assert hasattr(blk, 'rz_cron_event')
                blk.rz_cron_event(nowdt)

    def _event__get_config(self, _edata: EventData) -> dict[str, dict[str, list[str]]]:
        """Return the internal scheduling data for debugging or monitoring."""
        return {
            'alarms': {
                str(tod): sorted(blk.name for blk in blks)
                for tod, blks in self._alarms.items() if blks},
            'blocks': {blk.name: sorted(str(tod) for tod in tods)
                for blk, tods in self._reversed.items()},
            }
