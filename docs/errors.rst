.. currentmodule:: redzed

==============
Error handling
==============


Reporting and handling of errors
================================

1. Redzed aborts the runner (see :meth:`run`) when it detects:

   - an unhandled exception in the supplied code used as:

     - a function associated with a :class:`Trigger` or a :class:`Formula`
     - an :ref:`FSM hook <Hooks>`
     - an I/O function (e.g. from :class:`DataPoll` or :class:`OutputFunc`)

     However - as explained :ref:`below <Error checking in asyncio>` - exceptions raised
     in asynchronous tasks affect only the task itself. Please follow
     the recommendation given there.
   - a termination (with or without an exception) of a
     :ref:`service task or a supporting task <Service tasks vs. supporting tasks>`
     before shutdown.
   - a dependency loop. In order to prevent an endless recursion, these
     conditions are forbidden:

     - when evaluating a formula changes any of its inputs
     - when event handling in a block generates (directly or indirectly)
       another event of exactly the same type sent to the same block

   - explicit :meth:`Circuit.abort`

2. Redzed logs an exception, but otherwise ignores the error in:

   - :ref:`individual initializers <Initializers>`
   - :ref:`cleanup functions <6. Shutdown and cleanup>`
   - :ref:`stop functions <Stop functions>`

3. Redzed may raise in :meth:`Block.event`. The caller is responsible
   for handling the exception.


Error checking in asyncio
=========================

A non-trivial asyncio application may need several long-running tasks.
Even if the code was written in agreement with the *"Errors should never pass silently"*
guideline, tasks in asyncio are *"fire and forget"*. When a task crashes,
the rest of the program continues to run. The application could become unresponsive
or ill-behaving.

.. important::

  Make sure an unexpected asyncio task termination
  cannot happen unnoticed.

Please use the :meth:`Circuit.create_service` helper function.
If it doesn't suit you, make use of some of these techniques:

- use ``try / except`` wrappers around the task coroutines to catch unexpected
  termination, errors and if need be also cancellation. Remember that
  you should not consume an :exc:`!asyncio.CancelledError` unless
  you know exactly what you are doing.
- utilize asyncio task groups
- customize the global event loop's error handler,
  see `loop.set_exception_handler [↗] <https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_exception_handler>`_
  in asyncio.

And, as always, check the results of terminated tasks.
