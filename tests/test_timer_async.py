"""
Test the Timer block.
"""

import asyncio

import pytest

import redzed

from .utils import runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")

# pylint: disable=unused-argument

async def test_clock(circuit):
    """Test a trivial clock signal generator."""
    logger1 = TimeLogger('logger1')
    logger2 = TimeLogger('logger2')
    redzed.Timer('timer1', t_on=0.03, t_off=0.08)
    redzed.Timer('timer2', t_period=0.15)

    @redzed.triggered
    def t1_l1(timer1):
        logger1.log(timer1)

    @redzed.triggered
    def t2_l2(timer2):
        logger2.log(timer2)

    await runtest(sleep=0.5)
    LOG1 = [
        (0,   False), (80, True),
        (110, False), (190, True),
        (220, False), (300, True),
        (330, False), (410, True),
        (440, False)]
    LOG2 = [
        (0,   False), (75, True),
        (150, False), (225, True),
        (300, False), (375, True),
        (450, False)]
    logger1.compare(LOG1)
    logger2.compare(LOG2)


async def test_restartable(circuit):
    """Test restartable vs. not restartable."""
    rlogger = TimeLogger('rlogger')
    rmono = redzed.Timer('rtimer', t_on=0.12)
    nlogger = TimeLogger('nlogger')
    nmono = redzed.Timer('ntimer', t_on=0.12, restartable=False)

    @redzed.triggered
    def r2r(rtimer):
        rlogger.log(rtimer)

    @redzed.triggered
    def n2n(ntimer):
        nlogger.log(ntimer)

    async def tester():
        await asyncio.sleep(0.05)
        assert rmono.event('start')         # start OK
        assert nmono.event('start')         # start OK
        await asyncio.sleep(0.05)
        assert rmono.event('start')         # re-start OK
        assert not nmono.event('start')     # re-start not ok!
        await asyncio.sleep(0.1)
        assert rmono.event('start')         # re-start OK
        assert nmono.event('start')         # start OK
        await asyncio.sleep(0.05)
        rmono.event('start')
        nmono.event('start')
        await asyncio.sleep(0.2)

    await runtest(tester())

    RLOG = [
        (0, False),
        (50, True),
        (370, False),
        ]
    rlogger.compare(RLOG)
    NLOG = [
        (0, False),
        (50, True), (170, False),   # 120 ms
        (200, True), (320, False),  # 120 ms
        ]
    nlogger.compare(NLOG)


async def test_duration(circuit):
    """Test variable timer duration."""
    logger = TimeLogger('logger', triggered_by='timer')
    mono = redzed.Timer('timer', t_on=0.1)

    async def tester():
        mono.event('start')
        await asyncio.sleep(0.15)
        mono.event('start', duration=0.05)
        await asyncio.sleep(0.1)
        mono.event('start', duration=None)
        await asyncio.sleep(0.25)

    await runtest(tester())
    LOG = [
        (0, False),                 # initial state
        (0, True), (100, False),    # 100 ms pulse
        (150, True), (200, False),  # 50 ms
        (250, True), (350, False),  # 100 ms
        ]
    logger.compare(LOG)
