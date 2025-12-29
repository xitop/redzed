"""
Test the Memory block.
"""

import pytest

import redzed

from .utils import mini_init


def test_basic(circuit):
    """Basic functionality."""
    INITIAL = 'default_value'
    mem = redzed.Memory('Cell', initial=INITIAL)
    assert mem.get() is redzed.UNDEF
    mini_init(circuit)

    assert mem.get() == INITIAL
    mem.event('store', 3.14)
    assert mem.get() == 3.14


def test_noinit(circuit):
    """Missing initial parameter."""
    redzed.Memory('no_init')
    with pytest.raises(RuntimeError, match='not initialized'):
        mini_init(circuit)


def test_events(circuit):
    """Memories support only the store event."""
    mem = redzed.Memory('Cell', initial=None)
    mini_init(circuit)

    assert mem.event('store', 1) is True
    assert mem.get() == 1
    assert mem.event('store', 2, junk=-1) is True   # extra keys silently ignored
    assert mem.get() == 2
    with pytest.raises(KeyError, match="missing"):
        assert mem.event('store') is False
    with pytest.raises(redzed.UnknownEvent):
        mem.event('sleep')  # unknown event


def test_validator(circuit):
    """Test the validator."""
    def is_multiple_of_5(n):
        if n % 5 == 0:
            return n
        raise ValueError("no!")

    mem = redzed.Memory(
        'M', validator=is_multiple_of_5,
        initial=[redzed.InitValue(x) for x in [1, 3, 5, 7]])      # 5 will be accepted
    mini_init(circuit)

    assert mem.get() == 5
    assert mem.event('store', 25) is True
    assert mem.get() == 25
    assert mem.event('store', 68) is False
    assert mem.get() == 25
