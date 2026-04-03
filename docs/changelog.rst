.. currentmodule:: redzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D). Only recent changes
are listed here. Full history can be found on GitHub.


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


26.3.13 (beta)
==============

Breaking changes:

- :class:`PersistentState` (was :class:`!RestoreState`):
  *checkpoints* option was replaced by *save_flags*
  which allows a finer control and has a reasonable default
- :meth:`!Block.get_previous` was removed. Its functionality was integrated
  into :meth:`Block.get`.
- monitoring events ``"_get_names"`` and ``"_get_output"`` were combined
  into ":ref:`_get_info`"
- :meth:`Circuit.set_persistent_storage`: option *sync_time* was renamed to *save_interval*

Renaming - the old names will be kept as an alias for a short transitory period:

- :deco:`!@triggered` was renamed to :deco:`trigger`
- :class:`!RestoreState` was renamed to :class:`PersistentState`

New features, improvements:

- An implementation of persistent storage was added:
  :class:`redzed.utils.PersistentDict`
- :meth:`Circuit.set_persistent_storage` can register a *close_callback*
- :class:`FSM`: :ref:`dynamically selected states <Dynamically selected states>`
  were implemented
- :class:`FSM`: incorrect :ref:`hook method names <hooks>` are now rejected;
  previously they were ignored
- Functions :func:`redzed.send_event` and :func:`redzed.get_output`
  were added
- :ref:`Data validators <Data validation>` can reject values
  also by returning :const:`UNDEF`
- Triggers and Formulas now offer simple
  :ref:`access to the previous output <Access to the previous output>` value
- :class:`FSM`: output of ``'_get_config'`` event is now JSON serializable
- :class:`Formula` now auto-detects the name the same way as :deco:`formula`
- :meth:`Circuit.get_persistent_storage` was added


26.2.18 (beta)
==============

Breaking changes:

- :meth:`!Block.is_undef` was replaced by :meth:`Block.is_initialized`.
  Note the inverse meaning.
- :ref:`Logic block <Block API>` output modifiers were a bad design
  choice and were removed. Approximate replacements of options *output_counter*
  and *output_previous* are *always_trigger* and :meth:`Block.get_prev`
  respectively.
- :class:`Counter`: event ``'put'`` was renamed to ``'set'``

New features, improvements:

- :class:`MemoryBuffer`, :class:`QueueBuffer`: new ``.attach_output()`` method
  allows to create a matching async output block easily
- :deco:`formula`: new naming rule
- :class:`Counter`: event ``'reset'`` was added
- :class:`Repeat`: *jitter_pct* option was added
- Event data entries with :const:`UNDEF` value are automatically
  filtered out by :meth:`Block.event`


Older releases:

- 26.2.4 first beta
- 26.1.28 alpha stage
- 25.12.30 Initial release
