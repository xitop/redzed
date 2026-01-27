"""
Periodic events at fixed time/date.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
import datetime as dt
import typing as t

import redzed
from . import timeinterval as ti
from ..cron_service import Cron


__all__ = ['TimeDate', 'TimeSpan']

def _get_cron(utc: bool) -> Cron:
    name = '_cron_utc' if utc else '_cron_local'
    return t.cast(Cron, redzed.get_circuit().resolve_name(name))


_MIDNIGHT = dt.time(0, 0, 0)


class _ConfigType(t.TypedDict):
    times: t.NotRequired[ti.DT_Interval_Type]
    dates: t.NotRequired[ti.DT_Interval_Type]
    weekdays: t.NotRequired[Sequence[int]]


class TimeDate(redzed.Block):
    """
    Block for periodic events at given time/date.
    """

    def __init__(self, *args, utc: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cron = _get_cron(utc)
        self._times: ti.TimeInterval | None = None
        self._dates: ti.DateInterval | None = None
        self._weekdays: Set[int] | None = None

    def _reconfig(self, config: _ConfigType) -> None:
        """Reconfigure the block."""
        if extra := config.keys() - {'times', 'dates', 'weekdays'}:
            raise ValueError(f"{self}: Unexpected key '{next(iter(extra))}' in configuration")
        times = config.get('times', None)
        dates = config.get('dates', None)
        weekdays = config.get('weekdays', None)
        if all(cfg is None for cfg in [times, dates, weekdays]):
            raise ValueError("Empty configuration data")
        self._times = None if times is None else ti.TimeInterval(times)
        self._dates = None if dates is None else ti.DateInterval(dates)
        if weekdays is None:
            self._weekdays = None
        else:
            if not all(0 <= x <= 7 for x in weekdays):
                raise ValueError(
                    "Only numbers 0 or 7 (Sun), 1 (Mon), ... 6(Sat) are accepted as weekdays")
            self._weekdays = frozenset(7 if x == 0 else x for x in weekdays)

        endpoints = self._times.range_endpoints() if self._times is not None else set()
        if self._dates or self._weekdays:
            endpoints.add(_MIDNIGHT)
        self._cron.set_schedule(self, endpoints)
        self.rz_cron_event(self._cron.dtnow())

    def rz_init(self, value: _ConfigType, /) -> None:
        if not isinstance(value, Mapping):
            raise TypeError(
                "Initialization value must be a dict (mapping), "
                + f"but got {type(value).__name__}")
        self._reconfig(value)

    def rz_init_default(self) -> None:
        self._times = None
        self._dates = None
        self._weekdays = frozenset()
        self._set_output(False)

    def _event_reconfig(self, edata: redzed.EventData) -> None:
        self._reconfig(edata['evalue'])

    def _event__get_config(self, _edata: redzed.EventData) -> dict[str, Sequence|None]:
        # _get_config event == _get_state event == rz_export_state function
        return self.rz_export_state()

    def rz_cron_event(self, now: dt.datetime) -> None:
        """Update the output."""
        self._set_output(
            (self._weekdays is None or now.isoweekday() in self._weekdays)
            and (self._times is None or now.time() in self._times)
            and (self._dates is None
                 or dt.date(ti.DUMMY_YEAR, now.month, now.day) in self._dates)
            )

    def rz_export_state(self) -> dict[str, Sequence|None]:
        return {
            'times': None if self._times is None else self._times.as_list(),
            'dates': None if self._dates is None else self._dates.as_list(),
            'weekdays': None if self._weekdays is None else sorted(self._weekdays),
        }

    rz_restore_state = rz_init


class TimeSpan(redzed.Block):
    """
    Block active between start and stop time/date.
    """

    def __init__(self, *args, utc: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._cron = _get_cron(utc)
        self._span: ti.DateTimeInterval

    def _reconfig(self, config: ti.DT_Interval_Type) -> None:
        """Reconfigure the block."""
        self._span = ti.DateTimeInterval(config)
        now = self._cron.dtnow()
        now_date = now.date()
        endpoints = {ep.time() for ep in self._span.range_endpoints() if ep.date() >= now_date}
        self._cron.set_schedule(self, endpoints)
        self.rz_cron_event(now)

    rz_init = _reconfig

    def rz_init_default(self) -> None:
        self._reconfig([])

    def _event_reconfig(self, edata: redzed.EventData) -> None:
        self._reconfig(edata['evalue'])

    def _event__get_config(self, _edata: redzed.EventData) -> ti.DT_Interval_Type:
        # _get_config event == _get_state event == rz_export_state function
        return self.rz_export_state()

    def rz_cron_event(self, now: dt.datetime) -> None:
        """Update the output."""
        self._set_output(now in self._span)

    def rz_export_state(self) -> ti.DT_Interval_Type:
        return self._span.as_list()

    rz_restore_state = _reconfig
