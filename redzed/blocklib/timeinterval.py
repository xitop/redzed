"""
This module defines time/date intervals.

It is built on top of the datetime (dt) module:
    - time of day -> dt.time
    - date without a year -> dt.date with year set to a dummy value
    - date -> dt.date
    - full date+time -> dt.datetime

Intervals use those objects as endpoints:
    - TimeInterval defines time intervals within a day,
    - DateInterval defines periods in a year.
    - DateTimeInterval defines non-recurring intervals.

All intervals support the operation "value in interval".
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

from collections.abc import Sequence
import datetime as dt
import typing as t

# any sequence when importing, always a nested list when exporting
DT_Interval_Type = Sequence[Sequence[Sequence[int]]]

# endpoint type
_DateTimeType = t.TypeVar("_DateTimeType", dt.time, dt.date, dt.datetime)


_DT_ATTRS = "year month day hour minute second microsecond".split()

class _Interval(t.Generic[_DateTimeType]):
    """
    The common part of Date/Time Intervals.

    Warning: time/date intervals do not follow the strict mathematical
    interval definition.
    """

    # https://en.wikipedia.org/wiki/Interval_(mathematics)#Definitions_and_terminology
    # the subintervals are always left-closed
    _RCLOSED_INTERVAL: bool     # are the subintervals right-closed?
    _EXPORT_ATTRS: Sequence[str]

    @staticmethod
    def _convert(seq: Sequence[int]) -> _DateTimeType:
        raise NotImplementedError

    def convert(self, seq: Sequence[int]) -> _DateTimeType:
        try:
            return self._convert(seq)
        except Exception as err:
            err.add_note(f"Input value was: {seq!r}")
            raise

    def __init__(self, ivalue: DT_Interval_Type):
        """
        Argument ivalue must be a sequence of ranges:
            _Interval([subinterval1, subinterval2, ...])
        where each range (subinterval) is a pair of endpoints [begin, end].

        After splitting into endpoints, each value is converted
        to time/date according to the actual interval type.
        """
        self._interval: list[list[_DateTimeType]]
        if not isinstance(ivalue, Sequence) or isinstance(ivalue, str):
            raise TypeError(f"Unsupported argument type: {type(ivalue).__name__}")
        self._interval = sorted(self._parse_range(subint) for subint in ivalue)

    def _parse_range(self, rng: Sequence[Sequence[int]]) -> list[_DateTimeType]:
        """Parse: [begin, end]"""
        if not isinstance(rng, Sequence) or isinstance(rng, str):
            raise TypeError(
                f"Invalid range type. Expected was a pair [begin, and], got {rng!r}")
        if (length := len(rng)) != 2:
            raise ValueError(f"A range must have 2 endpoints, got range with {length}: {rng!r}")
        return [self.convert(rng[0]), self.convert(rng[1])]

    def range_endpoints(self) -> set[_DateTimeType]:
        """return all unique range start and stop values."""
        enpoints = set()
        for start, stop in self._interval:
            enpoints.add(start)
            enpoints.add(stop)
        return enpoints

    @staticmethod
    def _cmp_open(low: _DateTimeType, item: _DateTimeType, high: _DateTimeType) -> bool:
        """
        The ranges are left-closed and right-open intervals, i.e.
        value is in interval if and only if start <= value < stop
        """
        if low < high:
            return low <= item < high
        # low <= item < MAX or MIN <= item < high
        return low <= item or item < high

    @staticmethod
    def _cmp_closed(low: _DateTimeType, item: _DateTimeType, high: _DateTimeType) -> bool:
        """
        The ranges are closed intervals, i.e.
        value is in interval if and only if start <= value <= stop
        """
        if low <= high:
            return low <= item <= high
        return low <= item or item <= high

    def _cmp(self, *args: _DateTimeType) -> bool:
        return (self._cmp_closed if self._RCLOSED_INTERVAL else self._cmp_open)(*args)

    def __contains__(self, item: _DateTimeType) -> bool:
        return any(self._cmp(low, item, high) for low, high in self._interval)

    @classmethod
    def _export_dt(cls, dt_object: _DateTimeType) -> list[int]:
        """Export a date/time object."""
        return [getattr(dt_object, attr) for attr in cls._EXPORT_ATTRS]

    def as_list(self) -> DT_Interval_Type:
        """
        Return the intervals as a nested list of integers.

        The output is a list of endpoint pairs. Each endpoint is a list
        of integers. The output is suitable as an input argument.
        """
        return [
            [self._export_dt(start), self._export_dt(stop)]
            for start, stop in self._interval]


class TimeInterval(_Interval[dt.time]):
    """
    List of time ranges.

    The whole day is 00:00 - 00:00.
    """

    _RCLOSED_INTERVAL = False
    _EXPORT_ATTRS = _DT_ATTRS[3:]

    @staticmethod
    def _convert(seq: Sequence[int]) -> dt.time:
        """[hour, minute, second=0, microsecond=0] -> time of day"""
        if not 2 <= len(seq) <= 4:
            raise ValueError(
                f"{seq} not in expected format: [hour, minute=0, second=0, µs=0]")
        # mypy is overlooking that the seq cannot have more than 4 items
        return dt.time(*seq, tzinfo=None)      # type: ignore[misc, arg-type]


DUMMY_YEAR = 404
# 404 is a leap year (allows Feb 29) and is not similar
# to anything related to modern date values

class DateInterval(_Interval[dt.date]):
    """
    List of date ranges and single dates.
    """

    _RCLOSED_INTERVAL = True
    _EXPORT_ATTRS = _DT_ATTRS[1:3]

    @staticmethod
    def _convert(seq: Sequence[int]) -> dt.date:
        """[month, day] -> date (without year)"""
        if len(seq) != 2:
            raise ValueError(f"{seq} not in expected format: [month, day]")
        return dt.date(DUMMY_YEAR, *seq)


class DateTimeInterval(_Interval[dt.datetime]):
    """
    List of datetime ranges.
    """

    _RCLOSED_INTERVAL = False
    _EXPORT_ATTRS = _DT_ATTRS

    @staticmethod
    def _cmp_open(low: dt.datetime, item: dt.datetime, high: dt.datetime) -> bool:
        """Compare function for non-recurring intervals."""
        return low <= item < high

    @staticmethod
    def _convert(seq: Sequence[int]) -> dt.datetime:
        """[year, month, day, hour, minute, second=0, microsecond=0] -> datetime"""
        if not 5 <= len(seq) <= 7:
            raise ValueError(
                f"{seq} not in expected format: "
                "[year, month, day, hour, minute, second=0, µs=0]")
        # mypy is overlooking that the time_seq cannot have more than 7 items
        return dt.datetime(*seq, tzinfo=None)      # type: ignore[misc, arg-type]
