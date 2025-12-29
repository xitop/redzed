"""
Test the timed states in FSMs.
"""

# pylint: disable=missing-class-docstring, no-member

import asyncio
import time

import pytest

import redzed

from .utils import runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")

# pylint: disable=unused-argument


async def test_duration(circuit):
    """Test variable timer duration."""
    PERIOD = 0.040 # 40 ms = 25 Hz
    cnt = 0

    class PWM(redzed.FSM):
        ALL_STATES = ('off', 'on')
        TIMED_STATES = [
            ['on', None, 'off'],
            ['off', None, 'on'],
            ]
        EVENTS = (
            ('start', ..., 'on'),
            ('stop', ..., 'off'),
            )
        def __init__(self, *args, dc=0.5, **kwargs):
            self.x_dc = dc   # duty cycle 0.0 < dc < 1.0
            super().__init__(*args, **kwargs)

        def _event_setdc(self, edata):
            self.x_dc = edata['evalue']

        def duration_on(self):
            # in minutes and as a string
            return f"0h {self.x_dc * PERIOD / 60.0}m"

        def duration_off(self):
            return (1.0 - self.x_dc) * PERIOD

    vclock_fsm = PWM('vclock', comment="25Hz variable duty cycle (PWM)", initial='on')

    logger = TimeLogger('logger', mstop=True)

    @redzed.triggered
    def log_output(vclock):
        nonlocal cnt
        logger.log(vclock == 'on')
        if vclock == 'off':
            return
        cnt += 1
        if cnt == 3:
            # 'on' has just begun; 'on' -> 'off' timer is not set yet
            vclock_fsm.event('setdc', 0.25)
        elif cnt == 6:
            vclock_fsm.event('setdc', 1.0)
        elif cnt == 9:
            circuit.shutdown()


    await runtest(sleep=0.5)
    LOG = [
        # duty cycle on:off = 20:20 ms
        (0, True),  (20, False),
        (40, True), (60, False),
        (80, True),  # 10:30
                     (90, False),
        (120, True), (130, False),
        (160, True), (170, False),
        (200, True),  # 40:0 (i.e. just overhead)
                     (240, False),
        (240, True), (280, False),
        (280, True), (320, False),
        (320, True), # cycle 9 -> shutdown
        (320, '--stop--'),
        ]
    logger.compare(LOG)


async def test_start(circuit):
    """Test if activity starts at the right moment."""

    class Delay(redzed.FSM):
        ALL_STATES = ['begin', 'end']
        TIMED_STATES = [('begin', "0.1s", 'end')]

    redzed.Memory('slow_init', initial=[redzed.InitWait(0.05), redzed.InitValue("i")])
    logger = TimeLogger('logger', mstart=True, mstop=True)
    Delay('vclock', exit_begin=lambda: logger.log('b->e'), enter_end=circuit.shutdown)

    @redzed.triggered
    def slow_init_done(slow_init):
        logger.log(slow_init)

    await runtest(sleep=0.5)
    LOG = [(50, 'i'), (50, '--start--'), (150, 'b->e'), (150, '--stop--') ]
    logger.compare(LOG)


async def test_afterrun(circuit):
    """Test after-run example from docs"""
    class AfterRun(redzed.FSM):
        ALL_STATES = ['off', 'on', 'afterrun']
        TIMED_STATES = [
            ['afterrun', None, 'off']
        ]
        EVENTS = [
            ['start', ['off'], 'on'],
            ['stop', ['on'], 'afterrun'],
        ]

        def enter_on(self):
            self.sdata['started'] = time.time()

        def duration_afterrun(self):
            return (time.time() - self.sdata.pop('started')) * (self.x_percentage / 100.0)

        def _set_output(self, output):
            super()._set_output(output != 'off')

    logger = TimeLogger('logger', mstart=True, mstop=True)
    ar_fsm = AfterRun('ar', x_percentage = 25, enter_afterrun=lambda: logger.log('afterrun'))

    @redzed.triggered
    def monitor(ar):
        logger.log(ar)

    async def tester():
        ar_fsm.event('start')
        await asyncio.sleep(0.1)
        ar_fsm.event('stop')
        await asyncio.sleep(0.05)

    await runtest(tester())
    LOG = [
        (0, False), (0, '--start--'), (0, True),
        (100, 'afterrun'), (125, False),
        (150, '--stop--') ]
    logger.compare(LOG)
