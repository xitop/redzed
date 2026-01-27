"""
Test the MemoryExp block.
"""

# pylint: disable=unused-argument

import asyncio

import pytest

import redzed

from .utils import runtest, TimeLogger, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_expiration(circuit):
    """Test the value expiration."""
    logger = TimeLogger('logger', mstop=True, triggered_by="exp")
    memexp = redzed.MemoryExp('exp', duration=0.07, expired=-1, initial=99)

    async def tester():
        await asyncio.sleep(0.1)
        assert memexp.state == 'expired'
        memexp.event('store', 77)
        assert memexp.state == 'valid'
        await asyncio.sleep(0.05)
        memexp.event('store', 55)
        await asyncio.sleep(0.1)
        memexp.event('store', 33, duration="0.03s")    # override
        await asyncio.sleep(0.07)

    await runtest(tester())
    LOG = [
        (0, 99),
        (70, -1),
        (100, 77),
        (150, 55),
        (220, -1),
        (250, 33),
        (280, -1),
        (320, "--stop--"),
    ]
    logger.compare(LOG)


async def ptest(circuit, delay, slog):
    state = {}
    # circuit 1
    circuit.set_persistent_storage(state)
    me = redzed.MemoryExp(
        'exp', duration=0.15, expired="exp",
        initial=[redzed.RestoreState(), redzed.InitValue("ok1")])
    await runtest(sleep=0.05)
    assert me.rz_key in state

    # circuit 2
    await asyncio.sleep(delay)
    redzed.reset_circuit()
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(state)
    logger = TimeLogger('logger', triggered_by='exp')
    redzed.MemoryExp(
        'exp', duration=0.15, expired="exp",
        initial=[redzed.RestoreState(), redzed.InitValue("ok2")])
    await runtest(sleep=0.2)
    logger.compare(slog)


async def test_persistent_state(circuit):
    """Test the state persistence."""
    LOG = [
        (0, "ok1"),
        (100, "exp"),   # 150 ms expiration - 50 ms in circuit1
    ]
    await ptest(circuit, 0.0, LOG)


async def test_expired_persistent_state(circuit):
    """Test the persistent state with expired state"""

    LOG = [
        (0, "ok2"),     # ok1 expired
        (150, "exp")
    ]
    await ptest(circuit, 0.2, LOG)


async def test_validator_persistence(circuit):
    """save value must not be double-validated"""
    def add100(n):
        return n + 100

    inp = redzed.MemoryExp(
        "inp", duration=10, expired=99,
        initial=[redzed.RestoreState(), redzed.InitValue(7)], validator=add100)
    storage = {}
    circuit.set_persistent_storage(storage)
    await runtest(sleep=0)
    assert inp.get() == 107

    redzed.reset_circuit()
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)

    inp = redzed.MemoryExp(
        "inp", duration=10, expired=0,
        initial=[redzed.RestoreState(), redzed.InitValue(3)], validator=add100)
    await runtest(sleep=0)
    assert inp.get() == 107     # add100 not applied again
