.. currentmodule:: redzed

================
Auxiliary blocks
================

**Conventions used in this chapter:**

- Only block specific parameters are documented here.

- Class signatures may be syntactically incorrect
  for the sake of comprehensibility.

- All time duration values (timeouts, intervals, etc.) can be given as a number
  of seconds or as a :ref:`string with time units<Time durations with units>`.


.. class:: Counter(name, *, modulo=None, initial=..., **block_kwargs)

  A counter. Its output is the current count (integer).

  :param int|None modulo:
    If set, count modulo M. For a positive integer M it means to count only
    from 0 to M-1 and then wrap around. If *modulo* is not set,
    the output value is not bounded.

  :param initial:
    Initial value, 0 by default

  Events:
    All events return the updated output value.

    - **'inc'**
       Increment (count up) by 1 or by the value of ``'evalue'`` data item
       if such item is present in the event data::

         counter.event('inc')     # increment by 1
         counter.event('inc', 3)  # increment by 3

    - **'dec'**
       Decrement (count down) the counter by 1 or by ``'evalue'``.
    - **'put'**
       Set the :class:`!Counter` to ``'evalue'`` data item (mod M).

  :class:`!Counter` supports persistent state.


.. class:: Repeat(name, *, dest, interval, count = None, **block_kwargs)

  Periodically repeat the last received event.

  :param redzed.Block | str dest:
    destination block, an instance or its name
  :param float | str interval:
    default time interval between repetitions; can be overridden per event
  :param int | None count:
    optional limit for repetition count, the original event is not counted.
    This limit can be overridden as well.

  :class:`!Repeat` is intended to repeat events destined to an output block.
  Its purpose is to minimize the chance that some connected device will fail to act
  due to transient problems. The key requirement is that repeating must not
  change the outcome, i.e. multiple invocations must have the same effect
  as a single invocation. Such actions are called *idempotent*.

  Any received event is first immediately forwarded to the destination block
  specified by *dest* and then duplicates are sent in time intervals specified
  by *interval*. The number of repetitions may be limited with *count*.
  If not :const:`None`, the repeating stops after *count* duplicates sent.
  The original event is always re-sent and not counted. When another
  event arrives, :class:`!Repeat` stops repeating the old event
  and starts over with the new one.

  A :class:`!Repeat` block adds a ``'repeat'`` count value to the
  event data. The original event is sent with ``'repeat': 0`` and
  subsequent repetitions are sent with ``'repeat': N`` where N is 1, 2, 3, ...
  This repeat value is also copied to the output, the initial output is 0.

  **Overriding interval and count**

  An event may include items ``'repeat_interval'`` and ``'repeat_count'`` with values
  overriding the defaults set by arguments *interval* and *count*.
  The interval must be a number (float). Strings with units are not accepted here.
  These event data items will be removed from the event data before forwarding
  the event to *dest*.

.. class:: Timer(name, *, restartable=True, **fsm_kwargs, **block_kwargs)

  This is an FSM block. The output is :const:`False` in state ``'off'`` for time
  duration *t_off*, then :const:`True` in state ``'on'`` for duration *t_on*,
  and then the cycle repeats.

  By default both durations are infinite (timer disabled), i.e. the
  block is bistable. If one duration is set, the block is monostable.
  If both durations are set, the block is astable.

  Setting any duration to 0.0 is discouraged. It is accepted for one of the states,
  but not for both. The corresponding state will be entered for a brief moment just
  due to the overhead.

  :param bool restartable:
    If :const:`True` (default), a ``'start'`` event
    occurring while in the ``'on'`` state restarts the timer
    to measure the ``'t_on'`` time from the beginning. If not
    restartable, the timer will continue to measure the
    time and ignore the event. The same holds for the ``'stop'``
    event in the ``'off'`` state.

  :class:`!Timer` accepts all standard :ref:`FSM parameters`
  (shown as *\*\*fsm_kwargs*) and a *t_period* added for convenience:

  :param t_on:
    ``'on'`` state timer duration
  :param t_off:
    ``'off'`` state timer duration
  :param t_period:
    ``t_period=T`` is a shortcut for setting ``t_on = t_off = T/2``,
    i.e. to create a clock signal generator with the period ``T``
    (plus some small overhead) and a duty cycle of 50%.
    Arguments *t_period* and *t_on*, *t_off* are mutually exclusive.
  :param initial:
    Set the initial state. Default is ``'off'``.
    Use ``initial='on'`` to start in the ``'on'`` state.

  Events:
    - **'start'**
        Go to the ``'on'`` state. See also: *restartable*.
    - **'stop'**
        Go to the ``'off'`` state. See also: *restartable*.
    - **'toggle'**
        Go from ``'on'`` to ``'off'`` or vice versa.
