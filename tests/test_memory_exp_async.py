"""
Test the MemoryExp block.
"""

# pylint: disable=unused-argument

import asyncio

import pytest

import redzed

from .utils import ms, runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_expiration(circuit):
    """Test the value expiration."""
    logger1 = TimeLogger('logger1', mstop=True, triggered_by="exp1")
    memexp1 = redzed.MemoryExp('exp1', duration=0.07, expired=-1, initial=99)

    logger2 = TimeLogger('logger2', mstop=True, triggered_by="exp2")
    memexp2 = redzed.MemoryExp('exp2', duration=0.07, expired=-1, initial=-1)

    async def tester1(memexp):
        assert memexp.fsm_state() == 'valid'
        await ms(100)
        assert memexp.fsm_state() == 'expired'
        memexp.event('store', 77)
        assert memexp.fsm_state() == 'valid'
        await ms(50)
        memexp.event('store', 55)
        await ms(100)
        memexp.event('store', 33, duration="0.02s")    # override
        await ms(40)

    async def tester2(memexp):
        assert memexp.get() == -1
        assert memexp.fsm_state() == 'expired'
        memexp.event('store', 99)
        assert memexp.fsm_state() == 'valid'
        await ms(50)
        memexp.event('store', 99)
        await ms(50)
        memexp.event('store', 99)
        await ms(100)
        memexp.event('store', 77)
        await ms(20)
        memexp.event('store', -1)
        assert memexp.fsm_state() == 'expired'
        await ms(30)
        memexp.event('store', 55)
        await ms(20)
        memexp.event('expire')

    async def tester():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(tester1(memexp1))
            tg.create_task(tester2(memexp2))

    await runtest(tester())
    LOG1 = [
        (0, 99),
        (70, -1),
        (100, 77),
        (150, 55),
        (220, -1),
        (250, 33),
        (270, -1),
        (290, "--stop--"),
    ]
    logger1.compare(LOG1)

    LOG2 = [
        (0, -1),
        (0, 99),
        (170, -1),
        (200, 77),
        (220, -1),
        (250, 55),
        (270, -1),
        (290, "--stop--"),
    ]
    logger2.compare(LOG2)


async def ptest(circuit, delay, slog):
    state = {}
    # circuit 1
    circuit.set_persistent_storage(state)
    me = redzed.MemoryExp(
        'exp', duration=0.15, expired="exp",
        initial=[redzed.PersistentState(), redzed.InitValue("ok1")])
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
        initial=[redzed.PersistentState(), redzed.InitValue("ok2")])
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
        initial=[redzed.PersistentState(), redzed.InitValue(7)], validator=add100)
    storage = {}
    circuit.set_persistent_storage(storage)
    await runtest(sleep=0)
    assert inp.get() == 107

    redzed.reset_circuit()
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)

    inp = redzed.MemoryExp(
        "inp", duration=10, expired=0,
        initial=[redzed.PersistentState(), redzed.InitValue(3)], validator=add100)
    await runtest(sleep=0)
    assert inp.get() == 107     # add100 not applied again


async def test_store(circuit):
    """Test store event and suppress."""
    inp = redzed.MemoryExp(
        "inp", duration=10, expired=99,
        initial=0, validator=lambda x: redzed.UNDEF if x < 0 else x)

    async def tester():
        assert inp.event('store', +1)
        with pytest.raises(redzed.ValidationError):
            assert inp.event('store', -1)
        assert inp.get() == 1
        assert not inp.event('store', -1, suppress=True)

    await runtest(tester())
