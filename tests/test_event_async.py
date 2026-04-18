"""
Test Block events.
"""

# pylint: disable=missing-class-docstring, unused-argument

import asyncio

import pytest

import redzed

from .utils import Exc, Grp, runtest

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_ready(circuit):
    """The circuit is ready when supporting coroutines start."""
    mem = redzed.Memory("memory", initial=1)

    async def tester():
        assert mem.get() == 1
        mem.event('store', 2)
        circuit.shutdown()

    assert mem.get() is redzed.UNDEF
    await redzed.run(tester())
    assert mem.get() == 2


async def _init_by_event(circuit, waittime):
    mem = redzed.Memory("memory", initial=redzed.InitWait(0.1))

    async def tester(wt):
        await asyncio.sleep(wt)
        mem.event('store', 321)

    await runtest(tester(waittime), immediate=True)


async def test_init_by_event_1(circuit):
    """Test initialization by an event 1/2."""
    with Grp(Exc(RuntimeError, match="hasn't been initialized")):
        await _init_by_event(circuit, 0.15)     # > 0.1 failure


async def test_init_by_event_2(circuit):
    """Test initialization by an event 2/2."""
    await _init_by_event(circuit, 0.05)         # < 0.1 OK


async def test_no_recursive_events1(circuit):
    """Recursive events are forbidden."""

    mem1 = redzed.Memory("memory1", initial=0)
    mem2 = redzed.Memory("memory2", initial=0)

    @redzed.trigger
    def mem1to2(memory1):
        mem2.event('store', memory1 + 1)

    @redzed.trigger
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

    mem = E321("mem321", initial=0)

    async def tester():
        mem.event('store3', 5)
        assert mem.get() == 5+3+2+1
        mem.event('store3', 105)    # 3->2->1->3 !

    with Grp(Exc(RuntimeError, match="event of the same type")):
        await runtest(tester())


async def test_no_get_state(circuit):
    """No _get_state_ without rz_export_state."""

    class TestBlock1(redzed.Block):
        pass

    class TestBlock2(redzed.Block):
        def rz_export_state(self):
            return "STATE!"

    tb1 = TestBlock1('test1')
    tb2 = TestBlock2('test2')

    async def tester():
        assert tb2.event('_get_state') == "STATE!"
        with pytest.raises(redzed.UnknownEvent):
            tb1.event('_get_state')

    await runtest(tester())
