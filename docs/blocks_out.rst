.. currentmodule:: redzed

=======
Outputs
=======

**Conventions used in this chapter:**

- Only block specific parameters are documented here.
  Parameters like *initial*, *stop_timeout* are documented in the :ref:`Block API`.

- Class signatures may be syntactically incorrect
  for the sake of comprehensibility.

- All time duration values (timeouts, intervals, etc.) can be given as a number
  of seconds or as a :ref:`string with time units<Time durations with units>`.


Sync outputs
============

.. class:: OutputFunc(name, *, func,  stop_value=redzed.UNDEF, triggered_by=redzed.UNDEF, **block_kwargs)

  Call the function *func* when an ``'put'`` event arrives.
  The output of an :class:`!OutputFunc` block is always :const:`None`.

  :param Callable[[Any], Any] func:
    Function to be invoked on each ``'put'`` event with the event data item ``'evalue'``
    as its only argument.

  :param Any stop_value:
    If *stop_value* is given, it is used as an argument of a synthetic
    event delivered to the block during the cleanup and processed as the
    last item before stopping. This allows to leave the controlled process
    in a well-defined state.

  :param str | redzed.Block | redzed.Formula triggered_by:

    Convenience option. Create a :class:`Trigger` sending the output of *triggered_by*
    to this output block via ``'put'`` events. The block or formula can be given
    by its name.

  Events:
    **'put'**
      Each ``'put'`` event triggers the function call and returns
      function's return value. The function receives only the ``'evalue'``
      item from the event data. If multiple values are to be passed,
      make ``'evalue'`` a container.


Async outputs
=============

Introduction
------------

Asynchronous output functions are to be used when the output function could
be blocking. A *blocking function* is a function that does not always return
in a very short time due to a CPU intensive computation or slow I/O.
Local file access is considered not blocking, but any network communication
is a typical example of blocking I/O.

CPU bound operations are best run in a separate process. We won't go into
details, because output functions are not CPU bound. If you find this topic
interesting, search keywords are: "Python :abbr:`GIL (Global Interpreter Lock)`"
and "Python free threading".

Slow I/O usually has its native async API. Slow I/O without an async API
can be run in a separate thread; see the example in :class:`OutputWorker`.

Because async output blocks do not process data at the moment when
they are produced, every async output block needs a buffer.
The buffer receives data on one end and provides an interface for an output
block on the other end. A buffer may receive data from multiple sources.

There are two major use-cases:

**Worker mode**

Each output data item represents an individual command or request
to be fulfilled independently of other items. Example: a message to be sent.

Use a :class:`QueueBuffer` with an :class:`OutputWorker` block.

**Controller mode**

The output data represent a desired state to be reached. Each new value
is an update overwriting the previous value. Example: controlling an actuator,
e.g. switching an electric circuit on or off.

Use a :class:`MemoryBuffer` with an :class:`OutputController`.


Worker mode
-----------

.. class:: QueueBuffer(name, *, maxsize=0, priority_queue=False, stop_value=redzed.UNDEF, triggered_by=redzed.UNDEF, **block_kwargs)

  Create a :abbr:`queue (FIFO = First In, First Out)` buffer
  with an interface for an output block. The output
  is unused and its value is always :const:`None`.

  :param int maxsize:

    Set the buffer capacity. If *maxsize* is zero (default),
    the queue size is not limited.

  :param bool priority_queue:

    Use a `priority queue [↗] <https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue>`_
    instead of a standard queue.

  :param Any stop_value:
    If defined, the ``stop_value`` is inserted into the buffer during shutdown
    as the very last value. This allows to leave the controlled process
    in a well-defined state.

    When this parameter is used, the :class:`OutputWorker` attached to this buffer
    should be run with ``workers=1``, which is the default. With multiple workers,
    the *stop_value* might be not the last processed value overall.

  :param str | redzed.Block | redzed.Formula triggered_by:

    Convenience option. Create a :class:`Trigger` sending the output of *triggered_by*
    to this buffer via ``'put'`` events. The block or formula can be given by its name.

  Events:
    **'put'**
      Usage: ``queue_buffer.event('put', value)``.

      Insert the *value* into the queue. Raise the :exc:`!asyncio.QueueFull` error
      if the buffer capacity set by *maxsize* was reached. Raise :exc:`!RuntimeError`
      if the circuit is no longer running.

    **'_get_size'**
      Usage: ``size = queue_buffer.event('_get_size')``.
      Return the number of items in the buffer.


.. class:: OutputWorker(name, *, coro_func, buffer, workers=1, stop_timeout=..., **block_kwargs)

  Repeatedly fetch a value from a *buffer* and run an async function *coro_func* with that
  value until it terminates. Wait for a value when the buffer is empty.

  :param buffer: A data buffer; :class:`QueueBuffer` is required for proper functioning.

  :param coro_func:
    An asynchronous function taking one argument, the value from the buffer.

    The function should be self-contained. It should handle errors, retries,
    timeouts, etc. If the function raises, the circuit shuts down.

    **Running in threads:**

    Asyncio provides a way to run a blocking function in a separate thread
    and await the result. This functionality is provided by
    `asyncio.to_thread [↗] <https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread>`_.
    A tiny adapter is needed for usage with :class:`!OutputWorker`::

      coro_func=lambda arg: asyncio.to_thread(blocking_function, arg)

  :param int workers: Number of concurrent worker tasks.

  During a shutdown are all workers active until the buffer is drained
  or until the *stop_timeout* is reached, whatever happens first.
  Workers that do not stop before the timeout are then cancelled.

  The output of an :class:`!OutputWorker` block is always :const:`None`.


Controller mode
---------------

.. class:: MemoryBuffer(name, stop_value=redzed.UNDEF, triggered_by=redzed.UNDEF, **block_kwargs)

  Create a buffer holding only the last value. The buffer has
  an interface for an output block. The output is unused
  and its value is always :const:`None`.

  :param Any stop_value:
    If defined, the ``stop_value`` is inserted into the buffer during shutdown
    as the very last value. This allows to leave the controlled process
    in a well-defined state.

  :param str | redzed.Block | redzed.Formula triggered_by:

    Convenience option. Create a :class:`Trigger` sending the output of *triggered_by*
    to this buffer via ``'put'`` events. The block or formula can be given by its name.

  Events:
    **'put'**
      Usage: ``memory_buffer.event('put', value)``.

      Store the *value* in the buffer. Any previously stored value will be overwritten.
      Raise :exc:`!RuntimeError` if the circuit is no longer running.

    **'_get_size'**
      Usage: ``size = memory_buffer.event('_get_size')``.
      Return the number of items in the buffer which is either 0 or 1.


.. class:: OutputController(name, *, coro_func, buffer, rest_time=0.0, stop_timeout=..., **block_kwargs)

  Repeatedly fetch a value from a *buffer* and run an async function *coro_func* with that
  value until it terminates OR until a new value is available from the buffer.
  Wait for a value when the buffer is empty.

  :param buffer:
    A data buffer; :class:`MemoryBuffer` is required for proper functioning.
    Only one :class:`!OutputController` should be connected to one :class:`!MemoryBuffer`.

  :param coro_func:

    An asynchronous function taking one argument, the value from the buffer.
    The task running *coro_func* will be cancelled (and awaited) when a new value
    arrives to the buffer. Any threading related operations should be avoided,
    because cancelling a thread is quite problematic.

    The function should be self-contained. It should handle errors, retries,
    timeouts, etc. If the function raises, the circuit shuts down.

  :param rest_time:
    *rest_time* is the duration of an idle sleep after each *coro_func*
    invocation, even after a failure, timeout or cancellation. It can represent
    a settling time or serve as a limit for the frequency of actions.
    The rest time sleep is shielded from cancellation. Keep it short.

    .. note::
      A *rest_time* idle interval will be added also after a cancellation
      due to the *stop_timeout*. Block's total shutdown time will be extended
      in this case.

  When shutting down, the block stops when the buffer gets empty or when
  the *stop_timeout* is reached, whatever happens first.
  Make sure the *stop_timeout* accounts for all required time
  to finish the work.
  Make allowance for processing of the last buffered value plus
  one additional value if the optional *stop_value* is defined
  and don't forget to add *rest_time* intervals after each value.

  The output of an :class:`!OutputController` block is always :const:`None`.
