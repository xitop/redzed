"""
Test the Memory/MemoryExp block.
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
    names = {'name': 'Cell', 'comment': 'test block', 'type': 'Memory'}

    mem = redzed.Memory('Cell', comment='test block', always_trigger=opt_trigger, initial=0)
    assert mem.event('_get_info') == names
    mini_init(circuit)

    assert mem.get() == 0
    assert mem.event('_get_info') == names | {'output': 0}
    assert mem.get(with_previous=True) == (0, redzed.UNDEF)

    assert mem.event('store', 1)
    assert mem.get() == 1
    assert mem.get(with_previous=True) == (1, 0)
    assert mem.event('_get_info') == names | {'output': 1, 'previous': 0}

    assert mem.event('store', 2)
    assert mem.get() == 2
    assert mem.get(with_previous=True) == (2, 1)
    assert mem.event('_get_info') == names | {'output': 2, 'previous': 1}

    for _ in 0,1,2:
        assert mem.event('store', 2)
        assert mem.get() == 2
        prev = 2 if opt_trigger else 1
        assert mem.get(with_previous=True) == (2, prev)
        assert mem.event('_get_info') == names | {'output': 2, 'previous': prev}

    assert mem.event('store', 99)
    assert mem.get() == 99
    assert mem.get(with_previous=True) == (99, 2)
    assert mem.event('_get_info') == names | {'output': 99, 'previous': 2}


@pytest.mark.parametrize('exc', [False, True])
@pytest.mark.parametrize('suppress', [False, True])
def test_validator(circuit, exc, suppress):
    """Test the validator."""
    def is_multiple_of_5(n):
        if n % 5 == 0:
            return n
        if exc:
            raise ValueError("no!")
        return redzed.UNDEF

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
        with pytest.raises(redzed.ValidationError):
            mem.event('store', 68)
        with pytest.raises(redzed.ValidationError):
            mem.event('store', 69, suppress=False)

    assert mem.get() == 25


@pytest.mark.parametrize(
    'exctype', [redzed.ValidationError, TypeError, ValueError, ArithmeticError])
# pylint: disable-next=unused-argument
def test_broken_validator(circuit, exctype):
    """Test a validator with a problem"""
    def validator(value):
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            raise exctype("value not OK")
        raise IndexError("bug!")

    inp = redzed.Memory('input', validator=validator, initial=0)
    mini_init(circuit)

    assert inp.event('store', 10)
    assert inp.get() == 10
    assert not inp.event('store', "text", suppress=True)
    with pytest.raises(redzed.ValidationError):
        inp.event('store', "text")
    assert inp.get() == 10
    with pytest.raises(Exception):
        inp.event('store', (1,2,3), suppress=True)  # not suppressed
    assert inp.get() == 10


# pylint: disable-next=unused-argument
def test_expired_validation(circuit):
    """Test validation of 'expired'"""
    def positive(x):
        return redzed.UNDEF if x < 0 else x

    redzed.MemoryExp('exp1', duration=1, expired=+1, validator=positive)
    with pytest.raises(redzed.ValidationError, match="validator rejected"):
        redzed.MemoryExp('exp2', duration=1, expired=-1, validator=positive)
