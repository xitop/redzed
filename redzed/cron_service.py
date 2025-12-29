"""
Call the .rz_cron_event() method of all registered blocks at given times of day.

Blocks acting on given time, date and weekdays are implemented
on top of this low-level service.

- - - - - -
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

import asyncio
import bisect
from collections.abc import Collection
import datetime as dt
import time
import typing as t

from .block import Block, EventData
from .debug import get_debug_level
from .utils import SEC_PER_HOUR, SEC_PER_MIN, SEC_PER_DAY

# time tracking accuracy (in seconds)
_TT_OK = 0.001          # desired accuracy
_TT_WARNING = 0.1       # log a warning when exceeded
_TT_ERROR = 2.5         # do a reset when exceeded
_SYNC_SLEEP = 0.000_2   # sleeps <= 200 µs can be blocking for sake of accuracy

# hourly wake-ups for precise time tracking and early detection of DST changes
_SET24 = frozenset(dt.time(hour, 0, 0) for hour in range(24))


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
        self._alarms: dict[dt.time, set[Block]] = {}
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
        """
        Add a block to be activated at given times or update its schedule.

        The block's 'rz_cron_event' method will be called at given time
        and also when this service is started, reset or reloaded.

        A datetime.datetime object will be passed to the blk as its
        only argument.
        """
        if not hasattr(blk, 'rz_cron_event'):
            raise TypeError(f"{blk} is not compatible with the cron service")

        times_of_day = set(times_of_day) # make a set, make a copy
        # remove old times of day
        old_times = self._reversed.get(blk, set())
        for tod in old_times - times_of_day:
            self._alarms[tod].discard(blk)

        do_reload = False
        # add new times of day
        for tod in times_of_day - old_times:
            self._check_tz(tod)
            if tod in self._alarms:
                self._alarms[tod].add(blk)
            else:
                self._alarms[tod] = {blk}
                if tod not in _SET24:
                    do_reload = True    # new entry added to timetable
        self._reversed[blk] = times_of_day

        # cleanup
        unused = [tod for tod, blkset in self._alarms.items() if not blkset]
        for tod in unused:
            del self._alarms[tod]
            if tod not in _SET24:
                do_reload = True    # empty entry removed from the timetable
        if do_reload:
            self._do_reload.set()

    async def _cron_daemon(self) -> t.NoReturn:
        """Recalculate registered blocks according to the schedule."""
        overhead = _TT_OK   # initial value, will be adjusted
                            # the sleeptime is reduced by this value
        reset_flag = False
        reload_flag = True      # reload will also initialize the index
        short_sleep = False     # alternative sleep function used => do not compute overhead
        while True:
            if reload_flag:
                timetable = sorted(_SET24.union(self._alarms))
                tlen = len(timetable)
                self.log_debug1("time schedule reloaded")
                index = None
                reload_flag = False

            nowdt = self.dtnow()
            nowt = nowdt.time()
            if index is None:
                # reload is set before entering the loop -> "tlen" gets initialized
                # pylint: disable-next=possibly-used-before-assignment
                index = bisect.bisect_left(timetable, nowt) % tlen
            wakeup = timetable[index]
            self.log_debug1("wakeup time: %s", wakeup)

            # sleep until the wakeup time:
            # step 0 - compute the delay until wakeup time
            #        - sleep
            # step 1 - check the current time, adjust overhead estimate,
            #            A: finish if the time is correct, or
            #            B: add a tiny sleep if woken up too early, because
            #               continuing before wakeup time is not acceptable
            #            C: do a reset if the time is way off
            # step 2 - check time after 1B,
            #            A: finish if the time is correct
            #            B: do a reset otherwise
            for step in range(3):
                # datetime.time does not support time arithmetic
                sleeptime = (SEC_PER_HOUR*(wakeup.hour - nowt.hour)
                    + SEC_PER_MIN*(wakeup.minute - nowt.minute)
                    + (wakeup.second - nowt.second)
                    + (wakeup.microsecond - nowt.microsecond)/ 1_000_000.0)
                if nowt.hour == 23 and wakeup.hour == 0:
                    # wrap around midnight (relying on hourly wakeups in SET24)
                    sleeptime += SEC_PER_DAY
                # sleeptime: negative = after the alarm time; positive = before the alarm time
                if step == 0:
                    self.log_debug2("sleep until wakeup: %.3f sec", sleeptime)
                if step >= 1 or sleeptime < 0:
                    diff = abs(sleeptime)
                    if get_debug_level() >= 2:
                        msg = 'BEFORE' if sleeptime > 0 else 'after'
                        self.log_debug(
                            "step %d, diff %.2f ms %s, estimated overhead: %.2f ms",
                            step, 1000*diff, msg, 1000*overhead)
                    if diff > _TT_WARNING:
                        self.log_warning(
                            "expected time: %s, current time: %s, diff: %.2f ms.",
                            wakeup, nowt, 1000*diff)
                    if (step == 2 and sleeptime > 0) or diff > _TT_ERROR:
                        reset_flag = True
                    if reset_flag:
                        break
                    if step == 1 and not short_sleep and not -_TT_OK <= sleeptime <= 0:
                        overhead -= (sleeptime + _TT_OK/2) / 2      # average of new and old
                    if sleeptime <= 0:
                        break
                    if get_debug_level() >= 2:
                        self.log_debug("additional sleep %.2f ms", 1000*sleeptime)

                if sleeptime == 0.0:
                    pass    # how likely is this?
                elif sleeptime <= _SYNC_SLEEP:
                    short_sleep = True
                    # breaking the asyncio rules for max time tracking accuracy:
                    # doing a blocking sleep, but only for a fraction of a millisecond
                    time.sleep(sleeptime)
                elif sleeptime <= overhead:
                    short_sleep = True
                    await asyncio.sleep(sleeptime)
                else:
                    short_sleep = False
                    try:
                        async with asyncio.timeout(sleeptime - overhead):
                            await self._do_reload.wait()
                    except TimeoutError:
                        pass
                    else:
                        self._do_reload.clear()
                        reload_flag = True
                        break
                nowdt = self.dtnow()
                nowt = nowdt.time()

            if reset_flag:
                # DST begin/end or other computer clock related reason
                if (not self._utc
                        and nowdt.isoweekday() >= 6
                        and abs(diff - SEC_PER_HOUR) <= _TT_ERROR
                        ):
                    self.log_warning("Apparently a DST (summer time) clock change has occured.")
                self.log_warning(
                    "Resetting due to a time tracking problem. "
                    + "Notifying all registered blocks.")
                # .rz_cron_event() may alter the dict we are iterating over
                for blk in list(self._reversed):    # all blocks
                    assert hasattr(blk, 'rz_cron_event')
                    blk.rz_cron_event(nowdt)
                index = None
                reset_flag = False
                continue
            if reload_flag:
                continue

            if wakeup in self._alarms:
                # .rz_cron_event() may alter the set we are iterating over
                block_list = list(self._alarms[wakeup])
                if get_debug_level() >= 1:
                    self.log_debug(
                        "Notifying blocks: %s", ", ".join(blk.name for blk in block_list))
                for blk in block_list:
                    assert hasattr(blk, 'rz_cron_event')
                    blk.rz_cron_event(nowdt)
            index = (index + 1) % tlen

    def _event__get_config(self, _edata: EventData) -> dict[str, dict[str, list[str]]]:
        """Return the internal scheduling data for debugging or monitoring."""
        return {
            'alarms': {
                str(recalc_time): sorted(blk.name for blk in blk_set)
                for recalc_time, blk_set in self._alarms.items()},
            'blocks': {blk.name: sorted(str(recalc_time) for recalc_time in times_set)
                for blk, times_set in self._reversed.items()},
            }
