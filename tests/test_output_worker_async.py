"""
Test the QueueBuffer + OutputWorker combination.
"""

# pylint: disable=unused-argument

import asyncio
import logging
import time

import pytest

import redzed

from .utils import Exc, Grp, ms, runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")


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
        await ms(70)
        logger.log(f'stop {arg}')
        return f'ok {arg}'

    logger = TimeLogger('logger', mstop=True)
    inp = redzed.Memory('inp', initial='i1')
    if stop_function:
        buff = redzed.QueueBuffer('q_buff', triggered_by='inp')
        @redzed.stop_function
        def stop():
            buff.event('put', stop_value)
    else:
        buff = redzed.QueueBuffer('q_buff', triggered_by='inp', stop_value=stop_value)

    if attach:
        buff2 = buff.attach_output(aw_func=wait70, **kwargs)
        assert buff2 == buff
        assert list(circuit.get_items(redzed.OutputWorker)) \
            == [circuit.resolve_name('q_io')]
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
        await ms(40)
        inp.event('store', 'i2')    # put into the queue indirectly (Memory->Trigger->Buffer)
        await asyncio.sleep(t23)
        buff.event('put', 'i3')     # put into the queue directly
        await ms(30)

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
        await ms(20)
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
            except redzed.ValidationError:
                pass
        await asyncio.sleep(0)
    await runtest(tester())
    assert log == [101, 103, 105, 107, 109, 155]


async def test_shutdown(circuit, caplog):
    """Test async shutdown."""
    logger = TimeLogger('logger', mstop=True)

    async def worker(w):
        logger.log(f"start {w}")
        try:
            await asyncio.sleep(0.05 if w == "C" else 2)
        except asyncio.CancelledError:
            logger.log(f"timeout {w}")
            if w == "A":
                logger.log(f"no exit {w}")
                # the "A" task refuses to exit after cancel
                # and will be abandoded by redzed
                await asyncio.sleep(2)
            logger.log(f"cancelled {w}")
            raise
        logger.log(f"done {w}")


    worker = redzed.QueueBuffer(
        'async_out').attach_output(aw_func=worker, workers=4, stop_timeout=0.15)

    async def tester():
        worker.event('put', "A")
        await ms(10)
        worker.event('put', "B")
        await ms(10)
        worker.event('put', "C")
        await ms(10)

    caplog.set_level(logging.WARNING)
    await runtest(tester())
    logger.log("terminated")

    LOG = [
        (0, "start A"),
        (10, "start B"),
        (20, "start C"),
        (30, "--stop--"),
        (70, "done C"),
        (180, "timeout A"),
        (180, "no exit A"),
        (180, "timeout B"),
        (180, "cancelled B"),
        (180, "terminated"),
    ]
    logger.compare(LOG)
    assert len(caplog.messages) >= 1
    assert "1 worker(s) did not stop" in caplog.messages[0]


async def test_buffer_size(circuit):
    """Test _get_size event."""
    qs = 0

    async def worker(_):
        nonlocal qs
        qs -= 1
        await ms(32)

    out = redzed.QueueBuffer('buffer').attach_output(aw_func=worker)

    async def tester():
        nonlocal qs
        for i in range(14):
            if i < 5:
                out.event('put', 0)
                qs += 1
            assert 0 <= redzed.send_event('buffer', '_get_size') == qs <= 5
            await ms(10)

    await runtest(tester())
