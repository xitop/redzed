.. currentmodule:: redzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).


26.2.4 (beta)
=============

New features, improvements:

- Output blocks: introducing :ref:`stop functions <Stop functions>`
- :class:`Repeat`: settings may be modified dynamically


26.1.28 (alpha)
===============

Breaking changes:

- :deco:`formula`: the decorator now does not take parameters
- :class:`FSM`: timed and non-timed states were combined into single table
- :class:`DataPoll`: support for a validator was removed.
  Validation is a responsibility of the acquisition function.
- :class:`Memory`, :class:`MemoryExp`:
  store events now report validation errors differently
- :class:`OutputWorker`, :class:`OutputController`, :class:`InitTask`:
  argument *coro_func* was renamed to more accurate *aw_func*;
  an awaitable (aw) is a broader term than a coroutine (coro)

Bug fixes:

- :class:`QueueBuffer`: the buffer was sometimes shut down before
  the *stop_value* was retrieved
- :class:`Memory` (but not :class:`MemoryExp`): during initialization from
  saved persistent data, previously preprocessed data were erroneously preprocessed again
- :ref:`cron server <Cron service API>`: a race condition during
  schedule updates was fixed
- some async function/coroutine/awaitable type checks were removed due to false positives

New features, improvements:

- :ref:`Initializers`: the rule for distinguishing multiple initializers
  from ordinary sequences was relaxed
- :class:`QueueBuffer`, :class:`MemoryBuffer`: buffers support data validation
- :ref:`logging setup <Handlers>` was improved
- :ref:`output counter <2. Output>` now does not wrap around


25.12.30 (alpha)
================

Initial release.
