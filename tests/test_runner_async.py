"""
Test the circuit runner
"""

from unittest.mock import patch, DEFAULT

import pytest

import redzed

pytestmark = pytest.mark.usefixtures("task_factories")

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup

async def test_quick_close(circuit):
    """Shutdown is skipped if init is aborted early."""
    async def will_fail():
        raise RuntimeError("quick error")

    # pylint: disable=attribute-defined-outside-init, missing-class-docstring
    class TestBlock(redzed.Block):
        def rz_start(self):
            self.x_start = True
        def rz_stop(self):
            self.x_stop = True
    canary = TestBlock('canary', x_start=False, x_stop=False)

    states = []
    def log_state(state):
        states.append(max(state,circuit.get_state()))
        return DEFAULT

    with Grp(Exc(RuntimeError, match="quick error")):
        with patch.object(
                # pylint: disable-next=protected-access
                circuit, '_set_state', wraps=circuit._set_state, side_effect=log_state):
            await redzed.run(will_fail())
    # no init&start, no shutdown&cleanup
    assert not canary.x_start and not canary.x_stop
    assert redzed.CircuitState.INIT_BLOCKS not in states
    assert redzed.CircuitState.RUNNING not in states
