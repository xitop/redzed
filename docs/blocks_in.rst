.. currentmodule:: redzed

======
Inputs
======

**Conventions used in this chapter:**

- Only block specific parameters are documented here.
  Parameters like *initial*, *stop_timeout* are documented in the :ref:`Block API`.

- Class signatures may be syntactically incorrect
  for the sake of comprehensibility.

- All time duration values (timeouts, intervals, etc.) can be given as a number
  of seconds or as a :ref:`string with time units<Time durations with units>`.


Data validation
---------------

Input blocks can validate data using a validator. It is a function specified
with the *validator* argument. It takes one argument, the incoming data.
The validator either accepts the input data by returning it or rejects it by raising
an exception. The returned data may be modified (pre-processed).

Data validation is optional, but strongly recommended especially for inputs processing
data from external sources.


Pushing data into the circuit
-----------------------------

Data are transported by events. Depending on your application's needs,
almost any logic block may serve as a part of the circuit's input interface.
The most common data entry block is :class:`!Memory`.


.. class:: Memory(name, *, validator=None, initial=..., **block_kwargs)

  A memory cell with optional value validation.
  Usage: ``memory.event('store', value)``

  :param validator: Optional :ref:`data validator <Data validation>`.
  :type validator: Callable[[Any], Any] | None

  Block's output equals the stored value. A new value is stored with
  a ``'store'`` event. This event stores and outputs the event data item  ``'evalue'``
  provided that it validates successfully. The event returns :const:`True`
  if the new value is accepted, :const:`False` otherwise.

  :class:`!Memory` supports persistent state. The last known value can
  be thus restored on the following start.

.. class:: MemoryExp(name, *, duration, expired=None, **memory_kwargs)

  Like :class:`Memory`, but after certain time after the ``'store'`` event
  replace the current value with the *expired* value. The value expiration
  can be forced at any time by sending an ``'expire'`` event.

  An :class:`!MemoryExp` takes the same arguments as :class:`Memory`
  plus two additional ones:

  :param float | str | None duration:
    The default duration in seconds before a value expires.
    The duration can be overridden on a per-event basis.
    Enter :const:`None` for no default duration. Without a default,
    every event must explicitly specify the duration.

  :param Any expired:
    A value to be applied after expiration. Make sure it passes the validator.

  If a ``'duration'`` item (with the same format as the *duration* parameter)
  is present in the event data, it overrides the default duration.


Polling data sources
--------------------

A specialized block is provided for this task:

.. class:: DataPoll(name, *, func, interval, retry_interval=None, validator=None, abort_after_failures=0, **block_kwargs)

  A source of measured or computed values. :class:`!DataPoll` outputs the result of an acquisition
  function *func* every *interval* seconds.

  :param Callable[[], Any] func:
    The data acquisition function. It could be a :abbr:`regular function (defined with def)`
    or an :abbr:`coroutine function (defined with async def)`.
    It is called without arguments and must return either the next value
    or :const:`UNDEF` to indicate a failed attempt and a missing value.

    When a value is missing, the output is not updated, the *retry_interval*
    overrides the regular *interval* and the counter of failures is incremented.

  :param validator: Optional :ref:`data validator <Data validation>`.
  :type validator: Callable[[Any], Any] | None

  :param float | str interval:
    The sleep time between function calls. Any overhead represents an additional delay.
    Only if the *func* is async, the time spent in ``await func()`` is measured
    and the sleep time is shortened accordingly.

  :param float | str | None retry_interval:
    [part 1/2 - fixed value] - Optional *interval* value to be used after a failed attempt.
    When *retry_interval* is :const:`None` (default), the regular *interval* value
    will be used.

  :param float | str | None retry_interval:
    [part 2/2 - exponential backoff] - A sequence of exactly two values - ``T_min`` and ``T_max``,
    both (*float | str*) - enables a so-called exponential backoff. The first retry
    interval is ``T_min``. The interval doubles every time until it reaches the ceiling
    ``T_max``. A successful data acquisition resets the retry interval back to ``T_min``.
    ``T_max`` must be at least twice as long as ``T_min``.

  :param int abort_after_failures:
    Optional safeguard, disabled by default. Abort the circuit after this many
    failed consecutive attempts to get the next value. Value 0 disables this feature.

  :param bool output_counter:
    see also the standard :ref:`output_counter <2. Output>` parameter.

  **Initialization:**
    :class:`!DataPoll` initializes itself automatically if the acquisition
    function *func* immediately delivers a result (i.e. not an :const:`UNDEF`)
    on its first call. Initializers specified by the *initial* parameter
    are used only if the first *func* call does not succeed to initialize
    the block immediately:

    - :class:`InitWait` gives the :class:`!DataPoll` block time to
      acquire its first value.
    - :class:`!DataPoll` supports persistent state. The last known value can
      be thus restored on the following start. Use :class:`RestoreState` for that.
    - You might want to use :class:`InitValue` with a default value
      as the last initializer.

    See also: the :ref:`initializer example <Examples (initializers)>`.
