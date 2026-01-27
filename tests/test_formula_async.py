"""
Test Formulas.
"""

# pylint: disable=unused-argument

import pytest

import redzed

from .utils import runtest

pytestmark = pytest.mark.usefixtures("task_factories")

async def test_example(circuit):
    """Test the example from the docs."""
    log1 = []
    log2 = []

    m1 = redzed.Memory("v1", comment="value #1", initial=False)
    m2 = redzed.Memory("v2", comment="value #2", initial=False)

    @redzed.triggered
    def output1(v1, v2):
        log1.append(v1 and v2)

    @redzed.formula
    def v1_v2(v1, v2):
        return v1 and v2

    @redzed.triggered
    def output2(v1_v2):
        log2.append(v1_v2)

    async def tester():
        # initial = FF -> F
        m1.event('store', True)     # TF
        m1.event('store', False)    # FF
        m1.event('store', True)     # TF
        m2.event('store', True)     # TT -> T
        m2.event('store', False)    # TF -> F
        m1.event('store', False)    # FF
        m2.event('store', True)     # FT

    await runtest(tester())
    assert log1 == [False, False, False, False, True, False, False, False]
    assert log2 == [False, True, False]


async def test_args(circuit):
    """Test various way of specifying inputs."""
    m1 = redzed.Memory("v1", comment="value #1", initial=False)
    m2 = redzed.Memory("v2", comment="value #2", initial=False)

    @redzed.formula
    def f1(v1, v2):
        return v1 and v2

    @redzed.formula
    def f2(v2, x=m1):
        return x and v2

    @redzed.formula
    def f3(v1, y='v2'):
        return v1 and y

    @redzed.triggered
    def output2(f1, f2, f3):
        assert f1 is f2 is f3

    async def tester():
        # initial = FF -> F
        m1.event('store', True)
        m1.event('store', False)
        m1.event('store', True)
        m2.event('store', True)
        m2.event('store', False)
        m1.event('store', False)
        m2.event('store', True)

    await runtest(tester())
