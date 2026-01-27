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


async def test_checkpointing(circuit):
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
    nmem = redzed.Memory('nmem', initial=[redzed.RestoreState(), 'n'])
    # with periodic checkpointing
    smem = redzed.Memory(
        'sync', initial=[redzed.RestoreState(checkpoints='interval'), 'i'])
    # with checkpoints after each event
    emem = redzed.Memory(
        'ev', initial=[redzed.RestoreState(checkpoints='event'), 'e'])
    circuit.set_persistent_storage(storage, sync_time=0.01)
    with patch.object(
            circuit, 'save_persistent_state', wraps=circuit.save_persistent_state) as wrapped:
        await runtest(tester(wrapped))
        nlist = [c.args[0].name for c in wrapped.mock_calls]
    assert strip_ts(storage) == {emem.rz_key: 'E2', nmem.rz_key: 'N2', smem.rz_key: 'S2'}
    assert len(nlist) == 10
    assert set(nlist[0:2]) == {'sync', 'ev'}        # initial checkpoints, order undefined
    assert nlist[2:7] == ['sync', 'ev', 'sync', 'sync', 'sync'] # regular checkpointing
    assert set(nlist[7:10]) == {'sync', 'ev', 'nmem'}       # final save, order undefined


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
        # RestoreState won't be run after InitValue, but it stores the configuration
        initial=[redzed.InitValue('S0'), redzed.RestoreState(checkpoints='event')]
        )

    olog = []
    @redzed.triggered
    def log_output(fsm012):
        olog.append(fsm012)

    slog = []
    def log_state(*_args, **_kwargs):
        slog.append(fsm.state)
        return DEFAULT

    storage = add_ts({fsm.rz_key: ('S2', None, {})})
    circuit.set_persistent_storage(storage, sync_time=0.01)

    with patch.object(
            circuit, 'save_persistent_state',
            wraps=circuit.save_persistent_state,
            side_effect=log_state
            ):
        await runtest(sleep=0.03)

    assert olog == ['S0', 'S1', 'S2']           # S0 -> S1 -> S2
    assert slog == ['S0', 'S1', 'S2', 'S2']     # initial, event, event, final
    assert strip_ts(storage) == {fsm.rz_key: ('S2', None, {})}
