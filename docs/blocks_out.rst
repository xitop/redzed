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


Stop functions
==============

A common requirement is that an application should leave the controlled systems
or devices in a well-defined state after it terminates. This is achieved by sending
appropriate values to output blocks during shutdown, so they are processed as last
values before stopping. We call these values "stop values" and functions
sending them are called "stop functions".

The most common case is sending a single fixed stop value. The output blocks provide
a convenience option *stop_value*  which creates a stop function automatically.

An explicit stop function is needed only if the stop value is not known in advance
or if a multiple values need to be sent.

.. decorator:: stop_function

  Register a stop function, i.e. a function that will be automatically run during
  circuit shutdown in order to send stop values to output blocks. Please note
  that by "output blocks" we mean the respective buffers if the blocks are asynchronous.

Stop functions are called without arguments. Exceptions in stop functions are logged,
but the shutdown will continue. When a stop function is called, triggers are already defunct
and non-output blocks do not accept non-monitoring events. The stop function may
check output values of all blocks using :meth:`Block.get`,
send :ref:`monitoring events <Monitoring events>` to all blocks
and, of course, send any events to output blocks.


Sync outputs
============

.. class:: OutputFunc(name, *, func, validator=None, stop_value=redzed.UNDEF, triggered_by=None, **block_kwargs)

  Call the function *func* when an ``'put'`` event arrives.
  The output of an :class:`!OutputFunc` block is always :const:`None`.

  :param Callable[[Any], Any] func:
    Function to be invoked on each ``'put'`` event with the event data item ``'evalue'``
    as its only argument.

  :param validator: Optional :ref:`data validator <Output data validation>`.
  :type validator: Callable[[Any], Any] | None

  :param Any stop_value:
    If *stop_value* is given, it is processed as the last value before stopping.
    See the :ref:`stop functions <Stop functions>`.

  :param str | redzed.Block | redzed.Formula | None triggered_by:

    Convenience option. If not :const:`None`, create a :class:`Trigger` sending
    the output of *triggered_by* to this output block via ``'put'`` events.
    The block or formula can be given by its name.

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
interesting, suggested search keywords are: "Python multiprocessing",
Python :abbr:`GIL (Global Interpreter Lock)`" and "Python free threading".

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

.. caution::

  In general, there are no warnings and no runtime errors when
  output blocks are attached to buffers in a nonsensical way.


Output data validation
----------------------

Async output buffers can validate data using a validator.
It is a function specified with the *validator* argument.
It takes one argument, the data to be output. This includes a *stop_value* if it is defined.
The validator either accepts the data by returning it or rejects it by raising
an exception. The returned data may be modified (preprocessed).

Unlike the input data validation, the output data originate inside the circuit,
so their validation provides only an additional layer of protection.
The main use-case here is the preprocessing.


Worker mode
-----------

.. class:: QueueBuffer(name, *, maxsize=0, priority_queue=False, validator=None, stop_value=redzed.UNDEF, triggered_by=None, **block_kwargs)

  Create a :abbr:`queue (FIFO = First In, First Out)` buffer
  with an interface for an async output block. The output
  is unused and its value is always :const:`None`.

  :param int maxsize:

    Set the buffer capacity. If *maxsize* is zero (default),
    the queue size is not limited.

  :param bool priority_queue:

    Use a `priority queue [↗] <https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue>`_
    instead of a standard queue.

  :param validator: Optional :ref:`data validator <Output data validation>`.
  :type validator: Callable[[Any], Any] | None

  :param Any stop_value:
    If *stop_value* is given, it is processed as the last value before stopping.
    See the :ref:`stop functions <Stop functions>`.

    When this parameter or a stop function is used, the :class:`OutputWorker` attached
    to this buffer should be run with ``workers=1``, which is the default.
    With multiple workers, the *stop_value* might be not the last processed value overall.

  :param str | redzed.Block | redzed.Formula | None triggered_by:

    Convenience option. If not :const:`None`, create a :class:`Trigger` sending
    the output of *triggered_by* to this buffer via ``'put'`` events.
    The block or formula can be given by its name.

  Events:
    **'put'**
      Usage: ``queue_buffer.event('put', value)``.

      Insert the *value* into the queue. Raise the :exc:`!asyncio.QueueFull` error
      if the buffer capacity set by *maxsize* was reached. Raise :exc:`!RuntimeError`
      if the circuit is no longer running.

    **'_get_size'**
      Usage: ``size = queue_buffer.event('_get_size')``.
      Return the number of items in the buffer.

  .. method:: attach_output(output = OutputWorker, **output_kwargs)

    Convenience option. Create an output block of type *output* that will fetch
    data from this buffer. The default block type is :class:`OutputWorker`.
    The output block will be created with *output_kwargs* arguments;
    please note:

    - By default, the name will be derived from the buffer's name by appending
      a short ``"_io"`` suffix. Use ``name=...`` to set the name explicitly.
    - By default, the comment will be copied from the buffer.
      Use ``comment=...`` to override.
    - The *buffer* argument will be set automatically. Do not include ``"buffer"``
      in *output_kwargs*.

    This method returns *self*, i.e. the buffer object. If need be,
    the output block object can be looked up by name with :meth:`Circuit.resolve_name`.

.. class:: OutputWorker(name, *, aw_func, buffer, workers=1, stop_timeout=..., **block_kwargs)

  Repeatedly fetch a value from a *buffer* and run an async function *aw_func* with that
  value until it terminates. Wait for a value when the buffer is empty.

  :param buffer: A data buffer; :class:`QueueBuffer` is required for proper functioning.

  :param aw_func:
    An asynchronous function taking one argument, the value from the buffer.
    More precisely, *aw_func* must be a callable returning an awaitable.
    It will be used in a statement::

      await aw_func(value)

    Usually it is defined with ``async def aw_func(arg): ...``,
    but other options exist.

    The function should be self-contained. It should handle errors, retries,
    timeouts, etc. If the function raises, the circuit shuts down.

    **Running in threads:**

    Asyncio provides a way to run a blocking function in a separate thread
    and await the result. This functionality is provided by
    `asyncio.to_thread [↗] <https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread>`_.
    A tiny adapter is needed for usage with :class:`!OutputWorker`::

      aw_func=lambda arg: asyncio.to_thread(blocking_function, arg)

  :param int workers: Number of concurrent worker tasks.

  During a shutdown are all workers active until the buffer is drained
  or until the *stop_timeout* is reached, whatever happens first.
  Workers that do not stop before the timeout are then cancelled.

  The output of an :class:`!OutputWorker` block is always :const:`None`.


Controller mode
---------------

.. class:: MemoryBuffer(name, *, validator=None, stop_value=redzed.UNDEF, triggered_by=redzed.UNDEF, **block_kwargs)

  Create a buffer holding only the last value. The buffer has
  an interface for an async output block. The output is unused
  and its value is always :const:`None`.

  :param validator: Optional :ref:`data validator <Output data validation>`.
  :type validator: Callable[[Any], Any] | None

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

  .. method:: attach_output(output = OutputController, **output_kwargs)

    This method is identical to :meth:`QueueBuffer.attach_output`,
    except that the default output block type is :class:`OutputController`.


.. class:: OutputController(name, *, aw_func, buffer, rest_time=0.0, stop_timeout=..., **block_kwargs)

  Repeatedly fetch a value from a *buffer* and run an async function *aw_func* with that
  value until it terminates OR until a new value is available from the buffer.
  Wait for a value when the buffer is empty.

  :param buffer:
    A data buffer; :class:`MemoryBuffer` is required for proper functioning.
    Only one :class:`!OutputController` should be attached to one :class:`!MemoryBuffer`.

  :param aw_func:

    An asynchronous function taking one argument, the value from the buffer.
    In exact terms is *aw_func* a callable returning an awaitable.
    The task awaiting *aw_func(value)* will be cancelled (and awaited) when a new value
    arrives to the buffer. Any threading related operations should be avoided,
    because cancelling a thread is quite problematic.

    The function should be self-contained. It should handle errors, retries,
    timeouts, etc. If the function raises, the circuit shuts down.

  :param rest_time:
    *rest_time* is the duration of an idle sleep after each *aw_func*
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
