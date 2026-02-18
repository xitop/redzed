"""
Test the Counter block.
"""

import collections

import redzed

from .utils import mini_init


def test_inc_dec(circuit):
    """Test the basic increment/decrement."""
    cnt = redzed.Counter('cnt')
    cnt100 = redzed.Counter('cnt_100', initial=100)
    mini_init(circuit)
    for i in range(5):
        assert cnt.get() == i
        assert cnt100.get() == i + 100
        assert cnt.event('inc') == i + 1
        assert cnt100.event('inc')== i + 101
    for i in reversed(range(5)):
        assert cnt.event('dec') == i
        assert cnt100.event('dec') == i + 100
        assert cnt.get() == i
        assert cnt100.get() == 100 + i
    assert cnt.event('reset') == cnt.get() == 0     # evaluation left to right


def test_amount_1(circuit):
    """Test variable amounts."""
    cnt = redzed.Counter('cnt')
    mini_init(circuit)
    for i in range(10):
        # sum of first N odd numbers = N**2 (example: 1+3+5+7 = 16)
        assert cnt.get() == i*i
        cnt.event('inc', 2*i + 1)


def test_amount_2(circuit):
    """Test variable amounts."""
    cnt = redzed.Counter('cnt', initial=1)
    mini_init(circuit)
    for _ in range(16):
        cnt.event('inc', evalue=cnt.get())
    assert cnt.get() == 2**16
    for _ in range(16):
        cnt.event('dec', cnt.get()//2)
    assert cnt.get() == 1


def test_amount_3(circuit):
    """Test variable amounts."""
    cnt = redzed.Counter('cnt')
    mini_init(circuit)
    for v in range(-10, 10, 1):
        cnt.event('inc', v)
        cnt.event('dec', evalue=v)
        assert cnt.get() == 0


def test_set(circuit):
    """Test set events."""
    cnt = redzed.Counter('cnt')
    cnt11 = redzed.Counter('cnt_mod_11', modulo=11)
    mini_init(circuit)

    for i in range(-300, +300, 7):
        cnt.event('set', evalue=i)
        assert cnt.get() == i
        cnt11.event('set', i)
        assert cnt11.get() == i % 11


def test_modulo_1(circuit):
    """Test modulo arithmetics."""
    MOD = 9
    ROUNDS = 15
    START = 4   # any integer 0 to MOD-1
    cycle = redzed.Counter('cnt_mod', modulo=MOD, initial=START)
    mini_init(circuit)

    values = collections.defaultdict(int)
    for _ in range(MOD * ROUNDS):
        cycle.event('inc')
        values[cycle.get()] += 1
    assert cycle.get() == START
    assert values.keys() == set(range(MOD))
    assert all(v == ROUNDS for v in values.values())


def test_modulo_2(circuit):
    """Test modulo arithmetics."""
    cnt = redzed.Counter('cnt')
    cnt24 = redzed.Counter('cnt_mod_24', modulo=24)
    cnt37 = redzed.Counter('cnt_mod_37', modulo=37)
    mini_init(circuit)

    for v in range(-200, +300, 7):
        cnt.event('inc', evalue=v)
        cnt24.event('inc', v)
        cnt37.event('dec', -v)
        assert cnt.get() % 24 == cnt24.get()  # congruent mod 24
        assert cnt.get() % 37 == cnt37.get()  # congruent mod 37


def test_modulo_initial(circuit):
    """Test modulo arithmetics on initial values."""
    cnt24 = redzed.Counter('cnt_mod_24', modulo=24, initial=241)
    cnt37 = redzed.Counter('cnt_mod_37', modulo=37, initial=-1)
    mini_init(circuit)

    assert cnt24.get() == 1
    assert cnt37.get() == 36
