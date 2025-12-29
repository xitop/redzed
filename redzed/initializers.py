"""
Block initializers.
- - - - - -
Part of the redzed package.
# Docs: https://redzed.readthedocs.io/en/latest/
# Project home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = [
    'AsyncInitializer', 'SyncInitializer',
    'InitFunction', 'InitTask', 'InitValue', 'InitWait', 'RestoreState']

import asyncio
from collections.abc import Callable, Awaitable
import time
import typing as t

from . import block
from .undef import UNDEF, UndefType
from .utils import check_async_func, time_period


_LONG_TIMEOUT = 60      # threshold for a "long timeout" debug message


class SyncInitializer:
    """
    Logic block initializers are used as initial=... arguments.

    A block can have multiple initializers. They will be called
    in given order until the first one succeeds.
    """

    def __init__(self) -> None:
        # Keep track in order to prevent repeated application of the same initializer.
        # It could happen when a block receives an event during initialization.
        self._applied = False

    @property
    def type_name(self) -> str:
        return type(self).__name__

    def _get_init(self) -> t.Any:
        """Return the initial value or UNDEF if not available."""
        raise NotImplementedError()

    def apply_to(self, blk: block.Block) -> None:
        """
        Apply this initializer to a logic block *blk*.

        Log exceptions, but do not propagate them. An error condition
        is when a block doesn't get proper initialization after using
        ALL initializers.
        """
        if self._applied:
            return
        self._applied = True
        try:
            init_value = self._get_init()
        except Exception as err:
            blk.log_error(
                "%s: could not get the initialization value: %r", self.type_name, err)
            return
        blk.log_debug2("%s: init value: %r", self.type_name, init_value)
        if init_value is UNDEF:
            return
        try:
            blk.rz_init(init_value)    # type: ignore[attr-defined]
        except Exception as err:
            blk.log_error(
                "%s could not apply the initialization value: %r", self.type_name, err)
            return


class InitFunction(SyncInitializer):
    """
    Initialize with a calculated value.
    """

    def __init__(self, func: Callable[..., t.Any], *args: t.Any) -> None:
        """
        Usage: InitFunction(func, arg1, arg2, ...)
        Use functools.partial to pass keyword arguments.
        """
        super().__init__()
        if not callable(func):
            raise TypeError(f"{self.type_name}: {func!r} is not a function")
        self._func = func
        self._args = args

    def _get_init(self) -> t.Any:
        return self._func(*self._args)


class InitValue(SyncInitializer):
    """
    Initialize with a literal value.
    """

    def __init__(self, value: t.Any) -> None:
        super().__init__()
        if value is UNDEF:
            raise ValueError("<UNDEF> is not a valid initialization value.")
        self._value = value

    def _get_init(self) -> t.Any:
        return self._value


_CHECKPOINTS = [None, 'event', 'interval']

class RestoreState(SyncInitializer):
    """Restore from saved state."""

    def __init__(
            self,
            checkpoints: None|t.Literal['event', 'interval'] = None,
            expiration: None|float|str = None
            ) -> None:
        super().__init__()
        if not checkpoints in _CHECKPOINTS:
            raise ValueError(
                "Parameter checkpoints must be one of: "
                + f"{', '.join(repr(ch) for ch in _CHECKPOINTS)}")
        self.rz_checkpoints = checkpoints
        self._expiration = time_period(expiration, passthrough=None)

    def _get_init(self) -> t.Any:
        pass

    def _get_state(self, blk: block.Block) -> t.Any:
        storage = blk.circuit.rz_persistent_dict
        assert storage is not None
        try:
            state, timestamp = storage[blk.rz_key]
        except KeyError:
            blk.log_debug2("No saved state was found")
            return UNDEF
        except Exception as err:
            blk.log_warning("State retrieval error: %r", err)
            return UNDEF
        if self._expiration is None:
            return state
        age = time.time() - timestamp
        if age < 0:
            blk.log_error(
                "The timestamp of saved data is in the future, check the system time")
        elif age > self._expiration:
            blk.log_debug2("The saved state has expired")
            return UNDEF
        return state

    def apply_to(self, blk: block.Block) -> None:
        if self._applied:
            return
        self._applied = True
        if not blk.rz_persistence:
            return
        try:
            init_state = self._get_state(blk)
        except Exception as err:
            blk.log_error(
                "%s could not get the initialization value: %r", self.type_name, err)
            return
        if init_state is UNDEF:
            # a debug message was logged in _get_state
            return
        blk.log_debug2("%s: saved state: %r", self.type_name, init_state)
        try:
            blk.rz_restore_state(init_state)       # type: ignore[attr-defined]
        except Exception as err:
            blk.log_error(
                "%s could not apply the initialization value: %r", self.type_name, err)
            return


class AsyncInitializer:
    """
    Asynchronous initializer.
    """

    def __init__(self, timeout: float|str):
        self._applied = False
        self._timeout = time_period(timeout, passthrough=None)

    @property
    def type_name(self) -> str:
        return type(self).__name__

    async def _async_get_init(self) -> t.Any:
        """Async version of _get_init."""
        raise NotImplementedError()

    async def async_apply_to(self, blk: block.Block) -> None:
        """Async version of apply(). Do not overwrite existing state."""
        if self._applied:
            return
        self._applied = True
        if self._timeout >= _LONG_TIMEOUT:
            blk.log_debug2("%s has a long timeout of %.1f secs", self.type_name, self._timeout)
        try:
            init_value = await self._async_get_init()
        except TimeoutError:
            blk.log_debug1("%s timed out", self.type_name)
            return
        except Exception as err:
            blk.log_error("Skipping failed %s. Error: %r", self.type_name, err)
            return
        blk.log_debug2("%s: init value: %r", self.type_name, init_value)
        if init_value is UNDEF:
            return
        if not blk.is_undef():
            blk.log_debug1(
                "%s: not applying the init value, because the block "
                + "has been initialized in the meantime", self.type_name)
            return
        blk.rz_init(init_value)    # type: ignore[attr-defined]


class InitTask(AsyncInitializer):
    """
    Initialize with a value calculated by a coroutine.
    """

    def __init__(
            self,
            coro_func: Callable[..., Awaitable[t.Any]],
            *args: t.Any,
            timeout: float|str = 10.0
            ) -> None:
        """Similar to InitFunction, but asynchonous."""
        check_async_func(coro_func)
        super().__init__(timeout)
        self._corofunc = coro_func
        self._args = args

    async def _async_get_init(self) -> t.Any:
        async with asyncio.timeout(self._timeout):
            return await self._corofunc(*self._args)


class InitWait(AsyncInitializer):
    """
    Passively wait for initialization by an event.
    """

    async def _async_get_init(self) -> UndefType:
        return await asyncio.sleep(self._timeout, result=UNDEF)
