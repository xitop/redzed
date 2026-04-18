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
Sometimes there exists a brief time window during initialization when an event
may be delivered to an uninitialized block.

This is an advanced topic covered :ref:`here <Issue 1: destination block is not initialized>`.
Summary: Redzed will do its best to handle the event.


Initializers
============

Initializers produce a value that is in turn used to initialize the block
which had the initializer included in its *initial* argument.
Failures (exceptions, timeouts, etc.) in individual initializers are logged,
but suppressed. An error occurs only when the whole initialization process fails
and the block's output remains not initialized.

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
      initial=[PersistentState(), 2]             # shortcut applies to integer 2
      initial=[PersistentState(), InitValue(2)]  # explicit equivalent

Initializers are reusable::

    # caution: in older beta releases this was not allowed
    import redzed as rz

    init0 = rz.InitValue(0)
    rz.Memory("ok1", initial=init0)
    rz.Memory("ok2", initial=init0)


Sync initializers
-----------------

.. class:: InitValue(value: object)

  Initialize with a fixed value.

  This is the most common initializer. For brevity, Block's *initial* argument
  allows to enter just the value ``initial=value`` instead of
  ``initial=redzed.InitValue(value)``.

  :class:`!InitValue` offers a fail-safe initialization, so it is usually used
  alone or as the last initializer following :class:`PersistentState` or async initializers.

.. class:: InitFunction(func: Callable[..., object], *args: object)

  Run *func* with arguments *args* and initialize with the return value
  unless it is :const:`UNDEF`. When the returned value is :const:`UNDEF`,
  the initialization continues with the next initializer.

.. class:: PersistentState(expiration=None, save_flags=None)

  Restore the internal state that was saved to persistent storage during
  previous program run.

  .. important::

    This initializer is special. Other initializers produce
    a single initialization value and the block builds a new internal state
    from that value. :class:`!PersistentState` directly restores the entire
    :ref:`internal state <Internal state and output>`.

  The :class:`!PersistentState` initializer is applicable only
  to blocks that support :ref:`persistent state <Persistent state>`.
  The presence of :class:`!PersistentState` among block's
  initializers automatically enables saving of the internal state.

  :param float|str|None expiration:
    An *expiration* time may be specified in order to disregard stale data
    when restoring the state. The argument can be given as a number of seconds
    or as a :ref:`string with time units <Time durations with units>`.
    The expiration time is measured since the last data save.

  :param SaveFlags|None save_flags:
    This parameter controls when exactly is block's internal state saved
    to persistent storage for :ref:`checkpointing <Checkpointing>` purposes.
    The default and recommended setting :const:`None` configures checkpointing
    automatically.

    Valid flags are listed below. Multiple flags may be given OR-ed together (bit-wise).
    Frequent checkpointing creates additional overhead and choosing the optimal
    settings is a trade-off. In this regard, the combination ``SF_EVENT | SF_OUTPUT``
    is often unfavorable. Consider using one or the other.

    - :attr:`SF_NONE`
        No checkpointing.
    - :attr:`SF_EVENT`
        Save state after each processed event except
        :ref:`monitoring events <Monitoring events>` which do not
        alter the internal state.
    - :attr:`SF_OUTPUT`
        Save state after each output change.
    - :attr:`SF_INTERVAL`
        Save state periodically by a background service
        configured with :meth:`Circuit.set_persistent_storage`.

    **Default settings:**

    Without explicitly given *save_flags*, following settings
    will be applied:

    - Depending on :attr:`Block.RZ_STATE_IS_OUTPUT`:

      - blocks :class:`Memory`, :class:`Counter`, :class:`DataPoll` and similar
        will use :attr:`SF_OUTPUT`
      - other blocks will use :attr:`SF_EVENT`

    - If *expiration* is set, :attr:`SF_INTERVAL` will be added to keep
      timestamps updated


Async initializers
------------------

Asynchronous initialization usually interacts with external systems and as such should
be utilized by circuit inputs only. This kind of initialization has a higher chance of being
unsuccessful. For reliability combine it with sync initializers like :class:`InitValue`;
there is an example at the bottom of this page.

.. class:: InitTask(aw_func: Callable[..., Awaitable], *args: object, timeout: float|str = 10.0)

  Create an awaitable by calling *aw_func* with arguments *args*
  and await it in an async task with *timeout*.
  Initialize with the return value unless it is :const:`UNDEF`. When the returned
  value is :const:`UNDEF`, the initialization continues with the next initializer.

  Argument *timeout* is a number of seconds or a
  :ref:`string with time units <Time durations with units>`. Default timeout is 10 seconds.

  .. important::

    If the block gets a successful initialization (by an external event)
    while :class:`!InitTask` is waiting for the task running *aw_func*,
    :class:`!InitTask` will immediately cancel its operation and won't
    overwrite the existing initialization. In other words, the first
    received value wins.

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

  import redzed as rz

  rz.Memory("example_1A", initial=rz.InitValue(0))  # initial value is 0
  rz.Memory("example_1B", initial=0)      # same as above, better readable


  # compare:
  rz.Memory("timestamp_2A", initial=rz.InitValue(time.time()))
  # initial value = time of block creation; time.time() is called immediately

  rz.Memory("timestamp_2B", initial=rz.InitFunction(time.time))
  # initial value = time of block initialization; time.time() is called later

  rz.DataPoll(
      'RH', comment="relative humidity in %", func=read_humidity, interval=60,
      # 1. wait up to 3 seconds for data
      # 2. if not initialized, use the saved value if it is recent (2 hours max.)
      # 3. if still not initialized, use a default of 50 %
      initial=[rz.InitWait(3), rz.PersistentState("2h"), 50)
