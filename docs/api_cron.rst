.. currentmodule:: redzed

**--- INFORMATION FOR DEVELOPERS ---**

================
Cron service API
================

This internal service allows execution of scheduled actions. It is named after
the traditional Unix daemon.

A client block instructs the cron at what times within a day it wants to
get activated. The client may update its schedule at any time.
The cron activates the client blocks in given times.


Cron clients
============

In order to use the cron service, a logical block must make
few preparations before it can send its schedule to the cron:

- Implement a callback that the cron will call at given times:

  .. method:: Block.rz_cron_event(now: datetime.time)

    A method called by cron with one argument, the current time.
    Only blocks with this method are able to use cron.

    :meth:`!Block.rz_cron_event` will be called according to a schedule,
    but may be called also at other times, most notably when
    the computer clock makes a jump like when the DST begins or ends.

- Get and save a reference to the cron object before using it
  for the first time. Choose either the UTC time or the local time::

    name = '_cron_utc' if utc else '_cron_local'
    cron = redzed.get_circuit().resolve_name(name)

A schedule is a :abbr:`collection (a list, tuple or set)` of times of day
when an activation from the cron is requested. The times are represented by Python's
`datetime.time [↗] <https://docs.python.org/3/library/datetime.html#time-objects>`_
objects.

.. important::

  Do not include any timezone information in the :class:`datetime.time` objects.
  The cron accepts only a so-called "naive" time objects. The timezone
  is always implied from cron's configuration.

Finally, use the saved reference to post the schedule to the cron::

  cron.set_schedule(self, schedule)

The called method is:

.. method:: Cron.set_schedule(self, blk: Block, times_of_day: Collection[datetime.time]) -> None:

  Replace any existing schedule for block *blk* with the new schedule *times_of_day*.
  Block's :meth:`Block.blk.rz_cron_event` will be called at given times regardless of date.

  Note that the :class:`Cron` class is not a public symbol.


Cron server
===========

This server has a form of a common :class:`Block` and is created automatically
on demand. There can exist two instances, one for the local time
and one for the :abbr:`UTC (Coordinated Universal Time)` time.
Their names are ``'_cron_local'`` and ``'_cron_utc'`` respectively.


Inspecting schedule
-------------------

The cron server block supports the ':ref:`_get_config`' monitoring event.
It returns the scheduling data for the whole circuit.


DST adjustments
---------------

The :abbr:`DST (Daylight Saving Time a.k.a. Summer time)` affects the local time
in many time zones, but not the UTC time. If you do not want any irregularities,
consider switching to the UTC zone.

- When the DST starts, the clock is moved forward
  and scheduled actions that would have been made in that time are skipped.

- When the DST ends, the clock is rolled back and actions scheduled for that time
  are executed twice. To mitigate, client blocks may check the
  `datetime.time.fold [↗] <https://docs.python.org/3/library/datetime.html#datetime.time.fold>`_
  attribute of the *now* argument.

- As with every detected clock time jump, *all* cron client blocks get
  an unscheduled :meth:`Block.rz_cron_event` call.
