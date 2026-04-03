"""
Definition of some common values.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['CircuitState', 'UNDEF', 'UndefType']

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


# Uninitialized circuit block's state or output,
# and a sentinel for general use
UNDEF: t.Final = UndefType.UNDEF


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
