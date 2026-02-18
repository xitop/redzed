"""
Test the QueueBuffer + OutputWorker combination.
"""

# pylint: disable=unused-argument

import asyncio
import time

import pytest

import redzed

from .utils import TimeLogger, runtest

pytestmark = pytest.mark.usefixtures("task_factories")

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


async def output_worker(
        circuit, *,
        t23=0.05, log, test_error=False,
        stop_value=redzed.UNDEF, stop_function=False, attach=False,
        **kwargs):

    async def wait70(arg):
        logger.log(f'start {arg}')
        if test_error and arg == 'i2':
            # pylint: disable=pointless-statement
            1/0     # BOOM!
        await asyncio.sleep(0.07)
        logger.log(f'stop {arg}')
        return f'ok {arg}'

    logger = TimeLogger('logger', mstop=True)
    inp = redzed.Memory('inp', initial='i1')
    if stop_function:
        buff = redzed.QueueBuffer('buff', triggered_by='inp')
        @redzed.stop_function
        def stop():
            buff.event('put', stop_value)
    else:
        buff = redzed.QueueBuffer('buff', triggered_by='inp', stop_value=stop_value)

    if attach:
        buff2 = buff.attach_output(aw_func=wait70, **kwargs)
        assert buff2 == buff
        assert list(circuit.get_items(redzed.OutputWorker)) \
            == [circuit.resolve_name('buff_io')]
    else:
        redzed.OutputWorker('out', aw_func=wait70, buffer=buff, **kwargs)

    async def tester():
        """
        value 'i1' (initial)
            wait 40ms
        value 'i3'
            wait t23 (50ms default)
        value 'i3'
            wait 30ms
        stop
        """
        await asyncio.sleep(0.04)
        inp.event('store', 'i2')    # put into the queue indirectly (Memory->Trigger->Buffer)
        await asyncio.sleep(t23)
        buff.event('put', 'i3')     # put into the queue directly
        await asyncio.sleep(0.03)

    try:
        await runtest(tester())
        logger.log("END")
    finally:
        logger.compare(log)


@pytest.mark.parametrize('attach', [False, True])
async def test_1_worker(circuit, attach):
    """Test basic QueueBuffer function."""
    LOG = [
        (0, 'start i1'),
        # time 40: i2 was put into the queue
        (70, 'stop i1'),
        (70, 'start i2'),
        # time 90: i3 was put into the queue
        (120, '--stop--'),
        (140, 'stop i2'),
        (140, 'start i3'),
        (210, 'stop i3'),
        (210, 'END')
        ]
    await output_worker(circuit, log=LOG, attach=attach)


@pytest.mark.parametrize('attach', [False, True])
async def test_2_workers(circuit, attach):
    """Test 2 workers."""
    LOG = [
        (0, 'start i1'),    # worker 1
        # time 40: i2 was put into the queue
        (40, 'start i2'),   # worker 2
        (70, 'stop i1'),
        # time 90: i3 was put into the queue
        (90, 'start i3'),   # worker 1
        (110, 'stop i2'),
        (120, '--stop--'),
        (160, 'stop i3'),
        (160, 'END')
        ]
    await output_worker(circuit, workers=2, log=LOG, attach=attach)


@pytest.mark.parametrize('attach', [False, True])
async def test_3_workers(circuit, attach):
    """Test 2 workers."""
    LOG = [
        (0, 'start i1'),    # worker 1
        # time 40: i2 was put into the queue
        (40, 'start i2'),   # worker 2
        # time 50: i3 was put into the queue
        (60, 'start i3'),   # worker 3
        (70, 'stop i1'),
        (90, '--stop--'),   # 40+20+30
        (110, 'stop i2'),
        (130, 'stop i3'),
        (130, 'END')
        ]
    await output_worker(circuit, t23=0.02, workers=3, log=LOG, attach=attach)


async def test_worker_error(circuit):
    LOG = [
        (0, 'start i1'),
        (70, 'stop i1'),
        (70, 'start i2'),   # will fail immediately
        (70, '--stop--'),
        # (0, 'END'), not reached
        ]
    with Grp(Exc(ZeroDivisionError)):
        await output_worker(circuit, test_error=True, log=LOG)


@pytest.mark.parametrize("stop_function", [False, True])
async def test_stop_value(circuit, stop_function):
    """Test the stop value in start mode."""
    LOG = [
        (0, 'start i1'),
        (70, 'stop i1'),
        (70, 'start i2'),
        (120, '--stop--'),
        (140, 'stop i2'),
        (140, 'start i3'),
        (210, 'stop i3'),
        (210, 'start CLEANUP'),
        (280, 'stop CLEANUP'),
        (280, 'END')
        ]
    await output_worker(circuit, stop_value='CLEANUP', stop_function=stop_function, log=LOG)


async def test_threads(circuit):
    """Test execution in a thread."""
    def blocking(a, b, c=0):
        time.sleep(0.04)
        logger.log(100*a + 10*b + c)

    # Python 3.12+ @inspect.markcoroutinefunction
    def adapter(v):
        return asyncio.to_thread(blocking, **v)

    logger = TimeLogger('log')
    buff1 = redzed.QueueBuffer("buff1")
    buff2 = redzed.QueueBuffer("buff2")
    redzed.OutputWorker("out1", aw_func=adapter, buffer=buff1)
    redzed.OutputWorker("out2", aw_func=adapter, buffer=buff2)

    async def tester():
        # pylint: disable=use-dict-literal
        buff1.event('put', dict(a=1, b=2, c=3))
        buff1.event('put', dict(a=7, b=8, c=9))
        await asyncio.sleep(0.02)
        buff2.event('put', dict(a=1, b=2))
        buff2.event('put', dict(a=7, b=8))

    await runtest(tester())
    LOG = [(40, 123), (60, 120), (80, 789), (100, 780)]
    logger.compare(LOG)


async def test_validator(circuit):
    """Test the data validator."""
    log = []

    async def asynclog(value):
        log.append(value)

    def odd100(value):
        if value % 2:
            return value+100
        raise ValueError("No even numbers")

    buff = redzed.QueueBuffer("buff", validator=odd100, stop_value = 55)
    redzed.OutputWorker("out", aw_func=asynclog, buffer=buff)

    async def tester():
        for x in range(10):
            try:
                buff.event('put', x)
            except ValueError:
                pass
        await asyncio.sleep(0)
    await runtest(tester())
    assert log == [101, 103, 105, 107, 109, 155]
