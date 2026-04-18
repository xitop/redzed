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

    Intended for usage in unit tests. Do not use in production code,
    because a perfect cleanup cannot be guaranteed. Avoid resetting
    a running circuit if possible.

  Shut down the circuit runner if it is running. Clear the circuit data.
  The next :func:`get_circuit` call will return a new circuit.
  :func:`!reset_circuit` does not reset the :ref:`debug level <Debug levels>`.

----

.. class:: CircuitState

  Circuit state symbols.

  These are integer enums. Their value may only increase during the circuit runner's
  :ref:`life-cycle <Runner's life-cycle>`. Listed in order from the initial state
  (smallest value) to the final state (highest value):

  .. attribute:: UNDER_CONSTRUCTION

    The circuit is being built, :ref:`the runner <Circuit runner>` hasn't been started yet.

  .. attribute:: INIT_CIRCUIT

    The runner has been started and initializes itself. No circuit modification
    is allowed from this moment.

  .. attribute:: INIT_BLOCKS

    The runner is now initializing blocks and triggers. Blocks start to accept
    events.

  .. attribute:: RUNNING

    Normal operation. The circuit is running.

  .. attribute:: SHUTDOWN

    Shutting down. Triggers are deactivated. Blocks stop to accept events.

  .. attribute:: CLOSED

    The runner has terminated. It cannot be restarted.

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
  e.g. to a list if necessary for storage or further processing.

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

.. method:: Circuit.is_shut_down() -> bool:

  Check, if the circuit is no longer running.
  This simple helper returns :const:`True` if and only if
  the current state is :attr:`CircuitState.SHUTDOWN` or higher.

.. method:: Circuit.reached_state(state: CircuitState|str) -> bool
  :async:

  Synchronization tool. The *state* can be given as a :class:`CircuitState`
  enum member or as its name; e.g. ``redzed.CircuitState.RUNNING`` or just ``'RUNNING'``.

  Wait until the desired circuit *state* is reached. Because the exact *state*
  may have been skipped due to an error, :meth:`!reached_state` returns
  also when a subsequent state is reached. The return value is :const:`True`
  only when the desired state has been reached exactly.
  See :class:`CircuitState` for an ordered list of known states.

.. method:: Circuit.shutdown() -> None

  Stop the runner if it is running.
  Prevent the runner from starting if it hasn't been started yet.

.. method:: Circuit.abort(exc: Exception) -> None

  Abort the circuit runner due to an exception.
  Prevent the runner from starting if it hasn't been started yet.

  Calling :meth:`!abort` is necessary only when an exception wouldn't
  be propagated to the runner. If unsure, do call.

  :meth:`!abort` may be called multiple times. The first call starts
  a shutdown. When :func:`run` exits after the shutdown, it raises
  exceptions from all :meth:`!abort` calls in an :exc:`!ExceptionGroup`
  with duplicates removed.

.. method:: Circuit.get_errors() -> list[Exception]

   Return a list of exceptions collected by :meth:`Circuit.abort`.
   Do not modify the list.


3. Persistent storage
---------------------

.. method:: Circuit.set_persistent_storage(persistent_dict, *, save_interval=None, close_callback=None) -> None

  Setup the :ref:`persistent state <Persistent state>` data storage.
  This must be done before the runner is started.
  Of course, the same storage must be used each time.

  :param MutableMapping[str, object]|None persistent_dict:
    The *persistent_dict* argument should be a dictionary-like object backed by
    a disk file or similar non-volatile storage. It may be also
    :const:`None` to leave the feature disabled.

    Redzed provides :class:`redzed.utils.PersistentDict`.
    As an alternative, the Python standard library offers the
    `shelve module [↗] <https://docs.python.org/3/library/shelve.html>`_

  :param float|str|None save_interval:
    *save_interval* controls the frequency of checkpointing for blocks that have
    opted-in with :attr:`!SF_INTERVAL` option in their :class:`PersistentState`
    settings. Checkpointing saves the in-memory states of these blocks
    to *persistent_dict* every *save_interval* seconds.

    Default interval is 251 seconds (slightly more than four minutes).
    Any argument other than :const:`None` overrides this default.
    Shortest allowed interval is not set, but keep in mind that
    frequent checkpointing degrades the performance.

  :param Callable|None close_callback:
    Register a close/cleanup function if the storage has one.
    The function will be called without arguments when the storage
    is no longer in use by the circuit. Many storage types require this
    e.g. to flush buffers and close files. For an alternative method see the
    `atexit module [↗] <https://docs.python.org/3/library/atexit.html>`_

.. method:: Circuit.get_persistent_storage() -> Mapping[str, object]|None

  Return a *read-only* proxy of the persistent storage
  set by :meth:`Circuit.set_persistent_storage`.
  Return None if no storage is available.

.. class:: redzed.utils.PersistentDict(datafile, format=None, *, sync_time=10.0, error_callback=None)

  Create a dict-like object compatible with :meth:`Circuit.set_persistent_storage`.
  Populate it with data loaded from *datafile*.
  Save subsequent modifications back to the *datafile*.

  :param str|os.PathLike[str] datafile:
    File name of the data file. Always use an absolute path.
    The parent directory must be writable, because
    *datafile* is updated atomically using temporary files.

  :param Literal['json', 'pickle', None] format:
    Data serialization format. Supported are ``'json'`` and ``'pickle'``.

    The format can be explicitly set or derived from the file name.
    If the *format* option is unset (:const:`None`), the format is taken
    from the *datafile* suffix. Recognized are:
    ``'.pkl'``, ``'.pickle'`` and ``'.json'``. Using other
    suffixes requires an explicit *format* setting.

    - `[↗] JSON <https://docs.python.org/3/library/json.html>`_ produces
      human readable text files. JSON is a wide-spread standard.
      Its disadvantage is that only the very basic data types
      (None, booleans, numbers, strings) and structures (lists and dicts,
      possibly nested) are supported. The relation between Python
      and JSON types is not one-to-one; e.g. if you save a tuple,
      you will load a list.
    - `[↗] Pickle <https://docs.python.org/3/library/pickle.html>`_ produces
      binary files. It is fast and can handle a wide range of data types
      and structures. Unlike JSON, pickle is Python specific. Please,
      pay attention to the security warning (*"Only unpickle data you trust"*)
      on the linked web page.

    As a special case, an empty *datafile* (0 bytes) is always treated
    as it were containing an empty dict regardless of the *format*.

  :param float|str|None sync_time:
    :class:`!PersistentDict` modifications are normally cached for better performance.
    *sync_time* is maximum time in seconds between a dict modification and a file save.
    It can be given as a :ref:`string with time units <Time durations with units>` too.
    When set to zero, data is saved immediately without caching.

  :param Callable[[Exception], Any]|None error_callback:
    This parameter controls error handling. It takes an optional
    callable taking one argument. Every time an error occurs,
    the exception is logged, this function (if defined) is called with
    the exception as its sole argument and the :class:`!PersistentDict`
    code continues to run trying to recover from the error.
    The error recovery code may remove *datafile* that appears to be damaged.
    If that happens, :class:`!PersistentDict` attempts to preserve
    the offending *datafile* under modified name for a later inspection.

    If the primary concern is to keep the application running,
    no *error_callback* is needed ``(error_callback=None)``.
    This is the default setting. OTOH, if the persistent data are so important
    that errors are critical, use: ``error_callback=circuit.abort``.

    Note that an *error_callback* that does not permit the :exc:`FileNotFoundError`
    exception prevents the initial run on which the *datafile* would be used
    for the first time. In such case, create an empty file manually.

  .. method:: flush() -> None

    Flush the cache, i.e. write modifications to the file.

  Example of usage::

    storage = rz.utils.PersistentDict('/path/to/file.json')
    circuit.set_persistent_storage(storage, close_callback=storage.flush)

.. method:: Circuit.save_persistent_state(blk: Block) -> None

  Save the internal state of *blk* to the persistent storage.
  Application code rarely needs this function, because the state
  is saved automatically.

  This is a low-level save function. The caller must check
  the :attr:`Block.rz_save_flags` value before saving.
  Errors during saving are logged, but suppressed.


4. The runner
-------------

Always use the :func:`run` entry point to run the circuit!

.. method:: Circuit.runtime() -> float

  Return seconds since runner's start or 0.0 if it hasn't started yet.
  This time is displayed in log messages in :ref:`debug level <Debug levels>` 3.

.. method:: Circuit.create_service(coro: Coroutine, start_state: CircuitState = CircuitState.RUNNING, auto_cancel: bool = True, **task_kwargs) -> None

  Create a task providing some :ref:`service <Service tasks vs. supporting tasks>`
  to one or more circuit blocks. Usually a block creates the task it needs during
  the initialization or start. The task is then supposed to run until
  cancelled at shutdown.

  The task will run the coroutine *coro*. Extra arguments *task_kwargs*
  are passed to the :func:`!asyncio.create_task` function. It is recommended
  to give the task a name for better identification.

  The coroutine will be called when the circuit successfully reaches
  the *start_state* which defaults to :attr:`CircuitState.RUNNING`.
  This is also the highest allowed *start_state*, because it is
  followed by shutdown.

  If *auto_cancel* is true (default), the task will be automatically
  cancelled during shutdown. Typically, only output blocks set *auto_cancel*
  to :const:`False` in order to be able to finish the output operations.

  The task will be monitored for an eventual failure. It may stop only when
  cancelled. All other kinds of termination will abort the circuit runner.
  Even a normal exit is treated as an error if it happens before shutdown.
