"""
Test the MemoryBuffer + OutputController combination.
"""

# pylint: disable=unused-argument

import asyncio

import pytest

import redzed

from .utils import TimeLogger, runtest

pytestmark = pytest.mark.usefixtures("task_factories")

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


async def output_ctrl(
        circuit, *,
        log,
        t12=0.01, t23=0.01,
        test_error=False, rest_time=0.04, **kwargs):

    async def work_80(arg):
        logger.log(f'start {arg}')
        if test_error:
            # pylint: disable=pointless-statement
            logger.log("error!")
            1/0     # BOOM!
        try:
            await asyncio.sleep(0.08)
        except asyncio.CancelledError:
            logger.log(f"cancel {arg}")
            raise
        logger.log(f'stop {arg}')
        return f'ok {arg}'

    inp = redzed.Memory('inp', initial='i1')
    buff = redzed.MemoryBuffer(
        'buff', triggered_by='inp', stop_value=kwargs.pop('stop_value', redzed.UNDEF))
    redzed.OutputController(
        'out', aw_func=work_80, buffer=buff, rest_time=rest_time, **kwargs)
    logger = TimeLogger('logger', mstop=True)

    async def tester():
        await asyncio.sleep(t12)
        buff.event('put', 'i2')
        await asyncio.sleep(t23)
        inp.event('store', 'i3')
        await asyncio.sleep(0.04)

    try:
        await runtest(tester())
    finally:
        logger.log("END")
        logger.compare(log)


async def test_controller(circuit):
    LOG = [
        (0, 'start i1'),
        (30, 'cancel i1'), # i2 cancels i1
        (70, 'start i2'),
        (150, 'stop i2'),
        # 160 i3 -> buffer
        # 190 end of the rest time after i2
        (190, 'start i3'),
        (200, '--stop--'),
        (270, 'stop i3'),
        # 310: end of the rest time after i3
        (310, 'END')
        ]
    await output_ctrl(circuit, t12=0.03, t23=0.13, log=LOG)


async def test_stop_timeout(circuit):
    LOG = [
        (0, 'start i1'),
        (80, 'stop i1'),
        # 100 i2 -> buffer
        # 110 i3 -> buffer
        (120, 'start i3'),  # i3 would normally stop at time 200
        (150, '--stop--'),  # stop timeout (45 ms) start
        (195, 'cancel i3'), # timed out -> cancel task -> start rest_time 40ms
        (225, 'END')
        ]
    await output_ctrl(circuit, t12=0.1, stop_timeout=0.045, log=LOG)


async def test_no_rest_time(circuit):
    LOG = [
        (0, 'start i1'),
        (10, 'cancel i1'),
        (10, 'start i2'),
        (90, 'stop i2'),
        (110, 'start i3'),
        (150, '--stop--'),
        (190, 'stop i3'),
        (190, 'END')
        ]
    await output_ctrl(circuit, t23=0.1, rest_time=0, log=LOG)


async def test_rest_time_after_error1(circuit):
    """Rest time sleep is performed also after an error."""
    LOG = [
        (0, 'start i1'),
        (0, 'error!'),
        (0, '--stop--'),
        # 100 event put i2 -> CircuitShutDown error
        (120, 'END')
        ]
    with Grp(Exc(ZeroDivisionError), Exc(redzed.CircuitShutDown, match="shut down")):
        await output_ctrl(circuit, test_error=True, rest_time=0.12, log=LOG)


async def test_rest_time_after_error2(circuit):
    """Rest time sleep is performed also after an error."""
    # different timing as in above
    LOG = [
        (0, 'start i1'),
        (0, 'error!'),
        (0, '--stop--'),
        (40, 'END')
        ]
    with Grp(Exc(ZeroDivisionError)):
        await output_ctrl(circuit, t12=0.1, test_error=True, log=LOG)


async def test_stop_value(circuit):
    """Test the stop value."""
    LOG = [
        (0, 'start i1'),
        (10, 'cancel i1'), # i2 cancels i1
        (10, 'start i2'),
        (20, 'cancel i2'), # i3 cancels i2
        (20, 'start i3'),
        (60, '--stop--'),
        (60, 'cancel i3'),
        (60, 'start CLEANUP'),
        (140, 'stop CLEANUP'),
        (140, 'END')
        ]
    await output_ctrl(circuit, stop_value='CLEANUP', rest_time=0, log=LOG)


async def test_rest_time_too_long(circuit):
    async def dummy():
        pass

    with pytest.raises(ValueError, match="shorter than"):
        redzed.OutputController(
            'not_OK',
            buffer=redzed.MemoryBuffer(redzed.unique_name()),
            aw_func=dummy, rest_time=1.5, stop_timeout=1.0)
