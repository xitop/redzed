"""
Test FSM blocks.
"""

# pylint: disable=missing-class-docstring, no-member, unused-argument

import asyncio
import time

import pytest

import redzed

from .utils import Exc, Grp, ms, runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_duration(circuit):
    """Test variable timer duration."""
    PERIOD = 0.040 # 40 ms = 25 Hz
    cnt = 0

    class PWM(redzed.FSM):
        STATES = [
            ['off', None, 'on'],
            ['on', None, 'off'],
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

    @redzed.trigger
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
        (80, True),
        # 1. the timer is set to 20 ms
        # 2. duty cycle changed to: 10:30 ms
                     (100, False),
        (130, True), (140, False),
        (170, True), (180, False),
        (210, True),
        # 1. the timer is set to 10 ms
        # 2. duty cycle changed to: 40:0 ms (0 = just overhead);
                     (220, False),
        (220, True), (260, False),
        (260, True), (300, False),
        (300, True), # cycle 9 -> shutdown
        (300, '--stop--'),
        ]
    logger.compare(LOG)


async def test_start(circuit):
    """Test if activity starts at the right moment."""

    class Delay(redzed.FSM):
        STATES = [('begin', "0.1s", 'end'), 'end']
        EVENTS = []

    redzed.Memory('slow_init', initial=[redzed.InitWait(0.05), redzed.InitValue("i")])
    logger = TimeLogger('logger', mstart=True, mstop=True)
    Delay('vclock', exit_begin=lambda: logger.log('b->e'), enter_end=circuit.shutdown)

    @redzed.trigger
    def slow_init_done(slow_init):
        logger.log(slow_init)

    await runtest(sleep=0.5)
    LOG = [(50, 'i'), (50, '--start--'), (150, 'b->e'), (150, '--stop--') ]
    logger.compare(LOG)


async def test_afterrun(circuit):
    """Test after-run example from docs"""
    class AfterRun(redzed.FSM):
        STATES = ['off', 'on', ['afterrun', None, 'off']]
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

    @redzed.trigger
    def monitor(ar):
        logger.log(ar)

    async def tester():
        ar_fsm.event('start')
        await ms(100)
        ar_fsm.event('stop')
        await ms(50)

    await runtest(tester())
    LOG = [
        (0, False), (0, '--start--'), (0, True),
        (100, 'afterrun'), (125, False),
        (150, '--stop--') ]
    logger.compare(LOG)


@pytest.mark.parametrize('choose_long', [False, True])
async def test_dynamic1(circuit, choose_long):
    """Test dynamic state (after event)."""
    class TestFSM(redzed.FSM):
        STATES = [
            "ready",
            ("short", 0.01, "stop"),
            ("long",  0.03, "stop"),
            "stop"
            ]
        EVENTS = [
            ["start", ["ready"], "delay"],
            ]
        def select_delay(self):
            return "long" if choose_long else "short"
        def enter_stop(self):
            circuit.shutdown()

    fsm = TestFSM('dyn')
    logger = TimeLogger('logger', mstart=True, mstop=True, triggered_by=fsm)

    async def tester():
        fsm.event('start')
        await asyncio.sleep(0.5)

    await runtest(tester())

    LOG = [
        (0, 'ready'),
        (0, '--start--'),
        (0, 'long' if choose_long else 'short'),
        (30 if choose_long else 10, 'stop'),
        (30 if choose_long else 10, '--stop--')
        ]

    logger.compare(LOG)


@pytest.mark.parametrize('choose_long', [False, True])
async def test_dynamic2(circuit, choose_long):
    """Test dynamic state (after timed state)."""
    class TestFSM(redzed.FSM):
        STATES = [
            ["init", 0.01, "delay"],
            ("short", 0.01, "stop"),
            ("long",  0.03, "stop"),
            "stop"
            ]
        EVENTS = []
        def select_delay(self):
            return "long" if choose_long else "short"
        def enter_stop(self):
            circuit.shutdown()

    fsm = TestFSM('dyn')
    logger = TimeLogger('logger', mstart=True, mstop=True, triggered_by=fsm)

    async def tester():
        await asyncio.sleep(0.5)

    await runtest(tester())

    LOG = [
        (0, 'init'),
        (0, '--start--'),
        (10, 'long' if choose_long else 'short'),
        (40 if choose_long else 20, 'stop'),
        (40 if choose_long else 20, '--stop--')
        ]

    logger.compare(LOG)


@pytest.mark.parametrize("duration", [None, "text", ()])
async def test_duration_error_event(circuit, duration):
    """Explicit events are rejected on timer duration errors."""
    class TestFSM(redzed.FSM):
        STATES = [
            "off", ("on", None, "off")]
        EVENTS = [
            ("start", ..., "on"),
            ]

    fsm = TestFSM('myfsm')

    ERRORS = (RuntimeError, TypeError, ValueError)

    end_reached = False

    async def tester():
        nonlocal end_reached
        fsm.event("start", duration="1ms")
        assert fsm.fsm_state() == "on"
        await ms(10)
        assert fsm.fsm_state() == "off"
        with Exc(ERRORS):
            # this error is not fatal
            fsm.event("start", duration=duration)
        assert fsm.fsm_state() == "off"
        await ms(10)
        end_reached = True

    await runtest(tester())
    assert end_reached


async def test_duration_error_dynamic(circuit):
    """Test fatal timer duration error (timed state selected dynamically)."""
    class TestFSM(redzed.FSM):
        STATES = [
            "off", ("on", None, "off")]
        EVENTS = [
            ("start1", ..., "on"),
            ("start2", ..., "dyn"),
            ]
        def select_dyn(self):
            return "on"

    fsm = TestFSM('myfsm')

    async def tester():
        with Exc(RuntimeError):
            # regular event fails and that's all
            fsm.event("start1")
        assert fsm.fsm_state() == "off"
        await ms(10)
        with Exc(RuntimeError):
            # but this one is fatal (cannot remain in "dyn" state)
            fsm.event("start2")
        await asyncio.sleep(1)
        assert False, "not reached"

    with Grp(Exc(RuntimeError)):
        await runtest(tester())


async def test_duration_error_state(circuit):
    """Test fatal timer duration error (timed state after timed state)."""
    class TestFSM(redzed.FSM):
        STATES = [
            "off",
            ("on1", 0.01, "on2"),
            ("on2", None, "off"),
            ]
        EVENTS = [
            ("start", ..., "on1"),
            ]
        def duration_on2(self):
            return "invalid-duration"

    fsm = TestFSM('myfsm')

    async def tester():
        fsm.event("start")
        assert fsm.fsm_state() == "on1"     # start -> on1 was OK, but on1 -> on2 will fail
        await asyncio.sleep(1)
        assert False, "not reached"

    with Grp(Exc(ValueError, match="Invalid time representation")):
        await runtest(tester())


async def test_duration_error_init(circuit):
    """Test fatal timer duration error (timed state is initial state)."""
    class TestFSM(redzed.FSM):
        STATES = [("on", None, "off"), "off"]
        EVENTS = []

    TestFSM('myfsm')

    with Grp(Exc(RuntimeError, match="duration for state 'on'")):
        await runtest(sleep=1)


@pytest.mark.parametrize("raise_exc", [False, True])
async def test_async_init(circuit, raise_exc):
    """Test an example from docs"""

    enable_blk = redzed.Memory('enable', validator=bool, initial=redzed.InitWait(timeout=10))

    class Auto(redzed.FSM):
        STATES = ['off', 'on']
        EVENTS = [('start', ['off'], 'on')]

        def cond_start(self):
            enabled = enable_blk.get()
            if raise_exc and enabled is redzed.UNDEF:
                raise redzed.CircuitNotReady
            return enable_blk.get()

    auto_blk = Auto('auto')

    async def tester():
        await circuit.reached_state('INIT_BLOCKS')
        if raise_exc:
            with pytest.raises(redzed.CircuitNotReady):
                auto_blk.event('start')
        else:
            assert auto_blk.event('start') is False
        assert enable_blk.get() is redzed.UNDEF

        enable_blk.event('store', False)
        assert auto_blk.event('start') is False
        assert auto_blk.get() == 'off'

        enable_blk.event('store', True)
        assert auto_blk.event('start') is True
        assert auto_blk.get() == 'on'

    await runtest(tester(), immediate=True)


async def test_no_undef(circuit):
    """Test that hooks are not active during initialization."""
    log = []

    class OffOn(redzed.FSM):
        STATES = ['off', 'on']
        EVENTS = [('start', ['off'], 'on')]
        def enter_off(self):
            log.append(mem.get())

    fsm = OffOn('fsm1')
    mem = redzed.Memory('mem1', initial=[redzed.InitWait(timeout=5)])

    async def tester():
        await circuit.reached_state('INIT_BLOCKS')
        assert fsm.get() == 'off'
        assert mem.get() is redzed.UNDEF
        await asyncio.sleep(0.05)
        mem.event('store', 7)
        await asyncio.sleep(0.05)

    await runtest(tester(), immediate=True)
    assert log == [7]
