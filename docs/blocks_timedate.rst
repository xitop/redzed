.. currentmodule:: redzed

=======================
Time and date intervals
=======================

**Conventions used in this chapter:**

Only block specific parameters are documented here.
Class signatures may be syntactically incorrect
for the sake of comprehensibility.



Specifying intervals
====================

Redzed supports intervals of three types:

- times of day (periodically recurring),
- dates within a year (periodically recurring),
- complete dates with time (not recurring).

A full interval is a sequence of ranges (sub-intervals). A range is defined by
its two endpoints: begin and end, i.e. it is again a sequence of two values.
Each endpoint is a sequence of integers defining date/time. In Python,
a sequence is almost always either a list or a tuple.


Range endpoints
---------------

- time of day (e.g. ``[6, 45, 0]`` for 6:45:00 morning)

  A time is defined by ``(hour, minute, second=0, microsecond=0)``, i.e. a sequence
  of two to four integers. 24-hour clock is used. The optional values default to zero.
  Note that a microsecond precision cannot be expected.

- date (without a year, e.g. ``[12, 21]`` for the 21st of December - a typical solstice date)

  Exactly two integers specify a date: ``(month, date)``

- date+time (e.g. ``[2025, 10, 20, 6, 45]`` October 20, 2025 at 6:45 a.m.)

  Seven integers define a full date and time. The last two values are optional
  and default to zero: ``(year, month, date, hour, minute, second=0, microsecond=0)``


Ranges (sub-intervals) and intervals
------------------------------------

An **interval** contains any number of ranges (sub-intervals).

Each **range** is defined by its two :ref:`endpoints <Range endpoints>` and contains
moments between the beginning and the end:

- date intervals are closed: ``begin <= interval duration <= end``
- time intervals (with or without date) are right-open: ``begin <= interval duration < end``

Examples:

- time range ``[[5, 0], [7, 30]]`` - from five o'clock (incl.) to half past seven (excl.); every morning
- date range ``[[2, 3], [2, 4]]`` - two days in February - the 3rd and 4th; every year

When the end is before the begin, periodic events retain their usual meaning:

- time range ``[[22, 0], [0, 30]]`` - means from 22:00 to 00:30 next day
  (duration 2 hours and 30 minutes)
- date range ``[[12, 10], [1, 15]]`` - means from the 10th of December up to and including
  the 15th of January that follows.


Summary
-------

The type names are for illustration only.

::

  Date_Time_Type = Sequence[int]
  # accepted sequence length: time = 2..4, date = 2, datetime = 5..7
  # exported sequence length: time =    4, date = 2, datetime =    7

  Date_Time_Range_Type = Sequence[Date_Time_Type]
  # sequence length = exactly two: [start, end]

  Date_Time_Interval_Type = Sequence[Date_Time_Range_Type]
  # sequence length = any (zero, one or more)



Interval as strings
-------------------

If you prefer to write intervals as strings, there is a
:ref:`conversion utility <Date/time intervals as strings>`.


Periodic events
===============

.. class:: TimeDate(name, *, utc: bool = False, initial=..., **block_kwargs)

  A block for periodic events occurring daily, weekly or yearly. A combination
  of conditions is possible like in the example. More complicated setups
  can be achieved with several :class:`!TimeDate` blocks combined using a custom
  trigger or a formula.

  If *utc* is :const:`False` (which is the default), times are in the local timezone.
  If *utc* is :const:`True`, times are in UTC.

  Example - every Monday morning 6:30 to 9 a.m., but only in April and July::

    example_cfg = {
      'times': [
        [[6, 30], [9, 0]],  # 6:30 to 9:00
      ],
      'dates': [
        [[4, 1], [4, 30]],  # April 1 to 30
        [[7, 1], [7, 31]],  # July 1 to 31
      ],
      'weekdays': [1],      # Monday
    }
    redzed.TimeDate("example", initial=example_cfg)

  This block is configured by an initial value of type dict (``Mapping[str, None | Sequence]``)
  with items named ``'times'``, ``'dates'`` and ``'weekdays'``.

  - *config['times']* - optional :ref:`time interval<Ranges (sub-intervals) and intervals>`
  - *config['dates']* - optional :ref:`date interval<Ranges (sub-intervals) and intervals>`.
  - *config['weekdays']* - optional list of weekday numbers
      0=Sunday, 1=Monday, ... 5=Friday, 6=Saturday, 7=Sunday (same as 0)

  All three items are optional, but at least one item not equal to :const:`None` must be given.
  The output is a boolean and it's :const:`True` only when the current time, date and the weekday
  match the specified values. Unused values - missing or set to :const:`None` - are not taken into
  account.

  The initial argument is optional. The default configuration is a void interval
  resulting in constant :const:`False` on output.

  .. note::

    Unused arguments *times*, *dates*, or *weekdays* are given as :const:`None`.
    This is different than an empty sequence.

    - :const:`None` means we don't care which time, date or weekday respectively.

    - An empty value is a valid argument meaning no matching time or date or weekday.
      A :class:`!TimeDate` block with an empty sequence in the configuration always outputs
      :const:`False`.

  .. note::

    The weekday numbers in the standard library:

    - compatible with Redzed:

      - :func:`time.strftime` (directive ``'%w'``): 0 (Sunday) to 6 (Saturday)
      - :meth:`datetime.date.isoweekday`: 1 (Monday) to 7 (Sunday)

    - not compatible with Redzed (add/subtract 1 to adjust):

      - :meth:`datetime.date.weekday` and :data:`time.struct_time.wday`: 0 (Monday) to 6 (Sunday)

Non-periodic events
===================

.. class:: TimeSpan(name, *, utc: bool = False, initial=..., **block_kwargs)

  Block for non-periodic events occurring in ranges between begin
  and end defined with :ref:`full date and time<Range endpoints>`.
  Any number of ranges may be specified, including zero.

  If *utc* is :const:`False` (which is the default), times are in the local timezone.
  If *utc* is :const:`True`, times are in UTC.

  The output is a boolean and it is :const:`True` when the current time and date are inside
  of any of the ranges.

  The initial argument is a :ref:`date+time interval <Specifying intervals>`. It is
  optional. The default configuration is an empty sequence resulting in constant :const:`False`
  on output.

  Example::

    span=[
      [[2025,  3,  1, 12,  0],    [2025,  3,  7, 18, 30]   ],
      [[2025, 10, 10, 10, 30, 0], [2025, 10, 10, 22,  0, 0]],
      ]
    redzed.TimeSpan("TS", comment="another example", initial=span)


Dynamic updates
===============

Both :class:`TimeDate` and :class:`TimeSpan` blocks can be reconfigured during a circuit
run by a ``'reconfig'`` event. Pass the new configuration as the event data item 'evalue'.
The new configuration has exactly the same format and meaning as the block's initialization
value. For example::

  # new_config is a dict for a TimeDate and a sequence for a TimeSpan block.
  timeblock.event('reconfig', new_config)

Upon receipt of a ``'reconfig'`` event, the block discards the old settings.
and replaces them with the new values.

The *utc* value is fixed and cannot be changed.

The internal state is equal to the current configuration. It can be obtained
with the :meth:`Block.rz_export_state()` method or with the ':ref:`_get_state`'
monitoring event. The ':ref:`_get_config`' event returns the same data.

Both blocks support :ref:`state persistence <Persistent state>`.
It is only useful with dynamic updates, that's why it is documented here.


Cron service
============

Blocks :class:`TimeDate` and :class:`TimeSpan` are implemented as clients
of the :ref:`cron <Cron server>` internal service. Additional information,
e.g. about DST handling, is contained there.
