.. currentmodule:: redzed

==================
Block Initializers
==================


Initialization process
======================

By definition, a block is initialized when its output is not :const:`UNDEF`.
The output is closely related to the internal state, so block initialization basically
means internal state initialization.

During the initialization process, block's :ref:`initializers <Initializers>`
are tried until one of them succeeds. Initializers specified by the *initial* argument
are tried first and in given order, then the built-in default initializer
if it is defined. The circuit fails if any block remains uninitialized
after applying all initializers.


Initialization by an external event
-----------------------------------

This is a special case of initialization happening by coincidence.
When an event arrives to an uninitialized block, the block will first try
to initialize itself and then to handle the event. This event often
fully initializes the block. The exact procedure is:

1. call initializers specified by the *initial* argument
   *except* the async ones and *except* those already called
2. if still not initialized, call the built-in initializer
3. handle the event - initialized or not

Circuit ``Triggers`` are not activated yet during the initialization,
therefore an initialization event can come only from an external source
and if application's interface forwards it. The interface may be programmed not to
forward events to uninitialized blocks, but in general you don't want
to lose events.


Initializers
============

Initializers produce a value that is in turn used to initialize the block
which had the initializer included in its *initial* argument.
Failures (exceptions, timeouts, etc.) in individual initializers are logged,
but suppressed. An error occurs only when the whole initialization process fails
and the block's output remains undefined.

A block can have zero, one or more initializers.

- No initializers:
    This is the default. In most cases it is not sufficient.
    To specify no initializers, do not use *initial* at all or pass :const:`UNDEF`.

- One initializer:
    Enter the initializer as the *initial* argument::

      initial=<initializer>

    The most common case is initialization with a single fixed value.
    There is a shortcut for it. A value passed to *initial* that is not
    an initializer object is automatically wrapped into ``InitValue(value)``::

      initial=value   # shortcut for: initial=redzed.InitValue(value)

- Multiple initializers:
    Use a list or a tuple of initializers as the *initial* argument,
    the order matters. **Important**: at least one item must be
    an initializer object.::

      initial=[<initializer1>, <initializer2>, ...]

    The shortcut for fixed values mentioned above does apply in this case too::

      # single initializer:
      initial=[1, 2]              # shortcut applies to list [1, 2]
      initial=InitValue([1, 2])   # explicit equivalent

      # multiple initializers (at least one item is an initializer):
      initial=[RestoreState(), 2]             # shortcut applies to integer 2
      initial=[RestoreState(), InitValue(2)]  # explicit equivalent

.. warning::
  Initializers are not reusable::

    # correct
    redzed.Memory("ok1", initial=redzed.InitValue(0))
    redzed.Memory("ok2", initial=redzed.InitValue(0))
    # also correct
    redzed.Memory("ok3", initial=0)
    redzed.Memory("ok4", initial=0)

    # WRONG!
    init0 = redzed.InitValue(0)
    redzed.Memory("not_ok1", initial=init0)
    redzed.Memory("not_ok2", initial=init0)


Sync initializers
-----------------

.. class:: InitValue(value: Any)

  Initialize with a fixed value. This is the most common initializer.
  Block's *initial* argument allows you to enter just the value ``initial=value``
  instead of ``initial=redzed.InitValue(value)``.

  :class:`!InitValue` offers a fail-safe initialization, so it is usually used
  alone or as the last initializer following :class:`RestoreState` or async initializers.

.. class:: InitFunction(func: Callable[..., Any], *args: Any)

  Run *func* with arguments *args* and initialize with the return value.

.. class:: RestoreState(expiration=None, checkpoints=None)

  Restore the internal state that was saved to persistent storage during
  previous program run. The presence of :class:`!RestoreState` among block's
  initializers automatically enables saving of the internal state.

  The :class:`!RestoreState` initializer is applicable only
  to blocks that support :ref:`persistent state <Persistent state>`.

  :param None | float | str expiration:
    An *expiration* time may be specified in order to disregard stale data.
    The argument can be given as a number of seconds or as
    a :ref:`string with units <Time durations with units>`.
    The expiration time is measured since the last data save.

  :param None | Literal['event'] | Literal['interval'] checkpoints:
    This option enables :ref:`checkpointing <Checkpointing>`
    which is by default disabled.

    - When set to ``'event'``, the state is saved after each processed
      event (except monitoring events which do not alter the internal state).
    - When set to ``'interval'``, the state is periodically saved
      by a background service configured by :meth:`Circuit.set_persistent_storage`.

    Frequent checkpointing creates additional overhead. Choosing
    the optimal settings is a trade-off.

  This initializer differs from other initializers. Other initializers produce
  a single initialization value and the block builds a new internal state
  from that value. :class:`!RestoreState` directly restores the entire
  :ref:`internal state <Internal state and output>`
  and the state may contain more information than an initialization value alone.


Async initializers
------------------

Asynchronous initialization usually interacts with external systems and as such should
be utilized by circuit inputs only. This kind of initialization has a higher chance of being
unsuccessful. For reliability combine it with sync initializers like :class:`InitValue`;
there is an example at the bottom of this page.

.. class:: InitTask(aw_func: Callable[..., Awaitable], *args: Any, timeout: float|str = 10.0)

  Await an async function with arguments *args* in an async task with *timeout*.
  Initialize with the return value.
  In exact terms is *aw_func* a callable returning an awaitable.

  Argument *timeout* is a number of seconds or a
  :ref:`string with time units <Time durations with units>`. Default timeout is 10 seconds.

  .. important::

     If the block gets a successful initialization (by an external event)
     while :class:`!InitTask` is waiting for the task running *coro_func*,
     :class:`!InitTask` will immediately cancel its operation and won't
     overwrite the existing initialization.

.. class:: InitWait(timeout: float|str)

  Passively wait for an initialization, but not longer that the *timeout*.
  This initializer deliberately doesn't produce any value.
  The initialization could be a result of own activity or it could be
  caused by an :ref:`external event <Initialization by an external event>`.

  The mandatory argument *timeout* is a number of seconds or a
  :ref:`string with time units <Time durations with units>`.


Examples (initializers)
-----------------------

::

  redzed.Memory("example_1A",
      initial=redzed.InitValue(0))        # initial value is 0
  redzed.Memory("example_1B", initial=0)  # same as above, better readable


  # compare:
  redzed.Memory("timestamp_2A",
      # initial value = time of block creation; time.time() is called immediately
      initial=redzed.InitValue(time.time()))
  redzed.Memory("timestamp_2B",
      # initial value = time of block initialization; time.time() is called later
      initial=redzed.InitFunction(time.time))

  redzed.DataPoll(
      'RH', comment="relative humidity in %", func=read_humidity, interval=60,
      # 1. wait up to 3 seconds for data
      # 2. if not initialized, use the saved value if it is recent (2 hours max.)
      # 3. if still not initialized, use a default of 50 %
      initial=[redzed.InitWait(3), redzed.RestoreState("2h"), redzed.InitValue(50))
