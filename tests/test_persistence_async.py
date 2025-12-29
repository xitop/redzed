"""
Test the persistent state.
"""

import pytest

import redzed

from .utils import add_ts, runtest, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_remove_unused(circuit):
    """Unused keys are removed."""
    memy = redzed.Memory('myes', initial=[redzed.RestoreState(), redzed.InitValue(10)])
    memn = redzed.Memory('mno', initial=[redzed.InitValue(20)])
    out = redzed.OutputFunc('out', func=print)
    storage = add_ts({memy.rz_key: 1, memn.rz_key: 2, 'Memory:dummy': 3, out.rz_key: 4})
    circuit.set_persistent_storage(storage)
    await runtest(sleep=0)
    assert memy.get() == 1
    assert memn.get() == 20
    assert strip_ts(storage) == {memy.rz_key: 1}


async def test_expiration(circuit):
    """Test the internal state expiration + test timestamps"""
    mem1 = redzed.Memory(
        'mem1', initial=[redzed.RestoreState(), redzed.InitValue(91)])
    mem2 = redzed.Memory(
        'mem2', initial=[redzed.RestoreState(expiration=None), redzed.InitValue(92)])
    mem3 = redzed.Memory(
        'mem3', initial=[redzed.RestoreState(expiration=10), redzed.InitValue(93)])
    mem4 = redzed.Memory(
        'mem4', initial=[redzed.RestoreState(expiration="1m30s"), redzed.InitValue(94)])

    storage = add_ts({mem1.rz_key: 1, mem2.rz_key: 2, mem3.rz_key: 3, mem4.rz_key: 4}, age=12)
    storage_copy = {k: v.copy() for k, v in storage.items()}
    circuit.set_persistent_storage(storage)
    await runtest(sleep=0)

    assert mem1.get() == 1     # no expiration
    assert mem2.get() == 2     # no expiration
    assert mem3.get() == 93    # state expired, init from default
    assert mem4.get() == 4     # not expired

    # new timestamps are recent, previous ones are 12 seconds old
    assert storage.keys() == storage_copy.keys()
    assert all(12 <= storage[k][1] - storage_copy[k][1] <= 13 for k in storage)
