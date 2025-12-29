"""
Pytest fixtures.
"""

import asyncio
import gc
import os

import pytest

import redzed


# using readable names, because they are displayed in the "pytest -v" output
_factories = ["RegularTasks"]
if hasattr(asyncio, "eager_task_factory"):
    _factories.append("EagerTasks")


@pytest.fixture(scope="module", params=_factories)
async def task_factories(request):
    """If supported, run tests twice: with eager tasks off and on."""
    if request.param == "EagerTasks":
        factory = asyncio.eager_task_factory
    elif request.param == "RegularTasks":
        factory = None
    else:
        raise ValueError("Unknown task factory name in the pytest fixture")
    asyncio.get_running_loop().set_task_factory(factory)


def pytest_xdist_auto_num_workers(config):
    try:
        if config.option.numprocesses == "logical" and (cpus := os.cpu_count()) > 1 :
            return (4 * cpus) // 5    # limit load to approx. 80%
    except Exception:
        pass
    return None


@pytest.fixture(name='circuit')
def fixture_circuit():
    """Return a new empty circuit."""
    redzed.reset_circuit()
    return redzed.get_circuit()


@pytest.fixture(scope='module', autouse=True)
def suppress_gc_during_tests():
    """Do not interfere with timing tests."""
    gc.disable()
    yield None
    gc.enable()
    gc.collect()
