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

    inp = redzed.Memory(
        "m0", initial=[redzed.RestoreState(), redzed.InitValue("no")])
    num = redzed.Memory(
        "m1", initial=[redzed.RestoreState(), redzed.InitValue(0)], validator=int)
    mem = redzed.Memory(
        "m2", initial=[redzed.RestoreState(), redzed.InitValue(9)])
    assert inp.rz_key == "Memory:m0"
    storage = add_ts({inp.rz_key: "yes", num.rz_key: "//"})
    circuit.set_persistent_storage(storage)
    await runtest(tester())
    assert inp.get() == "yes"
    assert num.get() == 0
    assert mem.get() == "X"
    assert strip_ts(storage) == {inp.rz_key: "yes", num.rz_key: 0, mem.rz_key: "X"}
