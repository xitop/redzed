"""
The UNDEF singleton constant.
- - - - - -
Part of the redzed package.
# Docs: https://redzed.readthedocs.io/en/latest/
# Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['UNDEF', 'UndefType']

import enum
import typing as t


class DefaultEnumType(enum.EnumType):
    """Allow an UndefType() call without parameters."""
    # pylint: disable=keyword-arg-before-vararg
    def __call__(cls, value=None, *args, **kwargs):
        return super().__call__(value, *args, **kwargs)


# See PEP 484 - Support for singleton types in unions
class UndefType(enum.Enum, metaclass=DefaultEnumType):
    """Undefined output value"""
    UNDEF = None

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return '<UNDEF>'

    __str__ = __repr__


# Uninitialized circuit block's state value
UNDEF: t.Final = UndefType.UNDEF
