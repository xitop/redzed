.. currentmodule:: redzed


======
Events
======

**Events are the main communication tool in a circuit**. Events are messages
addressed to a block. They represent commands or requests.
A precise description of supported events is the most important part of block's documentation.

Events are often sent from a :deco:`triggered` function. These are called
internal events. External events are forwarded from the outside world
by a :ref:`supporting task <Supporting tasks>` acting as an interface.
This categorization is only logical. Circuit blocks do not distinguish
between internal and external events. In both cases is the event
delivered by calling :meth:`Block.event`.

When a valid event is received, the block handles it, changes its internal state
and its output accordingly and returns a value. The output change may activate
some triggers which may in turn send events to other blocks. Input changes propagate
in this way through the circuit and, depending on the circuit's logic, may reach
output blocks which are responsible for circuit's actions.


Event type and data
===================

An event is a message addressed to a destination block. It is identified
by its type. The type is a name (string) and must a valid Python identifier.
The event type selects the event handler for the given event. The event
can carry arbitrary data in the form of ``'name':<value>`` pairs, except when
the ``<value>`` is equal to the special constant :const:`UNDEF`, the whole
entry is filtered out.

Blocks react to events by performing some specific action and returning a result.
For example a :class:`Memory` block accepts a ``'store'`` event, expects
an ``'evalue'`` item in the data, and if the value passes validation, the block
changes its output value and returns :const:`True`.

Few basic event types are available on all blocks, see the next section.


Monitoring events
=================

These events are regular events and the term "monitoring"
is just a convention for events with these characteristics:

- **_get_xyz**: the type name begins with a ``'_get_'`` prefix
- **monitoring**: used for debugging, inspecting, statistics, etc.
- **simple query**: can be handled within the destination block
  and replied with a return value
- **no side-effects**: must not make any change to the circuit

.. important::

  Due to the absence of side-effects are monitoring events accepted
  during the shutdown when all other events are rejected
  with the :exc:`CircuitShutDown` exception.

If you are creating an own type of blocks, feel free to use the ``'_get_'`` prefix,
but only for events that match these characteristics.

First three of the following monitoring events are defined for all block types.

_get_names
----------
``Block.event('_get_names')`` returns a dict with items ``'name'``, ``'comment'``
and ``'type'`` containing block's name, block's comment and the name of the
block type. Other items may be added in the future.


_get_output
-----------

``Block.event('_get_output')`` calls :meth:`Block.get`
and returns the current output.


_get_previous
-------------

``Block.event('_get_previous')`` calls :meth:`Block.get_previous`
and returns the previous output.


_get_state
----------

``Block.event('_get_state')`` returns the current state if possible.
:exc:`UnknownEvent` is raised if the operation is not supported.
:exc:`!RuntimeError` is raised when the block is not initialized.


_get_config
-----------

``Block.event('_get_config')`` is a debugging aid supported only by some blocks,
notably by :ref:`Cron <Cron server>` and :ref:`FSMs <Finite-State Machines>`.
The exact structure of returned configuration data depends on the block.
Because the data is internal, it is subject to change between versions,
but the output format should be comprehensible.


Examples (events)
=================

::

  # definition
  m1_memory = redzed.Memory("m1", initial=0)

  # Example usage in a triggered function.
  # Store a value in the m1_memory cell:
  #   event type is 'store', event data is {'evalue': 123}
  #   because the positional argument is stored as the 'evalue' item.
  m1_memory.event('store', 123)
  # m1_memory.get() now returns 123 (output value)


  t1 = redzed.Timer("t1")
  ...
  # start a time interval:
  #   event type is 'start', event data is {'duration': '1m30s'}
  t1.event('start', duration='1m30s')
  # now the timer's output is scheduled to be True for 90 seconds
