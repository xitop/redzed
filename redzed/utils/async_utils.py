"""
Asynchronous utilities.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import typing as t

__all__ = ['BufferShutDown',  'cancel_shield']

try:
    BufferShutDown = asyncio.QueueShutDown      # Python 3.13+
except AttributeError:
    class BufferShutDown(Exception):            # type: ignore[no-redef]
        """asyncio.QueueShutDown substitute"""


_T = t.TypeVar("_T")


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
