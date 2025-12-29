"""
The circuit runner.
- - - - - -
Part of the redzed package.
# Docs: https://redzed.readthedocs.io/en/latest/
# Project home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['CircuitState', 'get_circuit', 'reset_circuit', 'run', 'unique_name']

import asyncio
from collections.abc import Coroutine, Iterable, MutableMapping, Sequence
import contextlib
import enum
import itertools
import logging
import signal
import time
import typing as t

from .block import Block, PersistenceFlags
from .cron_service import Cron
from .debug import get_debug_level
from .initializers import AsyncInitializer
from .formula_trigger import Formula, Trigger
from .signal_shutdown import TerminatingSignal
from .undef import UNDEF
from .utils import check_async_coro, check_identifier, tasks_are_eager, time_period

_logger = logging.getLogger(__package__)
_current_circuit: Circuit|None = None

# [attr-defined]: access to rz_xxx attrs is guarded by has_method() checks
# mypy: disable-error-code="attr-defined"


def get_circuit() -> Circuit:
    """Get the current circuit. Create one if it does not exist."""
    global _current_circuit     # pylint: disable=global-statement

    if _current_circuit is None:
        _current_circuit = Circuit()
    return _current_circuit


def reset_circuit() -> None:
    global _current_circuit     # pylint: disable=global-statement
    if _current_circuit is not None:
        if _current_circuit.get_state() not in [
                CircuitState.UNDER_CONSTRUCTION, CircuitState.CLOSED]:
            raise RuntimeError("Cannot reset running circuit")
        # pylint: disable=protected-access
        # break some reference cycles
        _current_circuit._blocks.clear()
        _current_circuit._triggers.clear()
        _current_circuit._errors.clear()
        _current_circuit = None


def unique_name(prefix: str = 'auto') -> str:
    """Add a numeric suffix to make the name unique."""
    return get_circuit().rz_unique_name(prefix)


class CircuitState(enum.IntEnum):
    """
    Circuit state.

    The integer value may only increase during the circuit's life-cycle.
    """

    UNDER_CONSTRUCTION = 0  # being built, the runner is not started yet
    INIT_CIRCUIT = 1        # the runner initializes itself
    INIT_BLOCKS = 2         # runner is started, now initializing blocks and triggers
    RUNNING = 3             # the circuit is running
    SHUTDOWN = 4            # shutting down
    CLOSED = 5              # runner has exited


class _TerminateTaskGroup(Exception):
    """Exception raised to terminate a task group."""


@contextlib.contextmanager
def error_debug(item: Block|Formula|Trigger, suppress_error: bool = False) -> t.Iterator[None]:
    """Add a note to raised exception -or- log and suppress exception."""
    try:
        yield None
    except Exception as err:
        if not suppress_error:
            err.add_note(f"This {type(err).__name__} occurred in {item}")
            raise
        # errors should be suppressed only during the shutdown & cleanup
        _logger.error("[Circuit] %s: Suppressing %s: %s", item, type(err).__name__, err)


class Circuit:
    """
    A container of all blocks.

    In this implementation, circuit blocks can be added, but not removed.
    """

    def __init__(self) -> None:
        self._state = CircuitState.UNDER_CONSTRUCTION
        self._state_change: asyncio.Event|None = None  # used by .reached_state
        self._blocks: dict[str, Block|Formula] = {}
            # all Blocks and Formulas belonging to this circuit stored by name
        self._triggers: list[Trigger] = []      # all triggers belonging to this circuit
        self._errors: list[Exception] = []      # exceptions occurred in the runner
        self.rz_persistent_dict: MutableMapping[str, t.Any]|None = None
            # persistent state data back-end
        self.rz_persistent_ts: float|None = None
            # timestamp of persistent data (Unix clock)
        self._start_ts: float|None = None
            # runner's start timestamp (monotonic clock)
        self._auto_cancel_tasks: set[asyncio.Task[t.Any]] = set()
            # interval for checkpointing
        self._sync_time = 250.0

    def log_debug1(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message if debugging is enabled."""
        if get_debug_level() >= 1:
            _logger.debug("[Circuit] "+ msg, *args, **kwargs)

    def log_debug2(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message if verbose debugging is enabled."""
        if get_debug_level() >= 2:
            _logger.debug("[Circuit] "+ msg, *args, **kwargs)

    def log_info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with _INFO_ priority."""
        _logger.info("[Circuit] "+ msg, *args, **kwargs)

    def log_warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with _WARNING_ priority."""
        _logger.warning("[Circuit] "+ msg, *args, **kwargs)

    def log_error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with _ERROR_ priority."""
        _logger.error("[Circuit] "+ msg, *args, **kwargs)

    def _log_debug2_blocks(
            self,
            msg: str,
            *args: Sequence[Block]|Sequence[Formula]|Sequence[Trigger]
            ) -> None:
        """Log a debug message with a block count and a block name list."""
        if get_debug_level() < 2:
            return
        parts = []
        for ilist in args:
            if (cnt := len(ilist)) == 0:
                continue
            itype = type(ilist[0])
            plural = "" if cnt == 1 else "s"
            if issubclass(itype, Block):
                names = ', '.join(b.name for b in ilist)    # type: ignore[union-attr]
                parts.append(f"{cnt} block{plural}: {names}")
            elif itype is Formula:
                # issubclass is not needed, because Formula and Trigger are final classes
                names = ', '.join(f.name for f in ilist)    # type: ignore[union-attr]
                parts.append(f"{cnt} formula{plural}: {names}")
            elif itype is Trigger:
                parts.append(f"{cnt} trigger{plural}")
        if parts:
            _logger.debug("[Circuit] %s. Processing %s", msg, "; ".join(parts))

    # --- circuit components storage ---

    def rz_add_item(self, item: Block|Formula|Trigger) -> None:
        """Add a circuit item."""
        self._check_not_started()
        if isinstance(item, Trigger):
            self._triggers.append(item)
            return
        if not isinstance(item, (Block, Formula)):
            raise TypeError(
                f"Expected a circuit component (Block/Formula/Trigger), but got {item!r}")
        if item.name in self._blocks:
            raise ValueError(f"Duplicate name '{item.name}'")
        self._blocks[item.name] = item

    _Block = t.TypeVar("_Block", bound = Block)
    @t.overload
    def get_items(self, btype: type[Formula]) -> Iterable[Formula]: ...
    @t.overload
    def get_items(self, btype: type[Trigger]) -> Iterable[Trigger]: ...
    @t.overload
    def get_items(self, btype: type[_Block]) -> Iterable[_Block]: ...
    def get_items(
            self, btype: type[Formula|Trigger|Block]) -> Iterable[Formula|Trigger|Block]:
        """
        Return an iterable of circuit components of selected type *btype*.

        The returned iterable might be a generator.
        """
        # no issubclass(), because Trigger is a "final" class
        if btype is Trigger:
            return self._triggers
        if not isinstance(btype, type) or not issubclass(btype, (Block, Formula)):
            raise TypeError(f"Expected a circuit component type, got {btype!r}")
        return (item for item in self._blocks.values() if isinstance(item, btype))

    @t.overload
    def resolve_name(self, ref: Block) -> Block: ...
    @t.overload
    def resolve_name(self, ref: Formula) -> Formula: ...
    @t.overload
    def resolve_name(self, ref: str) -> Block|Formula: ...
    def resolve_name(self, ref: Block|Formula|str) -> Block|Formula:
        """
        Resolve a reference by name if necessary.

        If *ref* is a string, return circuit's block or formula with that name.
        Raise a KeyError when not found. Special case during initialization:
        create internal blocks on demand.

        Return *ref* unchanged if it is already a valid block or formula object.
        """
        if isinstance(ref, (Block, Formula)):
            return ref  # name already resolved
        if not isinstance(ref, str):
            raise TypeError(f"Expected a name (string), got {ref!r}")
        try:
            return self._blocks[ref]
        except KeyError:
            if self._state <= CircuitState.INIT_BLOCKS:
                if ref == '_cron_local':
                    return Cron(ref, utc=False, comment="Time scheduler (local time)")
                if ref == '_cron_utc':
                    return Cron(ref, utc=True, comment="Time scheduler (UTC time)")
            raise KeyError(f"No block or formula named '{ref}' found") from None

    def rz_unique_name(self, prefix: str) -> str:
        """Add a numeric suffix to make the name unique."""
        check_identifier(prefix, "Block/Formula name prefix")
        delim = '' if prefix.endswith('_') else '_'
        num = sum(1 for n in self._blocks if n.startswith(prefix))
        while True:
            if (name := f"{prefix}{delim}{num}") not in self._blocks:
                return name
            num += 1
        # not reached

    # --- State management ---

    def get_state(self) -> CircuitState:
        """Get the circuit's state."""
        return self._state

    def _set_state(self, newstate: CircuitState) -> None:
        """Set the circuit's state."""
        if newstate <= self._state:
            # This is not allowed, but in the same time, it's not an error. Usually
            # it happens when there was an abort(), but the runner wasn't notified yet.
            return
        self._state = newstate
        self.log_debug2("State: %s", newstate.name)

        if self._state_change is not None:
            self._state_change.set()
            self._state_change = None

    async def reached_state(self, state: CircuitState) -> bool:
        """
        Async synchronization tool.

        Wait until the DESIRED OR HIGHER state is reached.
        """
        if not isinstance(state, CircuitState):
            raise TypeError(f"Expected CircuitState, got {state!r}")
        while self._state < state:
            if self._state_change is None:
                self._state_change = asyncio.Event()
            await self._state_change.wait()
        return self._state == state

    def _check_not_started(self) -> None:
        """Raise an error if the circuit runner has started already."""
        if self._state == CircuitState.CLOSED:
            # A circuit may be closed before start (see shutdown),
            # let's use this message instead of the one below.
            raise RuntimeError("The circuit was closed")
        # allow adding special blocks in the INIT_CIRCUIT state
        if self._state > CircuitState.INIT_CIRCUIT:
            raise RuntimeError("Not allowed after the start")

    def after_shutdown(self) -> bool:
        """Test if we are past the shutdown() call."""
        return self._state >= CircuitState.SHUTDOWN

    async def _checkpointing_service(self, blocks: Sequence[Block]) -> None:
        while self._state <= CircuitState.RUNNING:
            await asyncio.sleep(self._sync_time)
            now = time.time()
            if self._state is CircuitState.RUNNING:
                for blk in blocks:
                    self.save_persistent_state(blk, now)

    def set_persistent_storage(
            self,
            persistent_dict: MutableMapping[str, t.Any]|None,
            *,
            sync_time: float|str|None = None
            ) -> None:
        """Setup the persistent state data storage."""
        self._check_not_started()
        self.rz_persistent_dict = persistent_dict
        if sync_time is not None:
            self._sync_time = time_period(sync_time)

    def _check_persistent_storage(self) -> None:
        """Check persistent state related settings."""
        storage = self.rz_persistent_dict
        ps_blocks = [blk for blk in self.get_items(Block) if blk.rz_persistence]
        if storage is None:
            if ps_blocks:
                self.log_warning("No data storage, disabling state persistence")
            for blk in ps_blocks:
                blk.rz_persistence = PersistenceFlags(0)
            return
        # clear the unused items
        used_keys = {pblk.rz_key for pblk in ps_blocks}
        for key in list(storage.keys()):
            if key not in used_keys:
                self.log_debug2("Removing unused persistent state for '%s'", key)
                del storage[key]
        # start checkpointing if necessary
        ch_blocks = [
            blk for blk in self.get_items(Block)
            if blk.rz_persistence & PersistenceFlags.INTERVAL]
        if ch_blocks:
            self.create_service(
                self._checkpointing_service(ch_blocks), name="Checkpointing service")

    # --- init/shutdown helpers ---

    def _init_block_core(self, blk: Block) -> t.Iterator[AsyncInitializer]:
        """
        Initialize with available initializers.

        Run sync initializers immediately. Yield async initializers
        for further processing.

        Persistent state is handled elsewhere.
        """
        for init in blk.rz_initializers:
            if not blk.is_undef():
                return
            if isinstance(init, AsyncInitializer):
                yield init
            else:
                init.apply_to(blk)
        if blk.is_undef() and blk.has_method('rz_init_default'):
            blk.log_debug2("Calling the built-in default initializer")
            blk.rz_init_default()

    def init_block_sync(self, blk: Block) -> None:
        """Initialize a Block excluding async initializers."""
        for _ in self._init_block_core(blk):
            pass

    async def init_block_async(self, blk: Block) -> None:
        """Initialize a Block including async initializers."""
        for initializer in self._init_block_core(blk):
            task = asyncio.create_task(
                initializer.async_apply_to(blk),
                name=f"initializer {type(initializer).__name__} for block '{blk.name}'")
            blk.rz_set_inittask(task)
            try:
                await task
            except asyncio.CancelledError:
                # [union-attr]: asyncio.current_task() cannot return None here
                if asyncio.current_task().cancelling() > 0: # type: ignore[union-attr]
                    raise

    async def _init_blocks(self, blocks: Sequence[Block]) -> None:
        """
        Initialize multiple logic blocks.

        Run async initializations concurrently.
        """
        # Init from value provided by initializers (specified with initial=... or built-in)
        uninitialized = [blk for blk in blocks if blk.is_undef()]
        sync_blocks: list[Block] = []
        async_blocks: list[Block] = []
        for blk in uninitialized:
            async_init = any(isinstance(init, AsyncInitializer) for init in blk.rz_initializers)
            (async_blocks if async_init else sync_blocks).append(blk)
        if sync_blocks:
            self._log_debug2_blocks(
                "Initializing blocks having sync initializers only", sync_blocks)
            for blk in sync_blocks:
                self.init_block_sync(blk)
        if async_blocks:
            self._log_debug2_blocks(
                "Initializing blocks having some async initializers", async_blocks)
            async with asyncio.TaskGroup() as tg:
                for blk in async_blocks:
                    tg.create_task(self.init_block_async(blk))
        # final check
        for blk in blocks:
            if blk.is_undef():
                raise RuntimeError(f"Block '{blk.name}' was not initialized")

    def save_persistent_state(self, blk: Block, now: float|None = None) -> None:
        """
        Save persistent state.

        It is assumed the block has the persistent state feature
        enabled and the storage is ready.
        """
        assert self.rz_persistent_dict is not None
        if blk.is_undef():
            blk.log_debug2("Not saving undefined state")
        if now is None:
            now = time.time()
        try:
            if (state := blk.rz_export_state()) is UNDEF:
                blk.error("Exported state was <UNDEF>")
                return
            self.rz_persistent_dict[blk.rz_key] = [state, now]
        except Exception as err:
            blk.log_error("Saving state failed with %r", err)

    async def _shutdown_block_async(self, blk: Block) -> None:
        """Shutdown a Block."""
        with error_debug(blk, suppress_error=True):
            async with asyncio.timeout(blk.rz_stop_timeout):
                await blk.rz_astop()

    # --- runner ---

    def runtime(self) -> float:
        """
        Return seconds since runner's start.

        Return 0.0 if it hasn't started yet.
        """
        return 0.0 if self._start_ts is None else time.monotonic() - self._start_ts

    async def _runner_init(self) -> None:
        """Run the circuit during the initialization phase."""
        self._set_state(CircuitState.INIT_CIRCUIT)
        await asyncio.sleep(0)  # allow reached_state() synchronization
        if self.after_shutdown():
            # It looks like a supporting task has failed immediately after the start
            return

        pe_blocks = [blk for blk in self.get_items(Block) if blk.has_method('rz_pre_init')]
        pe_formulas = list(self.get_items(Formula))
        pe_triggers = list(self.get_items(Trigger))
        self._log_debug2_blocks("Pre-initializing", pe_blocks, pe_formulas, pe_triggers)
        for pe in itertools.chain(pe_blocks, pe_formulas, pe_triggers):
            assert isinstance(pe, (Block, Formula, Trigger))    # @mypy
            with error_debug(pe):
                # union-attr: checked with .has_method()
                pe.rz_pre_init()   # type: ignore[union-attr]

        self._set_state(CircuitState.INIT_BLOCKS)
        await asyncio.sleep(0)
        await self._init_blocks(list(self.get_items(Block)))

        start_blocks = [blk for blk in self.get_items(Block) if blk.has_method('rz_start')]
        start_formulas = list(self.get_items(Formula))
        start_triggers = list(self.get_items(Trigger))
        self._log_debug2_blocks("Starting", start_formulas, start_triggers, start_blocks)
        # starting blocks after formulas and triggers
        for start in itertools.chain(start_formulas, start_triggers, start_blocks):
            assert isinstance(start, (Block, Formula, Trigger))     # @mypy
            with error_debug(start):
                # union-attr: checked with .has_method()
                start.rz_start()   # type: ignore[union-attr]

        if self.rz_persistent_dict is not None:
            # initial checkpoints
            ch_blocks = [
                blk for blk in self.get_items(Block)
                if blk.rz_persistence & (PersistenceFlags.EVENT | PersistenceFlags.INTERVAL)]
            if ch_blocks:
                now = time.time()
                for blk in ch_blocks:
                    self.save_persistent_state(blk, now)

    async def _runner_shutdown(self) -> None:
        """Run the circuit during the shutdown."""
        if self.rz_persistent_dict is not None:
            # save the state first, because stop may invalidate the state information
            ps_blocks = [blk for blk in self.get_items(Block) if blk.rz_persistence]
            if ps_blocks:
                self._log_debug2_blocks("Saving persistent state", ps_blocks)
                now = time.time()
                for blk in ps_blocks:
                    self.save_persistent_state(blk, now)

        stop_triggers = list(self.get_items(Trigger))
        stop_blocks = [blk for blk in self.get_items(Block) if blk.has_method('rz_stop')]
        if stop_blocks:
            self._log_debug2_blocks("Stopping (sync)", stop_triggers, stop_blocks)
            for stop in itertools.chain(stop_triggers, stop_blocks):
                assert isinstance(stop, (Block, Trigger))       # @mypy
                with error_debug(stop, suppress_error=True):
                    # union-attr: checked with .has_method()
                    stop.rz_stop()  # type: ignore[union-attr]

        if self._auto_cancel_tasks:
            self.log_debug2("Cancelling %d service task(s)")
            for task in self._auto_cancel_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.sleep(0)
            for task in self._auto_cancel_tasks:
                if not task.done():
                    self.log_warning("Canceled service task %s did not terminate", task)

        stop_blocks = [
            blk for blk in self.get_items(Block)
            if blk.has_method('rz_astop', async_method=True)]
        if stop_blocks:
            self._log_debug2_blocks("Stopping (async)", stop_blocks)
            async with asyncio.TaskGroup() as tg:
                for blk in stop_blocks:
                    tg.create_task(self._shutdown_block_async(blk))

        close_blocks = [blk for blk in self.get_items(Block) if blk.has_method('rz_close')]
        if close_blocks:
            self._log_debug2_blocks("Closing", close_blocks)
            for close in close_blocks:
                with error_debug(close, suppress_error=True):
                    close.rz_close()

    async def _runner_core(self) -> t.NoReturn:
        """
        Run the circuit until shutdown/abort, then clean up.

        _runner_core() never exits normally without an exception.
        It must be cancelled to switch from running to shutting down.

        Please note that the cleanup could take some time depending
        on the outputs' .rz_stop_timeout values.

        When the runner terminates, it cannot be invoked again.
        """
        if self._state == CircuitState.CLOSED:
            raise RuntimeError("Cannot restart a closed circuit.")
        if self._state != CircuitState.UNDER_CONSTRUCTION:
            raise RuntimeError("The circuit is already running.")
        if not self._blocks:
            raise RuntimeError("The circuit is empty")
        if tasks_are_eager():
            self.log_debug2("Eager asyncio tasks detected")
        self._check_persistent_storage()
        self._start_ts = time.monotonic()
        try:
            try:
                await self._runner_init()
            except Exception as err:
                self.abort(err)
            else:
                # There might be errors reported with abort().
                # In such case the state has been set to SHUTDOWN.
                # _set_state(RUNNING) will be silently ignored.
                self._set_state(CircuitState.RUNNING)
            # wait until cancelled from the task group; possible causes:
            #  1. shutdown() or abort()
            #  2. failed supporting task (this includes unexpected termination)
            #  3. cancellation of the task group itself
            await asyncio.Future()
        except asyncio.CancelledError:
            # will be re-raised at the end if there won't be other exceptions
            pass
        # cancellation causes 2 and 3 do not modify the state
        if not self.after_shutdown():
            self._set_state(CircuitState.SHUTDOWN)
            await asyncio.sleep(0)
        try:
            await self._runner_shutdown()
        except Exception as err:
            # If an exception is propagated from _runner_shutdown, it is probably a bug.
            # Calling abort is not necessary when shutting down, but the call will log
            # and register the exception to be included in the final ExceptionGroup.
            self.abort(err)
        self._set_state(CircuitState.CLOSED)

        if self._errors:
            raise ExceptionGroup("_runner_core() errors", self._errors)
        raise asyncio.CancelledError()

    # --- abort/shutdown ---

    def abort(self, err: Exception) -> None:
        """
        Abort the circuit runner due to an error.

        abort() is necessary only when an exception isn't propagated
        to the runner.
        """
        if not isinstance(err, Exception):
            # one more reason to abort
            err = TypeError(f'abort(): expected an exception, got {err!r}')
        if err in self._errors:
            # the same error may be reported from several places
            return
        self._errors.append(err)
        if self.after_shutdown():
            self.log_error("Unhandled error during shutdown: %r", err)
        else:
            self.log_warning("Aborting due to an exception: %r", err)
            self.shutdown()

    def shutdown(self) -> None:
        """
        Stop the runner if it was started.

        Prevent the runner from starting if it wasn't started yet.
        """
        if self.after_shutdown():
            return
        if self._state == CircuitState.UNDER_CONSTRUCTION:
            self._set_state(CircuitState.CLOSED)
            return
        self._set_state(CircuitState.SHUTDOWN)
        # The shutdown monitor will be awakened and exits with an error. The task
        # group will detect it and cancel the runner and its supporting tasks.

    async def watchdog(
            self,
            coro: Coroutine[t.Any, t.Any, t.Any],
            immediate_start: bool,
            name: str|None
            ) -> None:
        """
        Detect *coro* termination before shutdown and treat it as an error. Add logging.

        This is a low-level function for create_service.
        """
        this_task = asyncio.current_task()
        assert this_task is not None    # @mypy
        if name is None:
            name = this_task.get_name()
        elif this_task.get_name() != name:
            this_task.set_name(name)
        longname = f"Task '{name}' running '{coro.__name__}'"
        if not immediate_start:
            self.log_debug2("%s waiting for RUNNING state", longname)
            if not await self.reached_state(CircuitState.RUNNING):
                self.log_debug1("%s not started", longname)
                coro.close()    # won't be awaited; prevent a warning about that
                # Failed start! The return value does not matter now.
                # No abort() here, because this is not an error, it's a consequence.
                return
        self.log_debug1("%s started", longname)
        try:
            await coro  # return value of a service is ignored
        except asyncio.CancelledError:
            if self.after_shutdown():
                self.log_debug1("%s was cancelled", longname)
                raise
            err = RuntimeError(f"{longname} was cancelled before shutdown")
            self.abort(err)
            raise err from None
        except Exception as err:
            err.add_note(f"Error occurred in {longname}")
            self.abort(err)
            raise
        if self.after_shutdown():
            self.log_debug1("%s terminated", longname)
            return
        exc = RuntimeError(f"{longname} terminated before shutdown")
        self.abort(exc)
        raise exc

    def create_service(
            self, coro: Coroutine[t.Any, t.Any, t.Any],
            immediate_start: bool = False,
            auto_cancel: bool = True,
            **task_kwargs
            ) -> asyncio.Task[None]:
        """Create a service task for the circuit."""
        if self.after_shutdown():
            raise RuntimeError("Cannot create a service after shutdown")
        check_async_coro(coro)
        # Python 3.12 and 3.13 only: Eager tasks start to run before their name is set.
        # As a workaround we tell the watchdog wrapper the name.
        task = asyncio.create_task(
            self.watchdog(coro, immediate_start, task_kwargs.get('name')), **task_kwargs)
        if auto_cancel:
            self._auto_cancel_tasks.add(task)
        # mark exceptions as consumed, because they were reported with abort
        task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
        return task

    async def _shutdown_monitor(self) -> t.NoReturn:
        """
        Helper task: exit with an error when shutdown starts.

        The failure of the shutdown monitor task cancels the task group.
        (if it wasn't cancelling already). The _TerminateTaskGroup
        error will be filtered out.
        """
        await self.reached_state(CircuitState.SHUTDOWN)
        raise _TerminateTaskGroup()

    async def rz_runner(self) -> None:
        """Run the circuit."""
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._shutdown_monitor(), name="Shutdown monitor")
            tg.create_task(self._runner_core(), name="Circuit runner core")
        raise _TerminateTaskGroup()


_ET = t.TypeVar("_ET", bound=BaseException)

def leaf_exceptions(group: BaseExceptionGroup[_ET]) -> list[_ET]:
    """
    Return a flat list of all 'leaf' exceptions.

    Not using techniques from PEP-785, but leaving tracebacks unmodified.
    """
    result = []
    for exc in group.exceptions:
        if isinstance(exc, BaseExceptionGroup):
            result.extend(leaf_exceptions(exc))
        else:
            result.append(exc)
    return result


async def run(*coroutines: Coroutine[t.Any, t.Any, t.Any], catch_sigterm: bool = True) -> None:
    """
    The main entry point(). Run the circuit together with supporting coroutines.

    If errors occur, raise an exception group with all exceptions.
    """
    with TerminatingSignal(signal.SIGTERM) if catch_sigterm else contextlib.nullcontext():
        circuit = get_circuit()
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(circuit.rz_runner(), name="Circuit runner")
                task_cnt = len(coroutines)
                for i, coro in enumerate(coroutines, start=1):
                    name = "Supporting task"
                    if task_cnt > 1:
                        name += f" {i}/{task_cnt}"
                    tg.create_task(
                        circuit.watchdog(coro, immediate_start=True, name=name), name=name)
        except ExceptionGroup as eg:
            exceptions: list[Exception] = []
            for exc in leaf_exceptions(eg):
                if not isinstance(exc, _TerminateTaskGroup) and exc not in exceptions:
                    exceptions.append(exc)
            if exceptions:
                raise ExceptionGroup("Circuit runner exceptions", exceptions) from None
    circuit.log_debug2("Terminated normally")
