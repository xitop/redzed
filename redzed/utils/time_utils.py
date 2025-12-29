"""
Conversion routines for time periods/durations using multiple units.

Example: "20h15m10" = 20 hours + 15 minutes + 10 seconds = 72910 seconds
"""
from __future__ import annotations

__all__ = [
    'SEC_PER_DAY', 'SEC_PER_HOUR', 'SEC_PER_MIN',
    'fmt_period', 'parse_interval', 'time_period']

from collections.abc import Callable, Sequence
import re
import typing as t

from .data_utils import to_tuple


SEC_PER_DAY = 86_400
SEC_PER_HOUR = 3_600
SEC_PER_MIN = 60


def _fmt_parameters(seconds: float, approx: bool) -> tuple[int, int]:
    """Internal parameters for formatting."""
    # first value = exclusion of smallest units:
    #   6 = include everything, 5 = exclude: MS, 4 = exclude: S+MS, 3 = exclude: M+S+MS
    # second value = rounding unit in ms:
    if approx:
        if seconds >= 3 * SEC_PER_DAY:
            return (3, 1000 * SEC_PER_HOUR)
        if seconds >= SEC_PER_HOUR:
            return (4, 1000 * SEC_PER_MIN)
        if seconds >= SEC_PER_MIN:
            return (5, 1000)
        if seconds >= 10:
            return (6, 100)
        if seconds >= 3:
            return (6, 10)
    return (6, 1)


_UNITS = [('w', 'd', 'h', 'm', 's', 'ms'), ('W', 'D', 'H', 'M', 'S', 'MS')]
def fmt_period(
        seconds: float,
        iso8601: bool = False, sep: str = '', upper: bool = False, approx: bool = False
        ) -> str:
    """
    Return seconds as a string using units w, d, h, m, s and ms.

    The individual parts are separated with the 'sep' string.
    """
    if seconds < 0.0:
        raise ValueError("Number of seconds cannot be negative")
    if iso8601:
        upper = True
        sep = ''
    if seconds == 0.0:
        if iso8601:
            return "PT0S"
        return "0S" if upper else "0s"
    fmt_last, fmt_rounding = _fmt_parameters(seconds, approx)
    ms = int(1000 * seconds / fmt_rounding + 0.5) * fmt_rounding
    if ms == 0:
        if iso8601:
            return "PT0.001S"
        return "1MS" if upper else "1ms"
    s: int|float    # float only in iso8601 mode
    s, ms = divmod(ms, 1000)
    d, s = divmod(s, SEC_PER_DAY)
    if iso8601:
        w = 0
    else:
        w, d = divmod(d, 7)
    h, s = divmod(s, SEC_PER_HOUR)
    m, s = divmod(s, SEC_PER_MIN)
    if iso8601 and ms != 0:
        s += ms / 1000
        ms = 0
    numbers = [w, d, h, m, s, ms]
    units = _UNITS[bool(upper)]     # True == 1, False == 0
    for idx, value in enumerate(numbers):
        if value > 0:
            first = idx
            break
    for idx in range(fmt_last, 0, -1):
        if numbers[idx - 1] > 0:
            last = idx
            break
    assert first < last
    parts = [(str(n) + u) for n, u in zip(numbers[first:last], units[first:last], strict=True)]
    if iso8601:
        if last >= 3:
            # time units are included, must prepend 'T' before the first one
            parts.insert(max(0, 2 - first), 'T')
        parts.insert(0, 'P')
    return sep.join(parts)


_NUM = r'(\d+(?:[.,]\d*)?)'     # a match group for a number with optional fractional part
_RE_ISO_DURATION = re.compile(rf"""
    P
    (?: 0+Y)?
    (?: 0+M)?
    (?: {_NUM} W)?
    (?: {_NUM} D)?
    (?: T
        (?: {_NUM} H)?
        (?: {_NUM} M)?
        (?: {_NUM} S)?
    )?
    """, flags = re.ASCII | re.VERBOSE)
_RE_DURATION = re.compile(rf"""
    (?: {_NUM} \s* w \s*)?
    (?: {_NUM} \s* d \s*)?
    (?: {_NUM} \s* h \s*)?
    (?: {_NUM} \s* m \s*)?
    (?: {_NUM} \s* s \s*)?
    (?: {_NUM} \s* ms )?
    """, flags = re.ASCII | re.IGNORECASE | re.VERBOSE)

COEF = [0.001, 1, SEC_PER_MIN, SEC_PER_HOUR, SEC_PER_DAY, 7*SEC_PER_DAY]
ISO_COEF = COEF[1:]
def _str_to_period(tstr: str) -> float:
    """Convert string to number of seconds."""
    tstr = tstr.strip()
    iso = tstr.startswith("P")
    regex = _RE_ISO_DURATION if iso else _RE_DURATION
    if (match := regex.fullmatch(tstr)) is None:
        raise ValueError("Invalid time representation")

    result = 0.0
    smallest_unit = True
    for value, scale_factor in zip(reversed(match.groups()), ISO_COEF if iso else COEF):
        if value is None:
            continue
        if (decimal_comma := ',' in value) or ('.' in value):
            if not smallest_unit:
                raise ValueError("Only the smallest unit may have a fractional part")
            if decimal_comma:
                value = value.replace(',', '.', 1)
        num = float(value)
        smallest_unit = False
        if num == 0.0:
            continue
        if scale_factor is None:
            raise ValueError("Calendar years/months are not supported as duration units")
        result += num * scale_factor
    if smallest_unit:
        raise ValueError("At least one part must be present")
    return result


def time_period(
        period: t.Any,
        passthrough:None|type[object]|Sequence[None|type[object]] = (),
        zero_ok: bool = False) -> t.Any:
    """
    Convenience wrapper for convert().

    Return 'period' unchanged if its type is present in the
    'passthrough'. Otherwise convert a number or string to float.

    Argument 'passthrough' can be a type or a sequence of types.
    For convenience None is accepted as a type. Technically correct
    is NoneType, but in typing None is widely used.
    """
    if passthrough != ():
        passthrough = to_tuple(passthrough)
        if None in passthrough:
            if period is None:
                return None
            passthrough = tuple(t for t in passthrough if t is not None)
        if isinstance(period, t.cast(tuple[type[object], ...], passthrough)):
            return period
    saved_period = period
    if isinstance(period, str):
        try:
            period = _str_to_period(period)
        except Exception as err:
            err.add_note(f"Converted string was: '{period}'")
            raise
    elif isinstance(period, int):
        period = float(period)
    elif not isinstance(period, float):
        raise TypeError(f"Invalid type for time period specification: {period!r}")
    if period < 0:
        raise ValueError(f"Time period cannot be negative, got {saved_period}")
    if period == 0.0 and not zero_ok:
        raise ValueError("Time period must be positive, zero is not allowed.")
    return period


# integer sequence length limits for validation
_limits = {
    'date': (2, 2),
    'time': (2, 4),
    'datetime': (5, 7),
    None: (2, 7),   # unknown
}


def _sd_split(sd: str|Sequence[str], parsed_string:str) -> list[str]:
    """
    Choose a separator/deliemiter and split the *parsed_string*.

    If there are multiple choices, use the first one
    that is present in the *parsed_string*.
    """
    if not sd:
        raise ValueError("Got an empty separator or delimiter")
    if isinstance(sd, str):
        return parsed_string.split(sd)
    for try_sd in sd:
        if try_sd in parsed_string:
            return parsed_string.split(try_sd)
    return [parsed_string]


def parse_interval(
        interval: str, *,
        parser: Callable[[str], Sequence[int]],
        sep: str = "/", delim: str = ";",     # endpoint separator, range delimiter
        datatype: t.Literal['date', 'time', 'datetime'] | None = None,
        ) -> list[list[Sequence[int]]]:
    """
    Parse a string representation of a time/date/timedate interval.

    Intented for usage with TimeDate and TimeSpan blocks.
    """
    is_date = datatype == 'date'
    try:
        imin, imax = _limits[datatype]
    except KeyError:
        raise ValueError(
            "argument 'datatype' must be one of: 'date', 'time', 'datetime' or None, "
            + f"but got {datatype!r}") from None

    # wrap the parser
    def wparser(endpoint: str) -> Sequence[int]:
        value = parser(endpoint)
        if not imin <= len(value) <= imax:
            raise ValueError(
                f"Interval endpoint {endpoint} was not parsed correctly, "
                "please check the parser function")
        return value

    ranges = _sd_split(delim, interval)
    if ranges and not ranges[-1].strip():
        del ranges[-1]
    result = []
    for rng in ranges:
        elen = len(endpoints := _sd_split(sep, rng))
        if is_date and elen == 1:
            begin_end = wparser(rng.strip())
            result.append([begin_end, begin_end])
            continue
        if elen == 2:
            result.append([wparser(endpoints[0].strip()), wparser(endpoints[1].strip())])
            continue
        raise ValueError(f"A range cannot have {elen} endpoint(s): {rng}")
    return result
