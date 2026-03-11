"""
Test the persistent state.
"""

import json
import os
import pickle

import pytest

import redzed, redzed.utils
import tempfile

from .utils import add_ts, runtest, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


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
async def test_pdict(circuit, fmt):
    """Test the PersistentDict."""

    num = os.getpid()
    module = (json if fmt == 'json' else pickle)
    try:
        filename = None
        fd, filename = tempfile.mkstemp()
        os.close(fd)
        storage = redzed.utils.PersistentDict(filename, format=fmt)
        circuit.set_persistent_storage(storage, close_callback=storage.flush)
        mem1 = redzed.Memory('mem', initial=[redzed.PersistentState(), num])
        await runtest(sleep=0)

        with open(filename, "rb") as df:
            raw = df.read()
        data = module.loads(raw)
        assert data[mem1.rz_key][0] == num

        redzed.reset_circuit()
        circuit = redzed.get_circuit()
        circuit.set_persistent_storage(storage, close_callback=storage.flush)
        mem2 = redzed.Memory('mem', initial=[redzed.PersistentState()])
        async def tester():
            mem2.event('store', mem2.get() + 1000)
        await runtest(tester())

        with open(filename, "rb") as df:
            raw = df.read()
        data = module.loads(raw)
        assert data[mem2.rz_key][0] == num + 1000
    finally:
        if filename is not None:
            os.unlink(filename)
