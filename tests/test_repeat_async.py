"""
Test the Repeat block.
"""

# pylint: disable=missing-class-docstring

import asyncio

import pytest

import redzed

from .utils import runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")

# pylint: disable=unused-argument

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


async def _repeat(circuit, count, log, a_interval=None, b_count=None):
    """Test the event repeating."""
    logger = TimeLogger('log', log_edata=True)

    class Adapter(redzed.Block):
        def _event_one(self, edata):
            logger.log(edata | {'etype': 'one'})
        def _event_two(self, edata):
            logger.log(edata | {'etype': 'two'})

    repeater = redzed.Repeat('repeat', dest=Adapter('ada'), interval=0.05, count=count)

    async def tester(cnt_limit):
        await asyncio.sleep(0.05)
        assert repeater.get() == 0
        if a_interval is not None:
            repeater.event('one', 'A', repeat_interval=a_interval)
        else:
            repeater.event('one', 'A')
        await asyncio.sleep(0.18)   # 4 events (original + 3 repeats)
        a_events = len(logger.tlog)
        assert repeater.get() == a_events - 1
        # another event
        if b_count is not None:
            repeater.event('two', 'B', repeat_count=b_count)
        else:
            repeater.event('two', 'B')
        assert repeater.get() == 0
        await asyncio.sleep(0.12)
        assert repeater.get() == len(logger.tlog) - a_events - 1

    await runtest(tester(count))
    logger.compare(log)


async def test_repeat_unlimited(circuit):
    LOG = [
        ( 50, {'etype': 'one', 'evalue': 'A', 'repeat': 0}),
        (100, {'etype': 'one', 'evalue': 'A', 'repeat': 1}),
        (150, {'etype': 'one', 'evalue': 'A', 'repeat': 2}),
        (200, {'etype': 'one', 'evalue': 'A', 'repeat': 3}),
        (230, {'etype': 'two', 'evalue': 'B', 'repeat': 0}),
        (280, {'etype': 'two', 'evalue': 'B', 'repeat': 1}),
        (330, {'etype': 'two', 'evalue': 'B', 'repeat': 2}),
        ]
    await _repeat(circuit, count=999, log=LOG)


async def test_repeat_dynamic_count(circuit):
    LOG = [
        ( 50, {'etype': 'one', 'evalue': 'A', 'repeat': 0}),
        (100, {'etype': 'one', 'evalue': 'A', 'repeat': 1}),
        (150, {'etype': 'one', 'evalue': 'A', 'repeat': 2}),
        (200, {'etype': 'one', 'evalue': 'A', 'repeat': 3}),
        (230, {'etype': 'two', 'evalue': 'B', 'repeat': 0}),
        (280, {'etype': 'two', 'evalue': 'B', 'repeat': 1}),
        ]
    await _repeat(circuit, count=999, b_count=1,log=LOG)


async def test_repeat_dynamic_interval(circuit):
    LOG = [
        ( 50, {'etype': 'one', 'evalue': 'A', 'repeat': 0}),
        ( 82, {'etype': 'one', 'evalue': 'A', 'repeat': 1}),
        (114, {'etype': 'one', 'evalue': 'A', 'repeat': 2}),
        (146, {'etype': 'one', 'evalue': 'A', 'repeat': 3}),
        (178, {'etype': 'one', 'evalue': 'A', 'repeat': 4}),
        (210, {'etype': 'one', 'evalue': 'A', 'repeat': 5}),
        (230, {'etype': 'two', 'evalue': 'B', 'repeat': 0}),
        (280, {'etype': 'two', 'evalue': 'B', 'repeat': 1}),
        (330, {'etype': 'two', 'evalue': 'B', 'repeat': 2}),
        ]
    await _repeat(circuit, count=999, a_interval=0.032,log=LOG)


async def test_repeat_limited(circuit):
    LOG = [
        ( 50, {'etype': 'one', 'evalue': 'A', 'repeat': 0}),
        (100, {'etype': 'one', 'evalue': 'A', 'repeat': 1}),
        (230, {'etype': 'two', 'evalue': 'B', 'repeat': 0}),
        (280, {'etype': 'two', 'evalue': 'B', 'repeat': 1}),
        ]
    await _repeat(circuit, count=1, log=LOG)


async def test_repeat_disabled(circuit):
    LOG = [
        ( 50, {'etype': 'one', 'evalue': 'A', 'repeat': 0}),
        (230, {'etype': 'two', 'evalue': 'B', 'repeat': 0}),
        ]
    await _repeat(circuit, count=0, log=LOG)


async def test_output(circuit):
    """Test if the output value matches the repeat count."""
    class Check(redzed.Block):
        def _event_EV(self, edata):
            assert edata['evalue'] in [10, 20]
            assert edata['twelve'] == 12
            assert 0 <= edata['repeat'] == rpt.get() <= 3

    rpt = redzed.Repeat('repeat0', dest=Check('check'), interval=0.05)

    async def tester():
        assert rpt.get() == 0
        rpt.event('EV', 10, twelve=12, repeat=999)  # 'repeat' will be overwritten
        await asyncio.sleep(0.16)
        rpt.event('EV', 20, twelve=12)
        await asyncio.sleep(0.11)

    await runtest(tester())


async def test_loop1(circuit):
    """Test a loop in the circuit. Error at initialization."""
    mem = redzed.Memory('mem', initial=0, validator=lambda x: x+1)
    repeater = redzed.Repeat('rpt', dest=mem, interval="10ms")
    @redzed.triggered
    def mem2repeat(mem):
        repeater.event('store', mem)

    with Grp(Exc(RuntimeError, match="another event of the same type")):
        await runtest(sleep=0.5)
    assert mem.get() == 2   # mem output = init: 1, repeat#1: 2, repeat#2: error!


async def test_loop2(circuit):
    """Test a loop in the circuit. Error during runtime."""
    mem = redzed.Memory('mem', initial=0, validator=lambda x: x+1)
    repeater = redzed.Repeat('rpt', dest=mem, interval="10ms")
    @redzed.triggered
    def mem2repeat(mem):
        if mem > 10:
            repeater.event('store', mem)

    async def tester():
        mem.event('store', 20)

    with Grp(Exc(RuntimeError, match="another event of the same type")):
        await runtest(tester())
    assert mem.get() == 21   # mem output = init: 1, store: 21, repeat#1: error!
