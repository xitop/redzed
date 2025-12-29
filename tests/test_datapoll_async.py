"""
Test the DataPoll block.
"""

# pylint: disable=unused-argument

import asyncio

import pytest

import redzed

from .utils import runtest, TimeLogger, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


async def test_poll(circuit):
    """Test the basic value polling."""
    n = 0
    def acq():
        nonlocal n
        n += 1
        return n

    logger = TimeLogger('logger', triggered_by='dp')
    redzed.DataPoll('dp', func=acq, interval='0m0.04s', initial=redzed.InitWait(0.1))
    await runtest(sleep=0.27)

    LOG = [
        (0, 1),
        (40, 2),
        (80, 3),
        (120, 4),
        (160, 5),
        (200, 6),
        (240, 7)]
    logger.compare(LOG)


def _data_source(*data):
    queue = asyncio.Queue()
    for d in data:
        queue.put_nowait(d)
    return queue.get


async def test_async(circuit):
    """Test an async data acquisition function."""
    logger = TimeLogger('logger', mstop=True)
    redzed.DataPoll(
        'dp', func=_data_source("A", "E", "I"),
        interval='0m0.035s', initial=redzed.InitWait(0.1))

    @redzed.triggered
    def dp_to_logger(dp):
        logger.log(dp)

    await runtest(sleep=0.16)

    LOG = [
        (0, 'A'),
        (35, 'E'),
        (70, 'I'),     # no more data in queue
        (160, '--stop--')]
    logger.compare(LOG)


async def test_init_done(circuit):
    """Successful initialization stops the InitWait."""
    logger = TimeLogger('logger', mstop=True)
    redzed.DataPoll(
        'dp',
        func=_data_source(redzed.UNDEF, redzed.UNDEF, 1, 2, 3, 4),
        interval='0m0.05s', initial=redzed.InitWait(0.3))

    @redzed.triggered
    def dp_to_logger(dp):
        logger.log(dp)

    async def wait_init():
        await circuit.reached_state(redzed.CircuitState.RUNNING)
        logger.log("--running--")

    asyncio.create_task(wait_init())
    await runtest(immediate=True, sleep=0.18)

    LOG = [
        (100, 1),
        (100, "--running--"),
        (150, 2),
        (180, '--stop--')]
    logger.compare(LOG)


async def test_undef(circuit):
    """UNDEF means data not available."""
    n = 0
    def acq():
        nonlocal n
        n += 1
        return n if n not in (1, 3, 6) else redzed.UNDEF

    redzed.DataPoll(
        'dp',
        func=acq,
        interval=0.03, initial=redzed.InitWait(0.1))
    logger = TimeLogger('logger', mstop=True, triggered_by='dp')
    await runtest(immediate=True, sleep=0.26)

    LOG = [
        # (0, 1) missing, initialization not finished
        (30, 2),
        # (60, 3), missing
        (90, 4),
        (120, 5),
        # (150, 6), also missing
        (180, 7),
        (210, 8),
        (240, 9),
        (260, "--stop--")]
    logger.compare(LOG)


async def test_counter_1(circuit):
    """Test the output counter."""
    n = -1
    def acq():
        nonlocal n
        n += 1
        return n*5

    logger = TimeLogger('logger', mstop=True)
    redzed.DataPoll('dp', func=acq, output_counter=True, interval=0.02)
    @redzed.triggered
    def _to_logger(dp):
        logger.log(dp)
    await runtest(sleep=0.11)

    LOG = [(n*20, (n*5, n)) for n in range(6)] + [(110, "--stop--")]
    logger.compare(LOG)


@pytest.mark.parametrize("counter", [False, True])
async def test_counter_2(circuit, counter):
    """Test the counter with UNDEF and repeated value."""
    logger = TimeLogger('logger', triggered_by='dp')
    redzed.DataPoll(
        'dp',
        func=_data_source("A", "B", redzed.UNDEF, "C", "C", "D"),
        output_counter=counter,
        interval=0.02)
    await runtest(sleep=0.11)

    LOG_C = [
        (0, ("A", 0)),
        (20, ("B", 1)),
        # (40, (???))   missing, no data
        (60, ("C", 2)),
        (80, ("C", 3)),
        (100, ("D", 4)),
    ]

    LOG_NC = [(0, "A"), (20, "B"), (60, "C"), (100, "D")]

    logger.compare(LOG_C if counter else LOG_NC)


@pytest.mark.parametrize("failures", [0, 1, 3, 5])
async def test_abort(circuit, failures):
    """Test abort_after_failures"""
    n = 0
    def gen():
        nonlocal n
        n += 1
        return redzed.UNDEF if n == 3 or 7 <= n <= 10 else n
        # 1 2 - 4 5 6 - - - - 11 12 ...

    cnt = 0
    redzed.DataPoll('dp', func=gen, abort_after_failures=failures, interval=0.02)
    @redzed.triggered
    def count_values(dp):
        nonlocal cnt
        cnt += 1

    if failures == 0 or failures >= 5:
        await runtest(sleep=0.32)
        assert n == 16          # first value 1 + 15 polling cycles,
        assert cnt == n - 5     # 5 missing
    else:
        with Grp(Exc(RuntimeError, match="No data")):
            await runtest(sleep=0.20)
        if failures == 1:
            assert cnt == 2    # stop after 1, 2
        else:
            assert cnt == 5    # stop after 1, 2, 4, 5, 6


async def test_no_abort(circuit):
    """Test abort_after_failures=0"""
    n = 0
    def gen():
        nonlocal n
        n += 1
        return redzed.UNDEF if 5 <= n < 10 else n

    cnt = 0
    redzed.DataPoll('dp', func=gen, interval=0.012)     # abort_after_failures=0 is default
    @redzed.triggered
    def count_values(dp):
        nonlocal cnt
        cnt += 1

    await runtest(sleep=0.25)
    assert cnt == n - 5 == 16       # 1 initial + 250//12 polls - 5 undefs


async def test_init_timeout(circuit):
    """Test the initialization time_out."""
    logger = TimeLogger('logger', triggered_by='dp')
    redzed.DataPoll(
        'dp',
        func=lambda: redzed.UNDEF,  # it never delivers
        interval=2,                 # don't care
        initial=[redzed.InitWait(0.08), redzed.InitValue('DEFAULT')])
    await runtest(sleep=0.12)
    logger.compare([(80, 'DEFAULT')])


async def test_init_failure(circuit):
    """Test failed init."""
    logger = TimeLogger('logger', mstop=True)
    redzed.DataPoll(
        'dp',
        func=lambda: redzed.UNDEF,      # func never delivers
        interval=1,                     # don't care
        initial=redzed.InitWait(0.04))  # no InitValue()
    with Grp(Exc(RuntimeError, match="not initialized")):
        await runtest(sleep=0)
    logger.compare([(40, '--stop--')])


async def test_immediate_init(circuit):
    """Test init without waiting for it."""
    poller = redzed.DataPoll('out7', func=lambda: 7, interval=1)
    logger = TimeLogger('logger', mstop=True, triggered_by=poller)
    await runtest(sleep=0.04)
    logger.compare([(0, 7), (40, '--stop--')])


async def _do_test_async_init_timeout(init_timeout, slog):
    """Test the async initialization time_out."""
    async def w3():
        await asyncio.sleep(0.1)
        return 3
    logger = TimeLogger('logger', triggered_by='dp')
    redzed.DataPoll(
        'dp',
        func=w3,
        interval=10,                # don't care
        initial=[redzed.InitWait(init_timeout), redzed.InitValue('DEFAULT')])

    await runtest(sleep=0)
    logger.compare(slog)


async def test_async_init_timeout_1(circuit):
    """Test the async initialization time_out > polling function delay."""
    await _do_test_async_init_timeout(0.2, [(100, 3)])


async def test_async_init_timeout_2(circuit):
    """Test the async initialization time_out < polling function delay."""
    await _do_test_async_init_timeout(0.05, [(50, 'DEFAULT')])


async def test_validator(circuit):
    """Test data validation."""
    n = 1
    def gen():
        nonlocal n
        n += 1
        return n

    def even_only(n):
        if n % 2:
            raise ValueError("Odd!")
        return n

    cnt = 0
    redzed.DataPoll('dp', func=gen, validator=even_only, interval=0.007, initial=0)
    @redzed.triggered
    def count_values(dp):
        nonlocal cnt
        cnt += 1

    await runtest(sleep=0.2)
    assert cnt == n // 2


async def test_timing_adjustment(circuit):
    """Time spent in an async function is taken into account."""
    n = 0
    async def gen():
        nonlocal n
        n += 1
        logger.log("gen")
        await asyncio.sleep(0.011 * n)
        return n

    logger = TimeLogger('logger', triggered_by='dp', mstop=True)
    redzed.DataPoll('dp', func=gen, interval=0.04, initial="init")
    await runtest(sleep=0.24)

    LOG = [
        (0, "gen"),     # sleep 11
        (0, "init"),
        (11, 1),
        (40, "gen"),    # sleep 22
        (62, 2),
        (80, "gen"),    # sleep 33
        (113, 3),
        (120, "gen"),   # sleep 44 > 40!
        (164, 4),
        (164, "gen"),   # sleep 55 > 40!
        (219, 5),
        (219, "gen"),
        (240, '--stop--'),
        ]
    logger.compare(LOG)


async def test_persistence(circuit):
    storage = {}
    # circuit1: test saving
    circuit.set_persistent_storage(storage)
    dp1 = redzed.DataPoll(
        'pers', func=lambda: redzed.UNDEF, interval=1,
        initial=[redzed.RestoreState(), redzed.InitValue(33)])
    await runtest(sleep=0.05)
    assert dp1.get() == 33
    assert strip_ts(storage)[dp1.rz_key] == 33
    redzed.reset_circuit()
    del dp1

    # circuit2: saved value not needed
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)
    dp2 = redzed.DataPoll(
        'pers', func=lambda: 22, interval=1,
        initial=[redzed.RestoreState(), redzed.InitValue(11)])
    await runtest(sleep=0.05)
    assert dp2.get() == 22
    assert strip_ts(storage)[dp2.rz_key] == 22
    redzed.reset_circuit()
    del dp2

    # circuit3: saved value used
    circuit = redzed.get_circuit()
    circuit.set_persistent_storage(storage)

    async def get44():
        await asyncio.sleep(0.01)
        return 44

    dp3 = redzed.DataPoll(
        'pers', func=get44, interval=0.02,
        initial=[redzed.RestoreState(), redzed.InitValue(11)])

    log = []
    @redzed.triggered
    def append_to_log(pers):
        log.append(pers)
    await runtest(sleep=0.08)
    assert log == [22, 44]
    assert strip_ts(storage)[dp3.rz_key] == 44


async def test_backoff(circuit):
    """Test exponential backoff timing."""
    logger = TimeLogger('logger', mstop=True)

    n = 0
    def gen():
        nonlocal n
        n += 1
        v = redzed.UNDEF if 3 <= n <= 8 or 12 <= n <= 14 else n
        logger.log(None if v is redzed.UNDEF else v)
        return v

    redzed.DataPoll('dp', func=gen, interval=0.02, retry_interval=["4ms", "48ms"])
    await runtest(sleep=0.32)

    X = None
    LOG = [
        (0, 1),
        (20, 2),
        (40, X),
        (44, X),    # 4
        (52, X),    # 8
        (68, X),    # 16
        (100, X),   # 32
        (148, X),   # 48
        (196, 9),   # 48
        (216, 10),
        (236, 11),
        (256, X),
        (260, X),
        (268, X),
        (284, 15),
        (304, 16),
        (320, '--stop--')]
    logger.compare(LOG)
