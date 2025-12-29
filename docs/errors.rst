.. currentmodule:: redzed

==============
Error handling
==============


Reporting errors
================

1. Typically, when a fatal error occurs in a Redzed related function,
   it is sufficient to simply raise an exception as usual,
   because the runner will receive the exception. In reaction it will
   abort unless the error is deliberately ignored. All such cases are
   properly documented (:ref:`individual initializers <Initializers>`,
   :ref:`cleanup functions <6. Shutdown and cleanup>`).

2. However - as explained in a later section - exceptions raised
   in asynchronous tasks affect only the task itself. Please follow
   the recommendation given there.

3. In all other cases, if an abort is desired, :meth:`Circuit.abort` must
   be called explicitly.


Detecting loops
===============

Redzed will automatically detect dependency loops and abort the circuit
runner in order to prevent endless recursion in these cases:

- when evaluating a formula changes any of its inputs
- when event handling in a block causes (directly or indirectly) that
  another event of exactly the same type is sent to that block


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

And, of course, check the results of terminated tasks.
