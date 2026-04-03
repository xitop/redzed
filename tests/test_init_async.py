"""
Test async initializers.
"""

import asyncio

import pytest

import redzed

from .utils import runtest

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_init_task(circuit):
    """Test sync init during an async init in progress"""
    m_A = redzed.Memory(
        "mA", initial=[redzed.InitTask(asyncio.sleep, 0.10, "A", timeout=0.2), "no!"])
    m_B = redzed.Memory(
        "mB", initial=[redzed.InitTask(asyncio.sleep, 0.25, "B", timeout=0.1), "no!"])
    m_C = redzed.Memory(
        "mC", initial=[redzed.InitTask(asyncio.sleep, 0.25, "C", timeout=0.3), "no!"])


    async def tester():
        await asyncio.sleep(0.15)
        assert m_A.get() == "A"
        assert m_B.get() == "no!"
        assert m_C.get() is redzed.UNDEF
        m_C.event('store', "c_event")   # will abort m_C InitTask with its 0.5s timeout
        assert await circuit.reached_state(redzed.CircuitState.RUNNING) is True
        assert m_C.get() == "c_event"
        assert 0.15 <= circuit.runtime() <= 0.20  # the event has completed the initialization
        await asyncio.sleep(0.2)
        assert m_C.get() == "c_event"           # not overwritten

    await runtest(tester(), immediate=True)
