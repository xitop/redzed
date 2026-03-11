"""
Test persistent state checkpointing.
"""

import asyncio
from unittest.mock import patch, DEFAULT

import pytest

import redzed

from .utils import runtest, add_ts, strip_ts

pytestmark = pytest.mark.usefixtures("task_factories")

# pylint: disable=missing-class-docstring


async def test_defaults(circuit):
    """Test default options."""
    async def tester(blocks):
        for blk in blocks:
            assert blk.rz_save_flags == blk.x_sf
            if redzed.SF_OUTPUT in blk.rz_save_flags:
                assert getattr(type(blk), 'RZ_STATE_IS_OUTPUT', False)

    circuit.set_persistent_storage({})
    test_blocks = [
        redzed.Memory('m1', initial=0, x_sf=redzed.SF_NONE),
        redzed.Memory(
            'm2', initial=[redzed.PersistentState(), 0],
            x_sf=redzed.SF_OUTPUT),
        redzed.Memory(
            'm3', initial=[redzed.PersistentState(expiration=2), 0],
            x_sf=redzed.SF_OUTPUT | redzed.SF_INTERVAL),
        redzed.DataPoll(
            'dp', func=int, interval=5, initial=[redzed.PersistentState(), 0],
            x_sf=redzed.SF_OUTPUT),
        redzed.Counter(
            'cnt', initial=[redzed.PersistentState(expiration=2), 0],
            x_sf=redzed.SF_OUTPUT | redzed.SF_INTERVAL),
        redzed.Timer(
            't1', initial=[redzed.PersistentState()],
            x_sf=redzed.SF_EVENT),
        redzed.Timer(
            't2', initial=[redzed.PersistentState(expiration=2)],
            x_sf=redzed.SF_EVENT | redzed.SF_INTERVAL),
        redzed.OutputFunc('out', func=print, x_sf=redzed.SF_NONE),
        ]
    await runtest(tester(test_blocks))


async def test_checkpointing_1(circuit):
    """Verify that state is saved according to settings."""
    async def tester(wrapped):
        assert wrapped.call_count == 2
        await asyncio.sleep(0.015)
        assert wrapped.call_count == 3
        emem.event('store', 'E2')
        nmem.event('store', 'N2')
        smem.event('store', 'S2')
        assert wrapped.call_count == 4
        await asyncio.sleep(0.03)
        assert wrapped.call_count == 7

    storage = {}
    # no persistent state at all
    redzed.Memory('input', initial=0)
    # no checkpointing
    nmem = redzed.Memory(
        'nmem', initial=[redzed.PersistentState(save_flags=redzed.SF_NONE), 'n'])
    # with periodic checkpointing
    smem = redzed.Memory(
        'save', initial=[redzed.PersistentState(save_flags=redzed.SF_INTERVAL), 's'])
    # with checkpoints after each event
    emem = redzed.Memory(
        'ev', initial=[redzed.PersistentState(save_flags=redzed.SF_EVENT), 'e'])
    circuit.set_persistent_storage(storage, save_interval=0.01)
    with patch.object(
            circuit, 'save_persistent_state', wraps=circuit.save_persistent_state) as wrapped:
        await runtest(tester(wrapped))
        nlist = [c.args[0].name for c in wrapped.mock_calls]
    assert strip_ts(storage) == {emem.rz_key: 'E2', nmem.rz_key: 'N2', smem.rz_key: 'S2'}
    assert len(nlist) == 10
    assert set(nlist[0:2]) == {'save', 'ev'}        # initial checkpoints, order undefined
    assert nlist[2:7] == ['save', 'ev', 'save', 'save', 'save'] # regular checkpointing
    assert set(nlist[7:10]) == {'save', 'ev', 'nmem'}       # final save, order undefined


async def test_checkpointing_2(circuit):
    """Verify that state is saved according to settings."""
    async def tester():
        for i in range(4):
            for _ in range(3):
                omem.event('store', i)
                emem.event('store', 100+i)
                await asyncio.sleep(0)

    storage = {}
    omem = redzed.Memory(
        'out', initial=[redzed.PersistentState(save_flags=redzed.SF_OUTPUT), None])
    emem = redzed.Memory(
        'ev', initial=[redzed.PersistentState(save_flags=redzed.SF_EVENT), None])
    circuit.set_persistent_storage(storage)
    with patch.object(
            circuit, 'save_persistent_state', wraps=circuit.save_persistent_state) as wrapped:
        await runtest(tester())
        nlist = [c.args[0].name  for c in wrapped.mock_calls]
    assert strip_ts(storage) == {omem.rz_key: 3, emem.rz_key: 103}
    assert len(nlist) == 20
    # 20 = 2 blocks init, 4 output changes in omem, (3*4) events in emem, 2 blocks shutdown
    assert set(nlist[0:2]) == {'out', 'ev'}
    assert nlist[2:-2] == ['out', 'ev', 'ev', 'ev'] * 4
    assert set(nlist[-2:]) == {'out', 'ev'}


async def test_fsm(circuit):
    """Test checkpointing after timer based events."""
    class FSM_012(redzed.FSM):
        STATES = [
            ['S0', "10ms", 'S1'],
            ['S1', "10ms", 'S2'],
            'S2',
        ]

    fsm = FSM_012(
        'fsm012',
        # PersistentState won't be run after InitValue, but it stores the configuration
        initial=[redzed.InitValue('S0'), redzed.PersistentState(save_flags=redzed.SF_EVENT)]
        )

    olog = []
    @redzed.trigger
    def log_output(fsm012):
        olog.append(fsm012)

    slog = []
    def log_state(*_args, **_kwargs):
        slog.append(fsm.state)
        return DEFAULT

    storage = add_ts({fsm.rz_key: ('S2', None, {})})
    circuit.set_persistent_storage(storage, save_interval=0.01)

    with patch.object(
            circuit, 'save_persistent_state',
            wraps=circuit.save_persistent_state,
            side_effect=log_state
            ):
        await runtest(sleep=0.03)

    assert olog == ['S0', 'S1', 'S2']           # S0 -> S1 -> S2
    assert slog == ['S0', 'S1', 'S2', 'S2']     # initial, event, event, final
    assert strip_ts(storage) == {fsm.rz_key: ('S2', None, {})}
