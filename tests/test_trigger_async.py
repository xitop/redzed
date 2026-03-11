"""
Test function calls in triggers.
"""

# pylint: disable=unused-argument

import pytest

import redzed as rz

from .utils import runtest

pytestmark = pytest.mark.usefixtures("task_factories")

@pytest.mark.parametrize('always', [False, True])
async def test_with_prev(circuit, always):
    """Test the example from the docs."""
    log1 = []
    log2 = []

    mem = rz.Memory("mem", initial=0, always_trigger=always)

    @rz.trigger
    def log_out(mem, _with_previous=False):
        log1.append(mem)

    @rz.trigger
    def log_out_prev(mem, _with_previous=True):
        log2.append(mem)

    async def tester():
        mem.event('store', 1)
        mem.event('store', 1)
        mem.event('store', 2)
        mem.event('store', 2)
        mem.event('store', 3)
        mem.event('store', 4)
        mem.event('store', 5)

    await runtest(tester())
    if always:
        assert log1 == [0, 1, 1, 2, 2, 3, 4, 5]
        assert log2 == [(0, rz.UNDEF), (1,0), (1,1), (2,1), (2,2), (3,2), (4,3), (5,4)]
    else:
        assert log1 == [0, 1, 2, 3, 4, 5]
        assert log2 == [(0, rz.UNDEF), (1,0), (2,1), (3,2), (4,3), (5,4)]


async def test_example(circuit):
    """Test the example from docs."""

    state = rz.Memory("state", validator=bool, initial=True)
    diff = rz.Memory("diff", initial="?")
    cnt = 0

    @rz.trigger
    def _state_trigger(state, _with_previous=True):
        nonlocal cnt
        cur, prev = state
        if prev is rz.UNDEF:
            # initial value, nothing to compare with
            return
        cnt += 1
        if cur and not prev:
            diff.event('store', f'on{cnt}')
        if not cur and prev:
            diff.event('store', f'off{cnt}')

    def test(st, df):
        if st is not None:
            state.event('store', st)
        assert diff.get() == df

    async def tester():
        test(None, '?')
        test(True, '?')
        test(False, 'off1')
        test(False, 'off1')
        test(True, 'on2')
        test(False, 'off3')
        test(True, 'on4')
        test(True, 'on4')

    await runtest(tester())
