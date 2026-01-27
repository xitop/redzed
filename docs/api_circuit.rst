.. currentmodule:: redzed

**--- INFORMATION FOR DEVELOPERS ---**

===========
Circuit API
===========


.. function:: get_circuit() -> Circuit

  Return the current circuit. Create one if it does not exist.
  Applications are supposed to build and run only one circuit.

.. function:: redzed.reset_circuit() -> None

  .. attention::

    Intended for usage in unit tests. Avoid in production code,
    because a perfect cleanup cannot be guaranteed.

  Clear the circuit data. The next :func:`get_circuit` call will
  return a new circuit. The circuit must not be running.
  :func:`!reset_circuit` does not modify the :ref:`debug level <Debug levels>`.

----

.. class:: CircuitState

  Circuit state symbols.

  These are integer enums. Their value may only increase during
  the circuit's life-cycle. Listed in order from the initial state
  (smallest value) to the final state (highest value):

  .. attribute:: UNDER_CONSTRUCTION

    The circuit is being built, :ref:`the runner <Circuit runner>` hasn't been started yet.

  .. attribute:: INIT_CIRCUIT

    The runner was started and initializes itself. No circuit modification
    is allowed from this moment.

  .. attribute:: INIT_BLOCKS

    The runner is now initializing blocks and triggers.

  .. attribute:: RUNNING

    Normal operation. The circuit is running.

  .. attribute:: SHUTDOWN

    Shutting down.

  .. attribute:: CLOSED

    The runner has exited. It cannot be restarted.

----

.. class:: Circuit()

  The logic of an automated system is described by a circuit. The :class:`!Circuit` class
  represents it. A new circuit is empty. Each created component is automatically
  added to it. When the circuit is completed, the automated system can be run.

  .. important::

    The :class:`!Circuit` class should not be instantiated directly;
    always call :func:`get_circuit`.

  Sections:
    - :ref:`1. Circuit components`
    - :ref:`2. Circuit state`
    - :ref:`3. Persistent storage`
    - :ref:`4. The runner`


1. Circuit components
---------------------

.. method:: Circuit.get_items(btype: type[Block|Formula|Trigger]) -> Iterable

  Return an iterable of circuit components of selected type *btype*
  with derived subtypes included.

  The returned iterable might be a generator. Convert the result
  to e.g. a list if necessary for storage or further processing.

.. method:: Circuit.resolve_name(ref: Block|Formula|str) -> Block|Formula

  Resolve a reference by name if necessary.

  If *ref* is a string, find and return circuit's block or formula with
  that name. Raise a :exc:`!KeyError` when not found.

  Return *ref* unchanged if it is already a valid :class:`!Block`
  or :class:`!Formula` object.

.. method:: Circuit.rz_add_item(item: Block|Formula|Trigger) -> None

  Add a circuit component.

  All components register themselves automatically when created.
  You shouldn't need to call this method.


2. Circuit state
----------------

.. method:: Circuit.get_state() -> CircuitState:

  Return the current :class:`CircuitState`.

.. method:: Circuit.reached_state(state: CircuitState) -> bool
  :async:

  Synchronization tool.

  Wait until the desired circuit *state* is reached. Because the exact *state*
  may have been skipped due to an error, :meth:`!reached_state` returns
  also when a subsequent state is reached. The return value is :const:`True`
  only when the desired state has been reached exactly.
  See :class:`CircuitState` for an ordered list of known states.

.. method:: Circuit.shutdown() -> None

  Stop the runner if it was started.
  Prevent the runner from starting if it wasn't started yet.

.. method:: Circuit.abort(exc: Exception) -> None

  Abort the circuit runner due to an exception.
  Prevent the runner from starting if it wasn't started yet.

  Calling :meth:`!abort` is necessary only when an exception wouldn't
  be propagated to the runner. If unsure, do call.

  :meth:`!abort` may be called multiple times. The first call start
  a shutdown. When :func:`run` exits after the shutdown, it raises
  exceptions from all :meth:`!abort` calls in an :exc:`!ExceptionGroup`
  with duplicates removed.


3. Persistent storage
---------------------

.. method:: Circuit.set_persistent_storage(persistent_dict, *, sync_time=None) -> None

  Setup the :ref:`persistent state <Persistent state>` data storage.
  This must be done before the runner is started.
  Of course, the same storage must be used each time.

  :param MutableMapping[str, Any] | None persistent_dict:
    The *persistent_dict* argument should be a dictionary-like object backed by
    a disk file or similar non-volatile storage. It may be also
    :const:`!None` to leave the feature disabled.

  :param None | float | str sync_time:
    The frequency of checkpointing for blocks that have opted-in
    with ``checkpoints='interval'`` argument given to their :class:`RestoreState`
    initializer. Checkpointing synchronizes the *persistent_dict*
    with the in-memory states every *sync_time* seconds.
    Default is 250 seconds (slightly more than four minutes).
    An argument other than :const:`!None` overrides this default.

  The *persistent_dict* must be ready to use. If it needs to be closed
  after use, the application is responsible for that.

  The Python standard library offers the `shelve module [↗] <https://docs.python.org/3/library/shelve.html>`_
  and the corresponding documentation mentions another helpful
  `recipe [↗] <https://code.activestate.com/recipes/576642-persistent-dict-with-multiple-standard-file-format/>`_.

.. method:: Circuit.save_persistent_state(blk: Block) -> None

  Save the internal state of *blk* to the persistent storage.
  Application code rarely needs this function, because the state
  is saved automatically.

  This is a low-level save function. The caller has to check
  that the :data:`Block.rz_persistence` flag is set before saving.

  Errors during saving are logged, but suppressed.


4. The runner
-------------

Always use the :func:`run` entry point to run the circuit!

.. method:: Circuit.runtime() -> float

  Return seconds since runner's start or 0.0 if it hasn't started yet.
  This time is displayed in log messages in :ref:`debug level <Debug levels>` 3.

.. method:: Circuit.create_service(coro: Coroutine, immediate_start: bool = False, auto_cancel: bool = True, **task_kwargs) -> None

  Create a task providing some :ref:`service <Service tasks vs. supporting tasks>`
  to one or more circuit blocks. Usually a block creates the task it needs during
  the initialization or start. The task is then supposed to run until
  cancelled at shutdown.

  The task will run the coroutine *coro*. Extra arguments *task_kwargs*
  are passed to the :func:`!asyncio.create_task` function. It is recommended
  to give the task a name for better identification.

  By default, the coroutine will be called when the circuit successfully reaches
  the :data:`CircuitState.RUNNING` state. If *immediate_start* is true,
  the coroutine will be called asap.

  If *auto_cancel* is true (default), the task will be automatically
  cancelled during shutdown. Typically, only output blocks set *auto_cancel*
  to :const:`False` in order to be able to finish the output operations.

  The task will be monitored for an eventual failure. It may stop only when
  cancelled. All other kinds of termination will abort the circuit runner.
  Even a normal exit is treated as an error if it happens before shutdown.
