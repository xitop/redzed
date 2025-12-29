"""
Test Block events.
"""

# pylint: disable=missing-class-docstring, unused-argument

import asyncio

import pytest

import redzed

from .utils import runtest

pytestmark = pytest.mark.usefixtures("task_factories")

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


async def _init_by_event(circuit, waittime):
    mem = redzed.Memory("memory", initial=redzed.InitWait(0.1))

    async def tester(wt):
        await asyncio.sleep(wt)
        mem.event('store', 321)

    await runtest(tester(waittime), immediate=True)


async def test_init_by_event_1(circuit):
    """Test initialization by an event 1/2."""
    with Grp(Exc(RuntimeError, match="not initialized")):
        await _init_by_event(circuit, 0.15)     # > 0.1 failure


async def test_init_by_event_2(circuit):
    """Test initialization by an event 2/2."""
    await _init_by_event(circuit, 0.05)         # < 0.1 OK


async def test_no_recursive_events1(circuit):
    """Recursive events are forbidden."""

    mem1 = redzed.Memory("memory1", initial=0)
    mem2 = redzed.Memory("memory2", initial=0)

    @redzed.triggered
    def mem1to2(memory1):
        mem2.event('store', memory1 + 1)

    @redzed.triggered
    def mem2to1(memory2):
        mem1.event('store', memory2 + 1)

    with Grp(Exc(RuntimeError, match="event of the same type")):
        await runtest(sleep=0.5)


async def test_no_recursive_events2(circuit):
    """
    Recursive events are forbidden.

    Redirecting to a different event within the same block
    is OK unless there is a loop.
    """

    class E321(redzed.Memory):
        def _event_store1(self, edata):
            evalue = edata['evalue']
            self.event('store' if evalue < 100 else 'store3', evalue + 1)

        def _event_store2(self, edata):
            self.event('store1', edata['evalue'] + 2)

        def _event_store3(self, edata):
            self.event('store2', edata['evalue'] + 3)

    mem = E321("mem321")
    mem.event('store3', 5)          # 3->2->1->store
    assert mem.get() == 5+3+2+1

    with Exc(RuntimeError, match="event of the same type"):
        mem.event('store3', 105)    # 3->2->1->3 !!!
