"""
Test the Memory block.
"""

import pytest

import redzed

from .utils import runtest, add_ts, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_persistence(circuit):
    """test persistent state"""
    async def tester():
        mem.event('store', "X")

    inp = redzed.Memory("m0", initial=[redzed.RestoreState(), "no"])
    num = redzed.Memory("m1", initial=[redzed.RestoreState(), 0], validator=int)
    mem = redzed.Memory("m2", initial=[redzed.RestoreState(), 9])
    assert inp.rz_key == "Memory:m0"
    storage = add_ts({inp.rz_key: "yes"})
    circuit.set_persistent_storage(storage)
    await runtest(tester())
    assert inp.get() == "yes"
    assert num.get() == 0
    assert mem.get() == "X"
    assert strip_ts(storage) == {inp.rz_key: "yes", num.rz_key: 0, mem.rz_key: "X"}


async def test_validator_persistence(circuit):
    """save value must not be double-validated"""
    def add100(n):
        return n + 100

    inp = redzed.Memory(
        "inp", initial=[redzed.RestoreState(), redzed.InitValue(7)], validator=add100)
    storage = {}
    circuit.set_persistent_storage(storage)
    await runtest(sleep=0)
    assert strip_ts(storage) == {inp.rz_key: 107}

    redzed.reset_circuit()
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)

    inp = redzed.Memory(
        "inp", initial=[redzed.RestoreState(), redzed.InitValue(3)], validator=add100)
    await runtest(sleep=0)
    assert strip_ts(storage) == {inp.rz_key: 107}
