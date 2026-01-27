"""
Output blocks.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['MemoryBuffer', 'OutputFunc', 'OutputController', 'OutputWorker', 'QueueBuffer']

import asyncio
from collections.abc import Callable, Awaitable
import typing as t

import redzed
from redzed.utils import BufferShutDown, cancel_shield, func_call_string, MsgSync, time_period
from .validator import _Validate


class OutputFunc(redzed.Block):
    """
    Run a function when a value arrives.
    """

    def __init__(
            self, *args,
            func: Callable[..., t.Any],
            stop_value: t.Any = redzed.UNDEF,
            triggered_by: str|redzed.Block|redzed.Formula|redzed.UndefType = redzed.UNDEF,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._stop_value = stop_value
        self._func = func
        self._parameters: list[tuple[str, bool]] = []    # item: (name, is_required)
        if triggered_by is not redzed.UNDEF:
            @redzed.triggered
            def trigger(value=triggered_by) -> None:
                self.event('put', value)

    def _event_put(self, edata: redzed.EventData) -> t.Any:
        evalue = edata['evalue']
        if redzed.get_debug_level() >= 1:
            self.log_debug("Running %s", func_call_string(self._func, (evalue,)))
        try:
            result = self._func(evalue)
        except Exception as err:
            func_args = func_call_string(self._func, (evalue,))
            self.log_error("Output function failed; call: %s; error: %r", func_args, err)
            err.add_note(f"Error occurred in function call {func_args}")
            self.circuit.abort(err)
            raise
        self.log_debug2("output function returned: %r", result)
        return result

    def rz_stop(self) -> None:
        if self._stop_value is not redzed.UNDEF:
            self._event_put({'evalue': self._stop_value})


class _Buffer(_Validate, redzed.Block):
    def __init__(
            self, *args,
            stop_value: t.Any = redzed.UNDEF,
            triggered_by: str|redzed.Block|redzed.Formula|redzed.UndefType = redzed.UNDEF,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # the stop_value is stored already validated
        self._stop_value = \
            redzed.UNDEF if stop_value is redzed.UNDEF else self._validate(stop_value)
        if triggered_by is not redzed.UNDEF:
            @redzed.triggered
            def trigger(value=triggered_by) -> None:
                self.event('put', value)

    def _event_put(self, edata: redzed.EventData) -> None:
        """Put an item into the queue."""
        # not aggregating following two lines in order to have a clear traceback
        evalue = edata['evalue']
        evalue = self._validate(evalue)
        self.rz_put_value(evalue)

    def rz_put_value(self, value: t.Any) -> None:
        raise NotImplementedError

    def rz_get_size(self) -> int:
        raise NotImplementedError

    async def rz_buffer_get(self) -> t.Any:
        raise NotImplementedError


class QueueBuffer(_Buffer):
    """
    FIFO buffer for output values.
    """

    def __init__(
            self, *args,
            maxsize: int = 0,
            priority_queue: bool = False,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        queue_type = asyncio.PriorityQueue if priority_queue else asyncio.Queue
        self._queue: asyncio.Queue[t.Any] = queue_type(maxsize)
        # Queue.shutdown is available in Python 3.13, but we want to support 3.11+
        self._waiters = 0
        self._shutdown = False

    def rz_put_value(self, value: t.Any) -> None:
        self._queue.put_nowait(value)

    def rz_get_size(self) -> int:
        """Get the number of items in the buffer."""
        return self._queue.qsize()

    def _event__get_size(self, _edata: redzed.EventData) -> int:
        return self.rz_get_size()

    def rz_stop(self) -> None:
        waiters = self._waiters
        if self._stop_value is not redzed.UNDEF:
            self.rz_put_value(self._stop_value)
            waiters -= 1
        # unblock waiters
        for _ in range(waiters):
            self.rz_put_value(redzed.UNDEF)
        self._shutdown = True

    async def rz_buffer_get(self) -> t.Any:
        """
        Remove and return the next value from the queue.
        Wait for a value if the queue is empty.

        After the shutdown drain the queue
        and then raise BufferShutDown to each caller.
        """
        if self._shutdown and self._queue.qsize() == 0:
            raise BufferShutDown("The buffer was shut down")
        self._waiters += 1
        try:
            value = await self._queue.get()
        finally:
            self._waiters -= 1
        if value is redzed.UNDEF:
            # unblocked in rz_stop
            raise BufferShutDown("The buffer was shut down")
        return value

    def rz_close(self) -> None:
        if (size := self._queue.qsize()) > 0:
            self.log_warning("%d unprocessed item(s) left in the buffer", size)


class MemoryBuffer(_Buffer):
    """
    Single memory cell buffer.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cell: MsgSync[t.Any] = MsgSync()
        self._stop_pending = False

    def rz_get_size(self) -> int:
        """Get the number of items (0 or 1) in the buffer."""
        has_data = self._cell.has_data() or self._cell.is_shutdown() and self._stop_pending
        return 1 if has_data else 0

    def _event__get_size(self, _edata: redzed.EventData) -> int:
        return self.rz_get_size()

    def rz_put_value(self, value: t.Any) -> None:
        self._cell.send(value)

    def rz_stop(self) -> None:
        """Shut down"""
        self._cell.shutdown()
        self._stop_pending = self._stop_value is not redzed.UNDEF

    async def rz_buffer_get(self) -> t.Any:
        """
        Remove and return an item from the memory cell.

        When the buffer is empty:
          - before shutdown wait
          - after shutdown return the *stop_value* once (if defined),
            then raise BufferShutDown
        """
        try:
            return await self._cell.recv()
        except BufferShutDown:
            if not self._stop_pending:
                raise
            self._stop_pending = False
            return self._stop_value

    def rz_close(self) -> None:
        if self._stop_pending:
            self.log_error("The stop_value was not retrieved")


class OutputWorker(redzed.Block):
    """
    Run an awaitable for each value from a buffer.
    """

    def __init__(
            self, *args,
            buffer: str|redzed.Block,
            aw_func: Callable[[t.Any], Awaitable[t.Any]],   # e.g. an async function
            workers: int = 1,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if workers < 1:
            raise ValueError(f"{self}: At least one worker is required")
        self._buffer = buffer
        self._aw_func = aw_func
        self._workers = workers
        self._worker_tasks: list[asyncio.Task[None]] = []

    def rz_pre_init(self) -> None:
        self._buffer = self.circuit.resolve_name(self._buffer)  # type: ignore[assignment]
        if not isinstance(self._buffer, _Buffer):
            raise TypeError(
                f"Check the buffer parameter; {self._buffer} is not a compatible block")

    async def _worker(self, wname: str) -> None:
        getter = self._buffer.rz_buffer_get     # type: ignore[union-attr]
        while True:
            try:
                value = await getter()
            except BufferShutDown:
                return
            try:
                if redzed.get_debug_level() >= 1:
                    self.log_debug(
                        "%s: Awaiting %s", wname, func_call_string(self._aw_func, (value,)))
                await self._aw_func(value)
                self.log_debug2("%s: await done", wname)
            except Exception as err:
                err.add_note(f"Processed value was: {value!r}")
                raise

    def rz_start(self) -> None:
        workers = self._workers
        for n in range(workers):
            wname = "worker"
            if workers > 1:
                wname += f"={n+1}/{workers}"
            self._worker_tasks.append(
                self.circuit.create_service(
                    self._worker(wname), auto_cancel=False, name=f"{self}: {wname}"))

    async def rz_astop(self) -> None:
        worker_tasks = [worker for worker in self._worker_tasks if not worker.done()]
        if not worker_tasks:
            return
        try:
            await asyncio.wait(worker_tasks)
        except asyncio.CancelledError:
            # stop_timeout from the circuit runner
            for worker in worker_tasks:
                if not worker.done():
                    worker.cancel()
            await asyncio.sleep(0)
            if (running := sum(1 for worker in worker_tasks if not worker.done())) > 0:
                self.log_warning("%d worker(s) did not stop", running)
            raise

class OutputController(redzed.Block):
    """
    Run an awaitable for the latest value from a buffer.
    """

    def __init__(
            self, *args,
            buffer: str|redzed.Block,
            aw_func: Callable[[t.Any], Awaitable[t.Any]],     # e.g. an async function
            rest_time: float|str = 0.0,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rest_time = time_period(rest_time, zero_ok=True)
        if self._rest_time >= self.rz_stop_timeout:
            raise ValueError(f"{self}: rest_time must be shorter than the stop_timeout")
        self._buffer = buffer
        self._aw_func = aw_func
        self._main_loop_task: asyncio.Task[None]|None = None

    def rz_pre_init(self) -> None:
        self._buffer = self.circuit.resolve_name(self._buffer)  # type: ignore[assignment]
        if not isinstance(self._buffer, _Buffer):
            raise TypeError(
                f"Check the buffer parameter; {self._buffer} is not a compatible block")

    async def _rest_time_delay(self) -> None:
        if self._rest_time > 0:
            await cancel_shield(asyncio.sleep(self._rest_time))

    async def _run_with_rest_time(self, value: t.Any) -> None:
        try:
            await self._aw_func(value)
        except asyncio.CancelledError:
            self.log_debug2("Task cancelled")
            await self._rest_time_delay()
            raise
        except Exception as err:
            err.add_note(f"Processed value was: {value!r}")
            # this task is awaited only when a new task waits for its start
            self.circuit.abort(err)
            await self._rest_time_delay()
            raise
        await self._rest_time_delay()

    async def _main_loop(self) -> None:
        """
        For each value from the buffer cancel the old task (if any)
        and create a task. Exit after buffer's shutdown.
        """
        buffer = self._buffer
        assert isinstance(buffer, _Buffer)  # @mypy
        shutdown = False
        task = None
        while True:
            try:
                value = await buffer.rz_buffer_get()
            except BufferShutDown:
                shutdown = True
            if task is not None:
                if task.done():
                    task.result()   # will re-raise task exception if any
                else:
                    if not shutdown:
                        task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        if asyncio.current_task().cancelling() > 0: # type: ignore[union-attr]
                            raise
                task = None
            if shutdown:
                return
            if buffer.rz_get_size():
                # a new value has arrived while we were awaiting the task
                continue
            if redzed.get_debug_level() >= 1:
                self.log_debug(
                    "Creating task: %s%s",
                    func_call_string(self._aw_func, (value,)),
                    " + rest time" if self._rest_time > 0.0 else "",
                    )
            task = asyncio.create_task(self._run_with_rest_time(value))

    def rz_start(self) -> None:
        self._main_loop_task = self.circuit.create_service(
            self._main_loop(), auto_cancel=False, name=f"{self}: main loop")

    async def rz_astop(self) -> None:
        task = self._main_loop_task
        if task is None or task.done():
            return
        try:
            await task
        except asyncio.CancelledError:
            # stop_timeout from the circuit runner
            task.cancel()
            await asyncio.sleep(0)
            if not task.done():
                try:
                    async with asyncio.timeout(self._rest_time):
                        await task
                except TimeoutError:
                    pass
            if not task.done():
                self.log_warning("The main task did not stop")
            raise
