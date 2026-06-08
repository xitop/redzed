.. currentmodule:: redzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D). Only recent changes
are listed here. Full history can be found on GitHub.


26.6.8
======

- :class:`FSM`: fix an issue related to initialization from a saved timed state.


26.5.19 (stable release)
========================

- :meth:`Circuit.get_errors`: the returned list is now a copy
  and as such may be modified.


26.5.5 (release candidate 2)
============================

- an internal function invoking dynamically chosen methods
  (namely :ref:`FSM hook methods <Hooks>` and event handlers :meth:`Block._event_ETYPE`)
  now supports also methods modified with ``@staticmethod`` or ``@classmethod``.
  Previously only regular methods were supported.
- names discontinued in 26.4.4 due to renaming were removed


26.4.20 (release candidate 1)
=============================

- fix regression from 26.4.4: supporting tasks were started too early
- :meth:`Circuit.create_service`: parameter *immediate_start* was replaced by
  *start_state*
- :meth:`Circuit.reached_state`: circuit state can be given also as a string
- names discontinued in 26.3.13 due to renaming were removed


26.4.4 (last beta)
==================

Redzed is now feature-complete. The next release will be probably
a stable release candidate.

Breaking changes:

- :class:`FSM`: external ``cond_EVENT`` functions are no longer supported.

Renaming - the old names will be kept as an alias for a short transitory period:

- :attr:`!FSM.state` (property) was replaced by :meth:`FSM.fsm_state` (method).
- :exc:`!CircuitShutDown` was replaced by :exc:`CircuitNotReady`, because
  a shutdown is not the only reason for being not ready.

New features, improvements:

- :ref:`Block initializers` are now reusable.
- :ref:`Input validators <Data validation>`: a dedicated
  :exc:`ValidationError` was added. This change aims to expose
  eventual problems with validators themselves.
- :meth:`Circuit.get_errors` was added.
- :class:`FSM`: Initializers can set also the :attr:`FSM.sdata`.
- :class:`FSM`: Some features are more precisely specified, especially
  :ref:`error handling rules <Event error handling>`.
- :class:`redzed.utils.PersistentDict`: an empty file is accepted as valid.
  This allows to prevent :exc:`FileNotFoundError` on first run.

Bug fixes:

- Block events should be rejected when formulas and triggers are not functional,
  i.e. when they are uninitialized or have been shut down. Previously
  only the latter condition was tested.
- :class:`redzed.utils.PersistentDict`: no data was saved with ``sync_time=0``.
- :class:`MemoryExp`: Event data items ``'suppress'`` and ``'duration'``
  in a ``"store"`` event were not honored.
- :class:`MemoryExp`: Event ``'expire'`` was not implemented.
- :class:`Formula`: detection of dependency loops was not working.


Older releases
==============

- 26.2.4, 26.2.18, 26.3.13 Beta releases
- 26.1.28 Alpha stage
- 25.12.30 Initial release
