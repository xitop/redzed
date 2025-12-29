"""
Test the task_factory fixture.

If pytest-xdist is used, run pytest with '--dist loadfile' option
"""

import asyncio

import pytest

from redzed.utils.data_utils import tasks_are_eager

pytestmark = pytest.mark.usefixtures("task_factories")


@pytest.fixture(scope="module", name="memory")
def memory_fixture():
    storage = []
    yield storage
    assert storage == [False, True]


@pytest.mark.skipif(
    not hasattr(asyncio, "eager_task_factory"),
    reason="eager asyncio tasks not supported")
async def test_task_factory(memory):
    memory.append(tasks_are_eager())
