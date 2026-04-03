"""
Test the OutputFunc block.
"""

# pylint: disable=unused-argument

import asyncio

import pytest

import redzed

from .utils import Exc, Grp, runtest, TimeLogger

pytestmark = pytest.mark.usefixtures("task_factories")



async def output_func(circuit, *, log, v2=2, **kwargs):
    def worker(evalue):
        v = 12 // evalue
        logger.log(v)
        return 100+v

    inp = redzed.Memory('input', initial=6)
    logger = TimeLogger('logger', mstop=True)
    echo = redzed.OutputFunc('output', func=worker, **kwargs)
    @redzed.trigger
    def mem2echo(v='input'):
        d = echo.event('put', v)
        assert v * (d-100) == 12

    async def tester():
        await asyncio.sleep(0.05)
        inp.event('store', v2)
        await asyncio.sleep(0.05)
        assert inp.event('store', 3)

    await runtest(tester())
    logger.log("END")
    logger.compare(log)


async def test_basic(circuit):
    LOG = [
        (0, 2),
        (50, 6),
        (100, 4),
        (100, '--stop--'),
        (100, 'END')
        ]
    await output_func(circuit, log=LOG)


async def test_trigger_by(circuit):
    """Test triggered_by=..."""
    log1 = []
    log2 = []
    log3 = []
    cnt = redzed.Counter('counter', modulo=4)
    redzed.OutputFunc('out1', func=log1.append)
    redzed.OutputFunc('out2', func=log2.append, triggered_by='counter')
    redzed.OutputFunc('out3', func=log3.append, triggered_by=cnt)

    @redzed.trigger
    def cnt2out(counter):
        redzed.send_event('out1', 'put', counter)

    async def tester():
        for _ in range(10):
            cnt.event('inc')

    await runtest(tester())
    assert log1 == log2 == log3 == [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2]


async def test_on_error_abort(circuit):
    with Grp(Exc(
            ZeroDivisionError,
            match="<OutputFunc output>: Error occurred during handling of event 'put'")):
        await output_func(circuit, v2=0, log=[])


async def test_stop(circuit):
    """Test the stop arguments."""
    LOG = [
        (0, 2),
        (50, 6),
        (100, 4),
        (100, 1),       # stop function runs before block stop
        (100, '--stop--'),
        (100, 'END')
        ]
    await output_func(circuit, v2=2, stop_value=12, log=LOG)


@pytest.mark.parametrize("stop_function", [False, True])
async def test_stop_value(circuit, stop_function):
    """Test disabled service after stop."""
    saved_arg = None

    def save_arg(sa):
        nonlocal saved_arg
        saved_arg = sa

    async def tester():
        for x in range(5):
            out.event('put', x)
            assert saved_arg == x

    if stop_function:
        out = redzed.OutputFunc("outf", func=save_arg)
        @redzed.stop_function
        def stop():
            out.event('put', 99)
    else:
        out = redzed.OutputFunc("outf", func=save_arg, stop_value=99)
    await runtest(tester())

    assert saved_arg == 99
    with Exc(redzed.CircuitShutDown, match="has been shut down"):
        out.event('put', 0)
