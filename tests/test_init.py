"""
Test block initializers.
"""

# pylint: disable=missing-class-docstring

from unittest.mock import patch

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
        "m", initial=[redzed.RestoreState(), redzed.InitValue("zero")])
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
