.. currentmodule:: redzed

================
Persistent state
================

The goal of this feature is to make a continuation after an application
restart as seamless as possible. For a single block it means that its
:ref:`internal state <Internal state and output>` is saved to a non-volatile
storage when the application stops and the saved state is restored from that
storage on the next start.


Requirements
============

- The circuit must have access to :ref:`persistent storage <3. Persistent storage>`.
  Enabling persistent state without the storage has no effect.
- The block type must support both internal state export and restoration.
  Enabling persistent state on a block not supporting it is an error.

  For example input blocks, :class:`FSM`, :class:`Timer`,
  :class:`TimeDate`, :class:`TimeSpan` do support persistent state.
  Output blocks don't. If unsure, simply check the :attr:`Block.RZ_PERSISTENCE`
  flag in REPL::

    >>> import redzed
    >>> redzed.OutputFunc.RZ_PERSISTENCE
    False
    >>> redzed.Memory.RZ_PERSISTENCE
    True


Enabling
========

The saved state is restored by :class:`RestoreState`. If the above mentioned
requirements are met, including this initializer in block's *initial* argument
activates both saving and restoring. The internal state is then automatically
saved at shutdown and restored when the :class:`!RestoreState` is activated.

Checkpointing
-------------

It's a method of improving fault-tolerance of long-running applications.
With checkpointing, the internal state is saved not only at shutdown,
but also during the runtime. This increases the chance of having
somewhat recent saved data even if the application was not shut down
properly, e.g. due to a power outage.

For details please refer to the *checkpoints* parameter
of :class:`RestoreState`.
