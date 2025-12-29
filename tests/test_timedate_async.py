"""
Test the TimeDate block.
"""

# pylint: disable=unused-argument

import asyncio
import datetime as dt
import time

import pytest

import redzed
from redzed.utils import parse_interval

from .utils import TimeLogger, runtest, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_config(circuit):
    """Test the loading of config."""
    config = {
        'dates': [[[6,21], [12,20]]],
        'times': [[[1,30], [2,45,0]], [[17,1,10,50_000], [17,59,10,0]]],
        'weekdays': [1,7],
    }
    config_full = config.copy()
    config_full['times'] = [[[1,30,0,0], [2,45,0,0]], [[17,1,10,50_000], [17,59,10,0]]]

    td = redzed.TimeDate('td', initial=config)
    td2 = redzed.TimeDate('td2')

    async def tester():
        cfg = td.rz_export_state()
        td2.event('reconfig', cfg)
        cfg2 = td2.rz_export_state()
        assert cfg == cfg2 == config_full

    await runtest(tester())


async def _test6(circuit, *p6):
    yes1, yes2, no1, no2, ying, yang = [
        redzed.TimeDate(f"tmp_{i}", initial=cfg) for i, cfg in enumerate(p6)]

    async def tester():
        assert yes1.get()      # always on
        assert yes2.get()      # always on
        assert not no1.get()   # always off
        assert not no2.get()   # always off
        # either a or b; a race is possible, but repeated race condition cannot happen
        if ying.get() == yang.get():
            assert ying.get() != yang.get()

    await runtest(tester())


async def test_times(circuit):
    now = dt.datetime.today()
    othm = 13 - now.month

    def _tparse(t):
        return [int(n) for n in t.split(':')]

    def iparse(i):
        return parse_interval(i, sep=['-', '/'], parser=_tparse)

    await _test6(
        circuit,
        {'times': iparse('0:0 / 0:0')},
        {'times': [[[now.hour, now.minute], [(now.hour+1) % 24, now.minute]]]},
        {'times': [[[0,0],[0,0]]], 'dates': [[[othm, 2], [othm, 27]]]},
        {'times': iparse(f"{(now.hour+1) % 24}:{now.minute}-{(now.hour+2) % 24}:{now.minute}")},
        {'times': iparse('0:0:0 - 12:0:0')},
        {'times': iparse('12:0-0:0')},
        )


async def test_dates(circuit):
    now = dt.date.today()
    nowm = now.month
    await _test6(
        circuit,
        {'dates': [[[1,1], [12,31]]]},
        {'dates': [[[nowm, now.day], [nowm % 12 + 1, 15]]]},
        {'dates': [[[1,1], [12,31]]], 'weekdays': []},
        {'dates': [[[nowm % 12 + 1, 1], [(nowm+1) % 12 + 1, 20]]]},
        {'dates': [[[12,21], [6,20]]]},
        {'dates': [[[6,21], [12,20]]]},
        )

async def test_weekdays(circuit):
    other_hour = (dt.datetime.now().hour + 3) % 24
    await _test6(
        circuit,
        {'weekdays': [1,2,3,4,5,6,7]},
        {'weekdays': [0,1,2,3,4,5,6]},
        {'weekdays': [1,2,3,4,5,6,7], 'times': f'{other_hour}:0 - {other_hour}:59:59'},
        {'weekdays': []},
        {'weekdays': [1,3,5,7]},
        {'weekdays': [2,4,6]},
        )


def _dt_to_i7(datetime):
    return [*datetime.timetuple()[:6], datetime.microsecond]

@pytest.mark.parametrize('dynamic', [False, True])
async def test_fsec(circuit, dynamic):
    """Activate for a fraction of a second."""
    logger = TimeLogger('logger', mstop=True, triggered_by="fsec")
    while True:
        now = time.time()
        begin =_dt_to_i7(dt.datetime.fromtimestamp(now + 0.12))
        end = _dt_to_i7(dt.datetime.fromtimestamp(now + 0.28))
        if begin[2] == end[2]:      # msut be within the same day
            break
        await asyncio.sleep(0.5)
    config = {
        'times': [ [begin[3:], end[3:]] ],      # h, m, s, ms
        'dates': [ [begin[1:3], end[1:3]] ],    # month, day
        'weekdays': list(range(7)),
    }
    s1 = redzed.TimeDate("fsec", initial=redzed.UNDEF if dynamic else config)

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


async def test_cron(circuit):
    """Test the cron service, internal state."""
    targ = [[[1,2,3,5000], [2,3,4,0]]]
    td = redzed.TimeDate("local", initial={'times': targ, 'dates': [[[4,1], [4,1]]]})
    redzed.TimeDate("local2", initial={'weekdays': [6, 7]})
    cron = circuit.resolve_name('_cron_local')

    tdu = redzed.TimeDate(
        "utc",
        utc=True,
        initial=redzed.InitValue({'times': [[[10,11,12], [13,14,15]], [[14,15], [16,17,0]]]})
        )
    cronu = circuit.resolve_name('_cron_utc')

    async def tester():
        tinit = {'times': targ, 'dates': [[[4,1], [4,1]]], 'weekdays': None}
        assert td.rz_export_state() == tinit

        config = cron.event('_get_config')
        assert config['alarms'] == {
            '00:00:00': ['local', 'local2'],
            '01:02:03.005000': ['local'],
            '02:03:04': ['local']}
        assert config['blocks'] == {
            'local': ['00:00:00', '01:02:03.005000', '02:03:04'], 'local2': ['00:00:00']}
        config = cronu.event('_get_config')
        assert config['alarms'] == {
            '10:11:12': ['utc'], '13:14:15': ['utc'], '14:15:00': ['utc'], '16:17:00': ['utc']}
        assert config['blocks'] == {'utc': ['10:11:12', '13:14:15', '14:15:00', '16:17:00']}

        td.event('reconfig', {'times': []})
        config = cron.event('_get_config')
        assert config['alarms'] == {'00:00:00': ['local2']}
        assert config['blocks'] == {'local': [], 'local2': ['00:00:00']}

        conf = {'times': [[[20,20,0,0], [8,30,0,0]]], 'dates': None, 'weekdays': [4]}
        tdu.event('reconfig', conf)
        config = cronu.event('_get_config')
        assert config['alarms'] == {
            '00:00:00': ['utc'], '08:30:00': ['utc'], '20:20:00': ['utc']}
        assert config['blocks'] == {'utc': ['00:00:00', '08:30:00','20:20:00']}

        assert tdu.rz_export_state() == conf

    await runtest(tester())


async def test_persistent(circuit):
    td = redzed.TimeDate(
        "pers", initial=[redzed.RestoreState(), redzed.InitValue({'dates': []})])
    storage = {}
    circuit.set_persistent_storage(storage)
    conf = None

    async def tester1():
        nonlocal conf
        assert td.rz_export_state() == {'times': None, 'dates': [], 'weekdays': None}
        conf = {'times':[[[1,0],[2,0]]], 'weekdays': [7]}
        td.event('reconfig', conf)
        # fill-in missing default values
        conf['times'][0] = [[1,0,0,0],[2,0,0,0]]
        conf['dates'] = None
        assert td.rz_export_state() == conf

    await runtest(tester1())
    assert strip_ts(storage)[td.rz_key] == conf

    redzed.reset_circuit()
    td = redzed.TimeDate("pers", initial=redzed.RestoreState())
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)

    async def tester2():
        assert td.rz_export_state() == conf

    await runtest(tester2())
    assert strip_ts(storage)[td.rz_key] == conf
