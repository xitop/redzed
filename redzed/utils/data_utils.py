"""
Small utilities.
"""
from __future__ import annotations

__all__ = [
    'check_async_coro', 'check_async_func', 'check_identifier', 'func_call_string',
    'is_multiple', 'tasks_are_eager', 'to_tuple']

import asyncio
from collections.abc import Callable, Mapping, Sequence
import inspect
import itertools
import logging
import typing as t

_logger = logging.getLogger(__package__)


def check_identifier(name: t.Any, msg_prefix: str) -> None:
    """Raise if *name* is not a valid identifier."""
    if not isinstance(name, str):
        raise TypeError(f"{msg_prefix} must be a string, got {name!r}")
    if not name:
        raise ValueError(f"{msg_prefix} cannot be an empty string")
    if not name.isidentifier():
        raise ValueError(f"{msg_prefix} must be a valid identifier, got '{name!r}'")


def is_multiple(arg: t.Any) -> bool:
    """
    Check if *arg* specifies multiple ordered items.

    The check is based on the type. The actual item count does not
    matter and can be any value including zero or one.
    A string or a byte-string is considered a single argument.
    """
    return not isinstance(arg, (str, bytes)) and isinstance(arg, Sequence)


_T_item = t.TypeVar("_T_item")
def to_tuple(args: _T_item|Sequence[_T_item]) -> tuple[_T_item, ...]:
    """Transform *args* to a tuple of items."""

    if isinstance(args, tuple):
        return args
    if is_multiple(args):
        assert isinstance(args, Sequence)   # @mypy
        return tuple(args)
    return t.cast(tuple[_T_item], (args,))


# must not touch *kwargs* # pylint: disable-next=dangerous-default-value
def func_call_string(
        func: Callable[..., t.Any]|None,
        args: Sequence[t.Any],
        kwargs: Mapping[str, t.Any] = {}
        ) -> str:
    """Convert args and kwargs to a printable string."""
    arglist = '(' + ', '.join(itertools.chain(
        (repr(a) for a in args),
        (f"{k}={v!r}" for k, v in kwargs.items()))) + ')'
    if func is None:
        return arglist
    return func.__name__ + arglist


def tasks_are_eager() -> bool:
    """
    Detect if eager tasks are enabled.

    Eager tasks (Python 3.12+) change the order of execution.
    The changed order may violate assumptions made in the
    code written before eager tasks were introduced.
    """
    if not hasattr(asyncio, "eager_task_factory"):
        return False
    flag = False
    async def test_task() -> None:
        nonlocal flag
        flag = True
    asyncio.create_task(test_task())
    return flag


def check_async_coro(arg: t.Any) -> None:
    """
    Check if arg is a coroutine object.

    Raise a TypeError with a descriptive message if it isn't.
    """
    if inspect.iscoroutine(arg):
        return
    if inspect.iscoroutinefunction(arg):
        received = f"an async function '{arg.__name__}'. Did you mean '{arg.__name__}()'?"
    else:
        received = repr(arg)
    raise TypeError(f"Expected a coroutine, but got {received}")


def check_async_func(arg: t.Any) -> None:
    """
    Check if *arg* is an async function.

    Raise a TypeError with a descriptive message if it isn't.
    """
    if inspect.iscoroutinefunction(arg):
        return
    if inspect.iscoroutine(arg):
        received = (f"a coroutine '{arg.__name__}()'. "
            + f"Did you mean '{arg.__name__}' without parentheses?")
    elif callable(arg):
        received = f"a non-async function/callable '{arg.__name__}'"
    else:
        received = repr(arg)
    raise TypeError(f"Expected an async function, but got {received}")
