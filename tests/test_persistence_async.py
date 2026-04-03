"""
Test the persistent state.
"""

import asyncio
import json
import pickle
import random

import pytest

import redzed
import redzed.utils

from .utils import add_ts, Exc, Grp, runtest, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_remove_unused(circuit):
    """Unused keys are removed."""
    memy = redzed.Memory('myes', initial=[redzed.PersistentState(), redzed.InitValue(10)])
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
        'mem1', initial=[redzed.PersistentState(), redzed.InitValue(91)])
    mem2 = redzed.Memory(
        'mem2', initial=[redzed.PersistentState(expiration=None), redzed.InitValue(92)])
    mem3 = redzed.Memory(
        'mem3', initial=[redzed.PersistentState(expiration=10), redzed.InitValue(93)])
    mem4 = redzed.Memory(
        'mem4', initial=[redzed.PersistentState(expiration="1m30s"), redzed.InitValue(94)])

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


async def test_close_1(circuit):
    """Test if the close function is called (normal exit)."""
    closed = False
    def close():
        nonlocal closed
        closed = True

    redzed.Memory('mem', initial=None)
    circuit.set_persistent_storage({}, close_callback=close)
    await runtest(sleep=0)
    assert closed


async def test_close_2(circuit):
    """Test if the close function is called (error exit)."""
    closed = False
    def close():
        nonlocal closed
        closed = True

    mem_blk = redzed.Memory('mem', initial=1)
    @redzed.trigger
    def crash_0(mem):
        return 1/mem

    async def tester():
        mem_blk.event('store', 0)

    circuit.set_persistent_storage({}, close_callback=close)
    with Grp(Exc(ZeroDivisionError)):
        await runtest(tester())
    assert closed


@pytest.mark.parametrize('fmt', ['json', 'pickle'])
async def test_pdict(circuit, fmt, tmp_path):
    """Test the PersistentDict."""

    num = random.randint(0, 999_999)
    module = (json if fmt == 'json' else pickle)
    pdict_path = tmp_path / 'test.pdict'
    storage = redzed.utils.PersistentDict(pdict_path, format=fmt, sync_time=0.015)
    circuit.set_persistent_storage(storage, close_callback=storage.flush)
    mem = redzed.Memory('mem', initial=[redzed.PersistentState(), num])

    def get_size():
        return pdict_path.stat().st_size

    def get_saved_mem():
        with open(pdict_path, "rb") as df:
            raw = df.read()
        data = module.loads(raw)
        return data[mem.rz_key][0]

    await runtest(sleep=0)
    assert get_saved_mem() == num

    redzed.reset_circuit()
    del mem
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage, close_callback=storage.flush)
    mem = redzed.Memory('mem', initial=[redzed.PersistentState()])

    async def tester():
        m = mem.get()
        size1 = get_size()
        mem.event('store', [m+1, m+2, m+3])
        assert get_size() == size1
        await asyncio.sleep(0.02)   # sync every 15 ms
        assert (size2 := get_size()) > size1
        mem.event('store', m+4)
        assert get_size() == size2
        storage.flush()             # explicit sync
        assert get_size() < size2
        mem.event('store', m+5)
        # sync on close
    await runtest(tester())

    assert get_saved_mem() == num + 5
    pdict_path.unlink()
