"""
Test the TimeSpan block as much as possible in short time.
"""

# pylint: disable=unused-argument

import asyncio
import datetime as dt
import time

import pytest

import redzed

from .utils import TimeLogger, runtest, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_init_default(circuit):
    null = redzed.TimeSpan('null')
    empty = redzed.TimeSpan('empty', initial=[])

    async def tester():
        assert not null.get()
        assert null.rz_export_state() == []
        assert not empty.get()
        assert empty.rz_export_state() == []

    await runtest(tester())


async def test_args(circuit):
    arg = [
        [[2025, 3, 1, 12, 0], [2025, 3, 7, 18, 30, 1, 150_000]],
        [[2025, 10, 10, 10, 30, 0], [2025, 10, 10, 22, 0, 0]],
    ]
    td_num = redzed.TimeSpan('num_args', initial=arg) #redzed.InitValue(arg))

    for sub_interval in arg:
        for endpoint in sub_interval:
            endpoint.extend([0] * (7-len(endpoint)))    # right-pad to 7 ints

    async def tester():
        assert td_num.rz_export_state() == td_num.event('_get_config') == arg
        arg[1][1] = arg[0][1]
        del arg[0]
        td_num.event('reconfig', arg)
        assert td_num.rz_export_state() == td_num.event('_get_config') == arg

    await runtest(tester())


async def test_yesno(circuit):
    yes1 = redzed.TimeSpan("yes1", initial=[[[2001, 5, 1, 0, 0], [9999, 5, 4, 0, 0]]])
    # in the past:
    no1 = redzed.TimeSpan("no1", initial=[[[1970, 1, 1, 0, 0], [1987, 12, 31 ,0, 0]]])
    # backwards:
    no2 = redzed.TimeSpan("no2", initial=[[[2500, 1, 25, 0, 0], [1990, 1, 15, 1, 0, 0]]])

    async def tester():
        assert yes1.get()      # always on
        assert not no1.get()   # always off
        assert not no2.get()   # always off

    await runtest(tester())


def _dt_to_i7(datetime):
    return [*datetime.timetuple()[:6], datetime.microsecond]


@pytest.mark.parametrize('dynamic', [False, True])
async def tfsec(circuit, dynamic):
    """Activate for a fraction of a second."""
    logger = TimeLogger('logger', mstop=True, triggered_by="fsec")
    now = time.time()
    config = [
        [ _dt_to_i7(dt.datetime.fromtimestamp(now + 0.12)),
          _dt_to_i7(dt.datetime.fromtimestamp(now + 0.28))]
        ]
    s1 = redzed.TimeSpan("fsec", initial=redzed.UNDEF if dynamic else config)

    async def tester():
        if dynamic:
            s1.event('reconfig', config)
        await asyncio.sleep(0.35)

    await runtest(tester())

    LOG = [
        (0, False),
        (120, True),
        (280, False),
        (350, '--stop--'),
        ]
    logger.compare(LOG)


async def test_persistent(circuit):
    td = redzed.TimeSpan("pers", initial=redzed.RestoreState())
    storage = {}
    circuit.set_persistent_storage(storage)
    conf = []

    async def tester1():
        nonlocal conf
        assert td.rz_export_state() == []
        conf = [
            [[2015,5,4,3,2,1,0], [2035,9,8,7,6,5,0]],
            [[2020,1,2,3,40,50,600], [2030,8,9,10,11,12,0]],
            ]
        td.event('reconfig', conf)
        assert td.rz_export_state() == conf

    await runtest(tester1())
    assert strip_ts(storage)[td.rz_key] == conf
    del td

    redzed.reset_circuit()
    td = redzed.TimeSpan("pers", initial=redzed.RestoreState())
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)

    async def tester2():
        nonlocal conf
        assert td.rz_export_state() == conf
        del conf[0]
        td.event('reconfig', conf)  # state saved after each event
        assert td.rz_export_state() == conf

    await runtest(tester2())
    assert strip_ts(storage)[td.rz_key] == conf
