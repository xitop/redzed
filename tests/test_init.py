"""
Test block initializers.
"""

# pylint: disable=missing-class-docstring, unused-argument

from unittest.mock import patch

import pytest

import redzed

from .utils import add_ts, mini_init


def _fail():
    raise RuntimeError("failure")


def test_no_init_error(circuit):
    """Errors getting a value are suppressed."""
    mem = redzed.Memory(
        "m", initial=[
            redzed.InitFunction(_fail), redzed.InitFunction(_fail), redzed.InitFunction(int)]
        )
    with patch.object(mem, 'log_error', wraps=mem.log_error) as wrapped:
        mini_init(circuit)
        assert wrapped.call_count == 2
    assert mem.get() == 0


def test_no_apply_error(circuit):
    """Errors applying a value are suppressed."""
    class StrMemory(redzed.Memory):
        def rz_init(self, value, /):
            if not isinstance(value, str):
                raise TypeError("strings only!")
            super().rz_init(value)

    mem = StrMemory(
        "m", initial=[0, None, redzed.InitValue("zero")])   # one item must be an initializer
    with patch.object(mem, 'log_error', wraps=mem.log_error) as wrapped:
        mini_init(circuit)
        assert wrapped.call_count == 2
    assert mem.get() == "zero"


def test_no_restore_error(circuit):
    """Errors applying a saved state are suppressed."""
    class StrMemory(redzed.Memory):
        def rz_restore_state(self, state, /):
            if not isinstance(state, str):
                raise TypeError("strings only!")
            super().rz_restore_state(state)

    mem = StrMemory(
        "m", initial=[redzed.PersistentState(), redzed.InitValue("zero")])
    storage = add_ts({mem.rz_key: None})
    circuit.set_persistent_storage(storage)
    with patch.object(mem, 'log_error', wraps=mem.log_error) as wrapped:
        mini_init(circuit)
        assert wrapped.call_count == 1
    assert mem.get() == "zero"


def test_undef(circuit):
    """Undefs are quietly ignored."""
    mem = redzed.Memory(
        "m", initial=[
            redzed.InitFunction(lambda: redzed.UNDEF), redzed.InitValue(False)]
        )
    with patch.object(mem, 'log_error', wraps=mem.log_error) as wrapped:
        mini_init(circuit)
        assert not wrapped.called
    assert mem.get() is False


def test_reusability(circuit):
    """Initializers are reusable."""
    cnt = -2

    def counter():
        # returns: UNDEF, 0, 1, 2, 3, ...
        nonlocal cnt
        cnt += 1
        return redzed.UNDEF if cnt < 0 else cnt

    init1 = redzed.InitFunction(counter)
    init2 = redzed.InitValue("X")

    mems = [redzed.Memory(redzed.unique_name(), initial=(init1, init2)) for x in range(5)]
    assert all(m.rz_initializers == [init1, init2] for m in mems)
    mini_init(circuit)
    assert mems[0].rz_initializers == [None, None]
    assert all(m.rz_initializers == [None, init2] for m in mems[1:])
    assert mems[0].get() == "X"
    assert [m.get() for m in mems[1:]] == list(range(4))


def test_no_init_support(circuit):
    """Some blocks do not support state initialization."""
    class NoInit(redzed.Block):
        pass

    with pytest.raises(TypeError, match='not supported'):
        NoInit('np1', initial="value")


def test_no_ps_support(circuit):
    """Some blocks do not support persistent state."""
    class NoPers(redzed.Block):
        def rz_init(self, value):
            pass

    NoPers('np0', initial=redzed.InitValue(0))
    with pytest.raises(TypeError, match='not supported'):
        NoPers('np1', initial=redzed.PersistentState())


def test_only_one_ps(circuit):
    """PersistentState initializer may be used just once"""
    with pytest.raises(ValueError, match='Multiple'):
        redzed.Memory('mem', initial=[redzed.PersistentState(), redzed.PersistentState()])
