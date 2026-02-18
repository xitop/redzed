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


@pytest.mark.parametrize('opt_trigger', [False, True])
def test_outputs(circuit, opt_trigger):
    """Test output and previous output."""
    mem = redzed.Memory('Cell', always_trigger=opt_trigger, initial=0)
    mini_init(circuit)

    assert mem.get() == 0
    assert mem.get_previous() is redzed.UNDEF

    assert mem.event('store', 1)
    assert mem.get() == mem.event('_get_output') == 1
    assert mem.get_previous() == mem.event('_get_previous') == 0

    assert mem.event('store', 2)
    assert mem.get() == 2
    assert mem.get_previous() == 1

    for _ in 0,1,2:
        assert mem.event('store', 2)
        assert mem.get() == 2
        assert mem.get_previous() == (2 if opt_trigger else 1)

    assert mem.event('store', 99)
    assert mem.get() == mem.event('_get_output') == 99
    assert mem.get_previous() == mem.event('_get_previous') == 2


@pytest.mark.parametrize('suppress', [False, True])
def test_validator(circuit, suppress):
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
    assert mem.event('store', 25, suppress=suppress) is True
    assert mem.get() == 25
    if suppress:
        assert mem.event('store', 68, suppress=True) is False
    else:
        with pytest.raises(ValueError):
            mem.event('store', 68)
        with pytest.raises(ValueError):
            mem.event('store', 69, suppress=False)

    assert mem.get() == 25
