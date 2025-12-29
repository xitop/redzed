.. module:: redzed.utils

=========
Utilities
=========

Time durations with units
=========================

Time is measured in seconds, but Redzed classes accept also durations and time periods
represented as strings with time units like weeks, days or minutes. The general
requirements for such string are:

- At least one item (number + unit) must be present.
- Only the smallest unit may have a fractional part.
- Both decimal point and decimal comma are supported.
- Numbers do not have to be normalized, e.g. ``48H`` is fine (same as ``2D``).
- Underscores in numbers (e.g. ``1_500``)
  and scientific notation (e.g. ``1e3``) are not supported.
- One day is always 24 hours and one week always lasts 7*24 hours. Switching from or to
  daylight saving time (summer time) during that time is not taken into account.


**The basic format:**

  Duration = ``[n W] [n D] [n H] [n M] [n S] [n MS]``

Examples:

  | ``'2m'`` = 2 minutes = 120.0 seconds
  | ``'20h15m10s'`` = 20 hours + 15 minutes + 10 seconds = 72_910.0
  | ``'2d 12h'`` = 2 days + 12 hours = 216_000.0
  | ``'1.25 H'`` = 1 and a quarter of and hour = 4_500.0
  | ``'200ms'`` = 200 milliseconds = 0.2


- Unit symbols ``W``, ``D``, ... ``MS`` may be entered also in lower case.
- Whitespace around numbers and units is allowed.


**The ISO 8601 format:**

  Duration = ``P [0Y] [0M] [nW] [nD] [T [nH] [nM] [nS]]``

Description with examples: `Wikipedia [↗] <https://en.wikipedia.org/wiki/ISO_8601#Durations>`__.
This implementation differs slightly from the ISO 8601 specification:

- Calendar years and months are not supported. Only ``0Y`` and ``0M`` are accepted
  for compatibility.
- Weeks can be used together with other units.
- One day is always 24 hours.

----

Conversions routines:

.. function:: fmt_period(seconds: float, iso8601: bool = False, sep: str = '', upper: bool = False, approx: bool = False) -> str

  Convert time period or duration *seconds* to a string with time units.
  The units are weeks (``w``), days (``d``), ... etc ...,
  seconds (``s``) and milliseconds (``s``). The individual parts
  are separated with the *sep* string. The unit symbols are in lower
  case by default. Set the *upper* flag to switch to the upper case.

  If the *iso8601* flag is set, the output is ISO 8601 compatible.
  Arguments *upper*  and *sep* are ignored in this mode.

  Argument *seconds* cannot be negative. Value 0.0 is converted to "0s",
  values below 0.001 are converted to "1ms" (or equivalent - depending
  on flags). All remaining values are rounded to whole milliseconds.

  When *approx* flag is set, the conversion rounds off the least significant part
  of the value to make the result shorter and better human readable.

.. function:: time_period(period: Any, passthrough=(), zero_ok: bool = False) -> Any

  Convert time period/duration given as a number or as a string with units.

  The *passthrough* argument is a type or a sequence of types that should be
  returned untouched. For convenience :const:`None` can be given directly
  (the exact type is ``type(None)``).

  .. function:: time_period(period: T, passthrough=T) -> T
    :noindex:

    If passthrough contains the type ``T``, arguments of that type are returned as-is.
    This simplifies the use of sentinels like e.g. :const:`None`.

  .. function:: time_period(period: str|float, zero_ok=False) -> float
    :noindex:

    Integers, floats or strings will be converted to a number of seconds.
    For other argument types a :exc:`!TypeError` will be raised.

    The conversion result is always a float.
    Negative time periods are rejected with :exc:`!ValueError`.
    Period/duration of 0.0 is accepted only if *zero_ok* is set.


Clock related constants
=======================

.. data:: SEC_PER_DAY
          SEC_PER_HOUR
          SEC_PER_MIN

    Seconds per day, hour, minute (integers).


Date/time intervals as strings
==============================

The following utility is intended for use with :class:`redzed.TimeDate`
and :class:`redzed.TimeSpan`. It converts a string to a nested list
of integers that these blocks accept. Strings are sometimes preferred
for their human readability.

.. function:: parse_interval(interval, *, parser, sep="/", delim=";", datatype=None) -> list[list[Sequence[int]]]

  :param str interval: Input string
  :param Callable[[str], Sequence[int]] parser:
    User-supplied function converting one endpoint of selected type from
    the input string format to an integer sequence compatible with
    :class:`redzed.TimeDate` and :class:`redzed.TimeSpan`.
  :param str|Sequence[str] sep:
    Non-empty string - often just one character - separating begin and end values
    in sub-intervals. Multiple alternatives can be given in a :abbr:`sequence (list or tuple of separator strings)`.
    The function will use the first one that is present in the string to be split.
  :param str|Sequence[str] delim:
    Separator or terminator that delimits sub-intervals.
    This argument has the same format as *sep*.
  :param Literal['date', 'time', 'datetime'] | None datatype:
    Optional hint about selected data type. If not :const:`None`,
    the result of *parser* is checked for correct sequence length.
    If *datatype* is ``'date'``, a single date is accepted as
    a one-day long interval that begins and ends on the same day.

  Parse a string representation of a time/date/timedate interval. Split the *interval*
  to sub-intervals (ranges) at each *delim* occurrence. Then split each range to
  its two endpoints separated by *sep*. Strip leading and trailing white-space
  and convert each endpoint with the *parser* function. Return the resulting data structure.

  Example::

    import datetime as dt
    from redzed.utils import parse_interval

    def _iso_to_int7(iso):
        datetime = dt.datetime.fromisoformat(iso)
        return [*datetime.timetuple()[:6], datetime.microsecond]

    # input (the trailing delimiter (;) is optional):
    sarg = "20260301T1200 / 20260307T183001.15; 2026-10-11T12:30 -- 2026-10-10T22;"
    # output will be:
    narg = [
        [[2026, 3, 1,12, 0,0,0], [2026, 3, 7,18,30,1, 150_000]],
        [[2026,10,11,12,30,0,0], [2026,10,10,22, 0,0,       0]],
        ]
    assert parse_interval(sarg, sep=["--", "/"], parser=_iso_to_int7) == narg

