"""
Test the Cron service.
"""

# pylint: disable=missing-class-docstring

import asyncio
import datetime as dt
import time

import pytest

import redzed

from .utils import runtest

pytestmark = pytest.mark.usefixtures("task_factories")


@pytest.mark.parametrize('insert_before', [False, True])
@pytest.mark.parametrize('block', [False, True])
async def test_reschedule(circuit, insert_before, block):
    """
    Test cron schedule updates by inserting a new event
    before/after the scheduled next event. Also try
    to block the event loop for a short while to make
    the cron miss the correct time of the next event.
    """

    MS1 = dt.timedelta(milliseconds=1)

    class CronClient(redzed.Block):
        def __init__(self, *args, **kwargs):
            self.log = []
            super().__init__(*args, **kwargs)

        def rz_cron_event(self, now):
            cnt = len(self.log)
            self.log.append(int((now - start) / MS1 + 0.5))
            if  cnt == 0:
                cron.set_schedule(client, [t2, t3])
                if block:
                    time.sleep(0.04)    # block the event loop!
            elif cnt == 2:
                circuit.shutdown()

    cron = circuit.resolve_name('_cron_local')
    client = CronClient("cc")

    async def tester():
        cron.set_schedule(client, [t1, t3 if insert_before else t2])
        await asyncio.sleep(1)

    start = dt.datetime.now()
    t1 = (start + dt.timedelta(milliseconds=10)).time()
    t2 = (start + dt.timedelta(milliseconds=40)).time()
    t3 = (start + dt.timedelta(milliseconds=70)).time()

    await runtest(tester())
    assert all(
        0 <= measured - expected < 5
        for measured, expected in zip(client.log, [10, 50 if block else 40, 70]))
