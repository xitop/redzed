"""
Test asyncio related helpers.
"""

# pylint: disable=missing-class-docstring, unused-argument

import asyncio

import pytest

import redzed
from redzed.utils import cancel_shield

from .utils import ms, runtest

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_shield():
    """Test without and with cancel_shield."""
    result = None

    async def shielded():
        nonlocal result
        for _ in range(5):
            await ms(15)
            result += 1

    async def coro(shield):
        nonlocal result
        result = 0
        await (cancel_shield(shielded()) if shield else shielded())
        await ms(10)
        result = 99

    # without shield
    for t in range(2, 7):
        task = asyncio.create_task(coro(False))
        await ms(t*14)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert 0 <= result <= 5, "test without shield failed"

    # with shield
    for t in range(7):
        task = asyncio.create_task(coro(True))
        await ms(t*14)
        # cancel_shield's main feature is that it can withstand repeated cancel
        task.cancel()
        await ms(5)
        task.cancel()
        await ms(5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert result == 5


@pytest.mark.parametrize('immediate', [False, True])
async def test_service(circuit, immediate):
    """Test setting the task name and immediate_start."""
    TASKNAME = "jerry's task"

    class Jerry(redzed.Block):

        async def _test_task(self):
            self._set_output(self.circuit.get_state().name)
            assert asyncio.current_task().get_name() == TASKNAME
            await asyncio.sleep(1)

        def rz_pre_init(self):
            # pylint: disable=no-member
            self.circuit.create_service(
                self._test_task(),
                name=self.x_name,
                start_state='INIT_CIRCUIT' if immediate else 'RUNNING')

        def rz_init(self, value):
            self._set_output("default")

    jerry = Jerry(
        'jerry', comment="the mouse",
        x_name=TASKNAME, initial=[redzed.InitWait(0.01), redzed.InitValue("x")])
    await runtest(sleep=0.05)
    if immediate:
        assert jerry.get() in ["INIT_CIRCUIT", "INIT_BLOCKS"]   # timing dependent
    else:
        assert jerry.get() == "RUNNING"


async def test_auto_cancel(circuit):
    """Test the task auto cancel."""
    class TaskBlock(redzed.Block):

        async def _test_task(self):
            self.x_n += 1
            await asyncio.sleep(1)

        def rz_start(self):
            # pylint: disable=attribute-defined-outside-init
            self.x_n = 0
            self.x_t1 = self.circuit.create_service(self._test_task(), auto_cancel=False)
            self.x_t2 = self.circuit.create_service(self._test_task(), auto_cancel=True)
            self.x_t3 = self.circuit.create_service(self._test_task())  # default = cancel

    tb = TaskBlock('tb')

    await runtest(sleep=0.05)
    assert tb.x_n == 3

    assert tb.x_t3.cancelled()
    assert tb.x_t2.cancelled()

    assert not tb.x_t1.done()
    tb.x_t1.cancel()
    await asyncio.sleep(0)
    assert tb.x_t1.cancelled()  # cancelled() implies done()
