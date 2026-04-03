.. currentmodule:: redzed

.. role:: strike
  :class: strike

**--- INFORMATION FOR DEVELOPERS ---**

=========
Block API
=========

.. class:: Block(name, *, comment: str="", initial=redzed.UNDEF, stop_timeout=None, always_trigger=False, **x_kwargs)

  Base class of all logic blocks. A :class:`Block` has no function by itself
  and cannot be instantiated.

  .. attention::
    :class: note

    If you are not creating a new type of logic blocks,
    you can ignore all :meth:`!rz_methods` and :attr:`!rz_attributes`.
    Symbols starting with a ``rz_`` or ``RZ_`` prefix
    are reserved for interactions with the circuit runner.

  Sections:
    - :ref:`1. Name and comment`
    - :ref:`2. Output`
    - :ref:`3. Circuit membership`
    - :ref:`4. Setup and start`
    - :ref:`5. Persistent state`
    - :ref:`6. Shutdown and cleanup`
    - :ref:`7. Event handling`
    - :ref:`8. Logging functions`
    - :ref:`9. Application data`


1. Name and comment
===================

For a description visit :ref:`setting the name <Setting the name>`.

**Parameters:**

  **name** (str)
    A name uniquely identifying the block.

  **comment** (str)
    An optional comment, by default an empty string.

**Attributes:**

  .. attribute:: Block.name
    :type: str

    The assigned name. Do not modify.

  .. attribute:: Block.comment
    :type: str

    The assigned comment. Do not modify.


2. Output
=========

.. data:: UNDEF

  :const:`!UNDEF` is a sentinel value for an uninitialized (i.e. undefined)
  state or output. It is an error when a block outputs :const:`UNDEF` after
  the circuit initialization. All other output values are valid, including
  :const:`None`.

  It is also used as a placeholder for a missing value, an unused option, etc.
  mainly when :const:`None` cannot be used as a sentinel.

  :const:`!UNDEF` is a singleton, its boolean value is :const:`False`
  and its string representation is ``"<UNDEF>"``.


**Parameters:**

  **always_trigger** (bool)
    When :const:`False`, activate connected triggers only when the output changes.
    This is the default. When :const:`True`, activate the triggers every time
    a value is output. Set this option if you want to activate directly connected
    triggers for each value in a series of same values.

.. method:: Block.is_initialized() -> bool

  Check if the output differs from :const:`UNDEF`, i.e. if the block has been initialized.

.. method:: Block.get(*, with_previous: bool = False) -> object

  - when *with_previous* is :const:`False` (default):
      Get the current output value. Return :const:`UNDEF` if the block
      hasn't been initialized yet.
  - when *with_previous* is :const:`True`:
      Return a tuple ``(current_output, previous_output)``. The previous
      output is :const:`UNDEF` if the block did not have two values
      (current and previous) yet.

.. function:: redzed.get_output(name: str, with_previous: bool = False) -> object

  Get the output value(s) of a block (or formula) given by its *name*.

  Roughly equivalent to ``redzed.get_circuit().resolve_name(name).get(...)``.

.. method:: Block._set_output(output: object) -> bool

  Set the output value. It is not allowed to output :const:`UNDEF`.

  Return :const:`True` if the output has changed or if the *always_trigger*
  option was set. In these cases, the output value is saved as previous value,
  the new *value* becomes the current output, dependent formulas
  are recalculated and subsequently all affected triggers are activated.

  Return :const:`False` if the output value is the same
  as before and no circuit activity was initiated.

  If you override :meth:`!Block._set_output` in a subclass, please don't forget to return
  a proper value; in most cases: ``return super()._set_output(modified_output)``.


3. Circuit membership
=====================

.. attribute:: Block.circuit
  :type: Circuit

  A link to the circuit the logic block belongs to. Every block is automatically
  registered as a component of the current circuit. This reference provides access to
  circuit's functions.


4. Setup and start
==================

The output of just created blocks is set to :const:`UNDEF` sentinel.
The initialization process must replace :const:`UNDEF` with some other value.
When this happens the initialization process stops as completed.

**Parameters:**

  **initial** - block initializer(s), the default is no initializers
    The parameter *initial* is accepted only if :meth:`rz_init` is implemented.
    Otherwise it must not be used.
    A detailed description can be found :ref:`here <Initializers>`.

Following methods are listed in order they are invoked by the circuit runner.
Every logic block implements only those :meth:`!rz_methods()` that it needs
for its functionality.

.. method:: Block.rz_pre_init() -> None

  Optional. Set up necessary resources that could not be prepared in ``__init__()``.

  If implemented, it is called once before initialization. It is typically used for
  resolving block names with :meth:`Circuit.resolve_name`. Using names allows to reference blocks
  that are defined later in the code. Do not set the internal state or the output here.

.. method:: Block.rz_init(init_value: object, /) -> None

  Optional. Initialize the block's state and output based on the *init_value*.

  If implemented, the block initializers (specified by the *initial* argument)
  call this method in order they were given as long as the output equals :const:`UNDEF`.

  .. warning::

    When implementing :meth:`!rz_init`, do not call :meth:`event` to do the
    initialization. When an uninitialized block receives an event, it
    tries to initialize itself before handling it. However, you may call
    an event handler :meth:`!self._event_ETYPE()` directly.

.. method:: Block.rz_init_default() -> None

  Optional. Initialize the block's state with a built-in default value.

  This is an initializer of last resort. It is called if the block is still
  not initialized after trying all initializers. The base class provides
  a default implementation. If you override it, do not call :meth:`!super().rz_init_default()`.

  The default implementation checks if the block has got :meth:`rz_restore_state`
  or :meth:`rz_init`. If it doesn't, it is assumed that this block type doesn't
  care about its output and the output is set to :const:`None` in order to
  prevent an error.

.. method:: Block.rz_start() -> None

  Optional. Start own activity.

  This method is called once after a successful initialization of all blocks.

  Block's own activity is any activity other than reacting to received events.
  A typical example are timer based actions. Regarding this own activity,
  unless it's needed for the initialization, blocks should remain idle
  until receiving this start call.


5. Persistent state
===================

**Attributes:**

  .. attribute:: Block.RZ_PERSISTENCE
    :type: bool

    Class attribute. It is :const:`True` if the persistent state
    is supported by this block type.

    This attribute is created automatically by introspection.

  .. attribute:: Block.RZ_STATE_IS_OUTPUT
    :type: bool

    Optional class attribute. If it exists and is :const:`True`, the internal
    state contains just the block's output and nothing else. This information
    is a hint for :class:`PersistentState` when selecting default *save_flags*.

  .. attribute:: Block.rz_key
    :type: str

    The persistent storage key associated with this block. It contains the
    block's name. A renamed block won't find its state saved by the old name.


Block's :ref:`state persistence <Persistent state>` support requires two methods:

.. method:: Block.rz_export_state() -> object

  Optional. Return the entire internal state.
  The result of the call is undefined when the block hasn't been
  initialized.

  When implementing this method, take into consideration how the
  returned state will be serialized for :ref:`storage <3. Persistent storage>`.
  If not sure, prefer JSON serializable data structures.

  This method is considered low-level and the state should be queried with
  the ":ref:`_get_state`" monitoring event, because the event handler makes
  necessary checks before calling the :meth:`!rz_export_state`.

  .. tip::

    Regardless of the persistent state feature, you might want to implement
    :meth:`!rz_export_state` just for block inspection purposes.

.. method:: Block.rz_restore_state(state: object, /) -> None

  Optional. Initialize by restoring the entire internal *state* and the
  corresponding output. The *state* was returned by :meth:`rz_export_state`
  in some previous program run. Keep in mind that the *state*
  could have been exported by an older program version.

State saving flags
------------------


**Attribute:**

  .. attribute:: Block.rz_save_flags
    :type: redzed.SaveFlags

    State persistence settings set by block's :class:`PersistentState` initializer.
    The value is a combination of :class:`SaveFlags` OR-ed together.
    :attr:`!rz_save_flags` is :abbr:`truthy (boolean value is True)`
    if and only if the state persistence is switched on, i.e.:

    - the circuit has a persistent storage,
    - persistent state is supported by the block type, see :attr:`RZ_PERSISTENCE`
    - the feature was enabled by using :class:`PersistentState` among initializers.

.. class:: SaveFlags

  Enumeration of `flags [↗] <https://docs.python.org/3/library/enum.html#enum.Flag>`_
  related to state persistence settings stored in :attr:`Block.rz_save_flags`.
  Their semantics is documented in :class:`PersistentState`.

  .. attribute:: redzed.SaveFlags.ENABLED
    :noindex:

    Persistent state is enabled. If not set, all other flags are cleared too.
    This flag is used only internally.

  .. attribute:: redzed.SaveFlags.EVENT
    :noindex:

  .. attribute:: redzed.SaveFlags.INTERVAL
    :noindex:

  .. attribute:: redzed.SaveFlags.OUTPUT
    :noindex:

    Options controlling state checkpointing. For brevity they are aliased
    to shorter names listed below which are preferred.

.. data:: SF_NONE

      Null :class:`SaveFlags` value. All flags are cleared.

.. data:: SF_EVENT
.. data:: SF_INTERVAL
.. data:: SF_OUTPUT

    Aliases to respective :class:`SaveFlags` members.


6. Shutdown and cleanup
=======================

**Parameters:**

  **stop_timeout** (float|str) - timeout for asynchronous cleanup
    Optional, default is 10.0 seconds if applicable.
    The timeout can be given as a number of seconds
    or as a :ref:`string with time units <Time durations with units>`.
    It is accepted only if :meth:`rz_astop` is implemented.
    Otherwise it must not be used.

    Note that there is no *init_timeout* counterpart parameter.
    Async initialization is handled in block's
    :ref:`async initializers <Async initializers>`, not in the block itself.

Exceptions in cleanup functions will be logged, but otherwise ignored.
Please note that when shutting down due to a circuit initialization error,
these "stop" functions may be called even if :meth:`rz_start` hasn't been called.

.. attribute:: Block.rz_stop_timeout
  :type: float|None

  The *stop_timeout* value as a number if this parameter is allowed (see above).
  Otherwise :const:`None`.

.. method:: Block.rz_stop() -> None

  Optional. Stop activity and clean up.

.. method:: Block.rz_astop() -> None
  :async:

  Similar to :meth:`rz_stop`, but async.
  It is awaited after the :meth:`!rz_stop`.

  Usually only output blocks need an async shutdown/cleanup.
  The existence of this method automatically enables the *stop_timeout*
  keyword argument. If :meth:`!rz_astop` does not terminate before
  the *stop_timeout* elapses, it will be cancelled.

.. method:: Block.rz_post_stop() -> None

  Optional. This method is called when all blocks are stopped.
  This is the final cleanup function for blocks that must stay
  active also during the shutdown phase, e.g. the output buffers.


7. Event handling
=================

.. type:: EventData

  Event data type. An alias for ``dict[str, Any]``.

  The event data form a Python dict, i.e. they consist of ``'name': <value>`` pairs.
  The keys (names) are strings and valid Python identifiers, because the data
  items were passed to the :meth:`Block.event()` function as keyword arguments.

  When an event requires a value, the preferred name for it is ``'evalue'``.

Sending and receiving:
----------------------

.. method:: Block.is_ready() -> bool

  Check whether the block is ready to accept non-monitoring events.
  If not ready, these events will be rejected with a :exc:`CircuitNotReady` error.
  Monitoring events are always accepted.

  The default implementation checks the circuit's state, because
  not only the block itself, but also dependent formulas and triggers
  must be ready. This implies that normally are blocks ready only in
  states :attr:`CircuitState.INIT_BLOCKS` and :attr:`CircuitState.RUNNING`.

  .. dropdown:: Note for developers

    There exist blocks with special requirements for which is the default
    too narrow. For instance output blocks do shut down after
    :ref:`stop functions <Stop functions>` and the stop functions are
    active during circuit shutdown. These special blocks needs to override
    :meth:`!Block.is_ready` and define their own rules.

    However, it could be easily overlooked that a block operates also in circuit
    states where formulas and triggers are not working. In order to prevent
    mistakes, we recommend that blocks with custom :meth:`!Block.is_ready`
    have a fixed output value, because there is no reason to connect
    formulas or triggers to a fixed output.

.. method:: Block.event(etype: str, /, evalue: object = redzed.UNDEF, **edata: object) -> object

  .. important::
    Do not overload this method. Implement all functionality inside event handlers.

  Handle the incoming event of type *etype* with optionally attached *edata*
  by dispatching it to the appropriate handler. Return the handler's exit value.
  :exc:`UnknownEvent` is raised if there is no handler for the *etype*.
  :exc:`CircuitNotReady` is raised if a non-monitoring event arrives after
  block's shutdown - see :meth:`Block.is_ready`.

  The *evalue* is part of the *edata*. If it is given, it is inserted
  into *edata* as ``edata['evalue']``. It is accepted either as a positional or
  as a keyword argument just for convenience.

  All event data items whose value is :const:`UNDEF` are removed before calling
  the handler.

  While a block is handling an event, it will raise an exception when it receives
  an event of exactly the same type. This precaution stops otherwise infinite loops.

.. function:: send_event(name: str, etype: str, /, evalue: object = redzed.UNDEF, **edata: object) -> object

  Send an event to a block given by its *name* and return the result.
  After resolving the name, remaining arguments are passed to :meth:`Block.event`.

  Following exceptions may be raised during normal operation:

.. exception:: UnknownEvent

  This exception is raised when :meth:`Block.event` is called
  with an event type that the block does not recognize.

.. exception:: ValidationError
  :noindex:

  Sent data was rejected by block's validator. Main article: :ref:`Data validation`.

.. exception:: CircuitNotReady

  This exception is subclassed from :exc:`!RuntimeError`. It is raised when
  a block is not ready to process events, e.g. during shutdown.
  See also: :meth:`Block.is_ready`.

  :ref:`Monitoring events` are excluded from the check and are always accepted.


Event handlers:
---------------

.. method:: Block._event_ETYPE(edata: redzed.EventData) -> object

  Optional. Specialized event handler for type ``ETYPE``.

  ``ETYPE``  stands for an event type name. Each event type needs its own method.
  If a method with matching event type name is defined, it will be called to handle
  that event type. E.g. :meth:`!_event_store` will be called for all ``'store'`` events.

.. method:: Block._default_event_handler(etype: str, edata: redzed.EventData) -> object

  The handler that is called for event types without a specialized event handler.

  Handle all event types *etype* you want to support in this method and
  call ``super()._default_event_handler(etype, edata)`` for everything else.

All event handlers are supposed to extract their arguments from the *edata*.
Any extra items present there must be ignored.

When developing an event handler, take into consideration how the returned data
will be processed or transmitted. If not sure, prefer JSON serializable data structures.


8. Logging functions
====================

.. method:: Block.log_msg(msg: str, *args, level: int, **kwargs) -> None

  Log a message.

  The block's object name (``str(block)``, not :strike:`block.name`) is prepended to the *msg*
  and then the arguments are passed to the standard :meth:`logging.log` function with the given *level*.

.. method:: Block.log_debug(msg: str, *args, **kwargs) -> None
.. method:: Block.log_info(msg: str, *args, **kwargs) -> None
.. method:: Block.log_warning(msg: str, *args, **kwargs) -> None
.. method:: Block.log_error(msg: str, *args, **kwargs) -> None

  Log a debug/info/warning/error message respectively.
  These are simple :meth:`Block.log_msg` wrappers.

.. method:: Block.log_debug1(msg: str, *args, **kwargs) -> None
.. method:: Block.log_debug2(msg: str, *args, **kwargs) -> None

  Convenience methods for DEBUG level logging. Log the debug message *msg*
  if the :ref:`debug level <Debug levels>` is at least 1 or 2 respectively,


9. Application data
===================

**Parameters:**

  **x_anyname** (object) - reserved names for keyword arguments, also in upper case
    All keyword arguments starting with ``'x_'`` or ``'X_'`` are accepted
    and stored as block's attributes. These names are reserved for storing
    arbitrary application data.

**Attributes:**

  .. attribute:: Block.x_anyname
    :type: object

  .. attribute:: Block.X_ANYNAME
    :type: object
