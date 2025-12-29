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


async def _repeat(circuit, count, log):
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
        repeater.event('one', 'A')
        await asyncio.sleep(0.18)   # 4 events (original + 3 repeats)
        assert repeater.get() == min(3, cnt_limit)
        repeater.event('two', 'B')  # another event
        assert repeater.get() == 0
        await asyncio.sleep(0.12)   # 1 + 2 repeats
        assert repeater.get() == min(2, cnt_limit)

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
