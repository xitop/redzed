"""
Asynchronous utilities.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import typing as t

__all__ = ['BufferShutDown',  'cancel_shield', 'MsgSync']

try:
    BufferShutDown = asyncio.QueueShutDown      # Python 3.13+
except AttributeError:
    class BufferShutDown(Exception):            # type: ignore[no-redef]
        """asyncio.QueueShutDown substitute"""


_T = t.TypeVar("_T")
_MISSING = object()

class MsgSync(t.Generic[_T]):
    """
    Task synchronization based on sending messages of type _T.

    The count of unread message is always either zero or one,
    because messages are not queued. A new message replaces
    the previous unread one, if any.

    An existing unread message is available immediately.
    Otherwise the recipient must wait and will be awakened when
    a new message arrives. Reading a message consumes it,
    so each message can reach only one receiver.
    """

    def __init__(self) -> None:
        self._msg: t.Any = _MISSING
        self._shutdown = False
        self._has_data = asyncio.Event()    # valid before shutdown
        self._draining = False              # valid after shutdown

    def shutdown(self) -> None:
        """
        Disallow sending immediately. Disallow receiving after the MsgSync gets empty.

        Calls to .send() will raise BufferShutDown.

        If a message was sent before shutdown and is waiting, it can be
        normally received before the receiver shuts down too. After
        the shutdown all blocked callers will be unblocked with BufferShutDown.
        Calls to .recv() will raise BufferShutDown as well.
        """
        self._shutdown = True
        self._draining = self._has_data.is_set()
        if not self._draining:
            # wakeup all waiters
            self._has_data.set()

    def is_shutdown(self) -> bool:
        """Check if the buffer was shut down."""
        return self._shutdown

    def send(self, msg: _T) -> None:
        """
        Send a message to one receiver.

        If the previously sent message hasn't been received yet,
        the new message overwrites it.
        """
        if self._shutdown:
            raise BufferShutDown("The buffer was shut down")
        self._msg = msg
        self._has_data.set()

    def clear(self) -> None:
        """Remove the waiting message."""
        if self._shutdown:
            self._draining = False
        else:
            self._has_data.clear()
        self._msg = _MISSING

    def has_data(self) -> bool:
        """Return True only if there is a waiting message."""
        return self._draining if self._shutdown else self._has_data.is_set()

    async def _recv(self) -> _T:
        """Receive (consume) a message."""
        while not self._has_data.is_set():
            await self._has_data.wait()
        if not self._shutdown:
            self._has_data.clear()
        elif self._draining:
            self._draining = False
        else:
            raise BufferShutDown("The buffer was shut down")
        msg, self._msg = self._msg, _MISSING
        return t.cast(_T, msg)

    async def recv(self, timeout: float | None = None, default: t.Any = _MISSING) -> t.Any:
        """
        Receive a message with optional timeout.

        If a message is not available, wait until it arrives.

        If a timeout [seconds] is given, return the default value
        if no message is received before the timeout period elapses.
        Without a default, raise the TimeoutError.
        """
        if timeout is None:
            return await self._recv()
        try:
            async with asyncio.timeout(timeout):
                return await self._recv()
        except TimeoutError:
            if default is not _MISSING:
                return default
            raise


async def cancel_shield(aw: Awaitable[_T]) -> _T:
    """
    Shield from cancellation while aw is awaited.

    Any pending CancelledError is raised when aw is finished.
    """
    task = asyncio.ensure_future(aw)
    cancel_exc = None
    while True:
        try:
            retval = await asyncio.shield(task)
        except asyncio.CancelledError as err:
            if task.done():
                raise
            cancel_exc = err
        else:
            break
    if cancel_exc is not None:
        try:
            raise cancel_exc
        finally:
            # break the reference loop
            cancel_exc = None
    return retval
