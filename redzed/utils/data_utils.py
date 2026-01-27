"""
Small utilities.
"""
from __future__ import annotations

__all__ = [
    'check_identifier', 'func_name', 'func_call_string',
    'is_multiple', 'tasks_are_eager', 'to_tuple']

import asyncio
from collections.abc import Callable, Mapping, Sequence
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
        raise ValueError(f"{msg_prefix} must be a valid identifier, got '{name}'")


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


def func_name(func: Callable[..., t.Any]) -> str:
    """Return the name of a callable."""
    if not callable(func):
        raise TypeError(f"{func!r} is not callable")
    if (name := getattr(func, '__name__', None)) is not None:
        return name
    # callable objects with __call__ do not have a __name__
    if not isinstance(func, type) and (hasattr(ftype := type(func), '__call__')):
        return f'{ftype.__name__}.__call__'
    # fail-safe default, though there is no such type of callable
    return ftype.__name__


def func_call_string(
        func: Callable[..., t.Any]|None,
        args: Sequence[t.Any],
        kwargs: Mapping[str, t.Any]|None = None
        ) -> str:
    """Convert args and kwargs to a printable string."""
    agen = (repr(a) for a in args)
    gen = itertools.chain(agen, (f"{k}={v!r}" for k, v in kwargs.items())) if kwargs else agen
    arglist = f"({', '.join(gen)})"
    return arglist if func is None else func_name(func) + arglist


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
