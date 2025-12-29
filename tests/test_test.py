"""
Test the test utilities
"""

# pylint: disable=unused-argument

import time

import pytest

from .utils import compare_logs, mini_init, TimeLogger


def test_compare_logs(circuit):
    """Check the compare_logs()."""
    log = [(x, f'value_{x}') for x in range(0, 1000, 17)]
    compare_logs(log, log)
    with pytest.raises(AssertionError):
        compare_logs(log, log[:-1])                         # diff length
    with pytest.raises(AssertionError):
        compare_logs(log[:-2], log)                         # diff length
    with pytest.raises(AssertionError):
        compare_logs(
            [(0, 'start'), (22, 'string')],
            [(0, 'start'), (22, 'String')]) # s vs S in string
    # delta_abs tests
    compare_logs(
        [(0, 'start'), (15, 'x')],          # tlog (test)
        [(0, 'start'), (10, 'x')],          # slog (standard)
        delta_abs=5, delta_rel=0)
    with pytest.raises(AssertionError, match="15 is way above expected 10"):
        compare_logs(
            [(0, 'start'), (15, 'x')],
            [(0, 'start'), (10, 'x')],
            delta_abs=4, delta_rel=0)       # NOT 5 < 4 ms
    with pytest.raises(AssertionError, match="8.5 is way below expected 10"):
        compare_logs(
            [(0, 'start'), (8.5, 'x')],     # negative difference -> 1/5 of delta
            [(0, 'start'), (10, 'x')],
            delta_abs=4, delta_rel=0)       # NOT 1.5 < 0.8 (1/5 of 4) ms
    # delta_rel tests
    compare_logs(
        [(490, 'y')],
        [(460, 'y')],
        delta_abs=0, delta_rel=0.10)        # 6.5% < 10%
    with pytest.raises(AssertionError):
        compare_logs(
            [(490, 'y')],
            [(460, 'y')],
            delta_abs=0, delta_rel=0.05)    # 6.5% < 5%
    with pytest.raises(AssertionError):
        compare_logs(
            [(460, 'y')],                  # negative difference -> 1/5 of delta
            [(490, 'y')],
            delta_abs=0, delta_rel=0.1)    # NOT 6.1% < 2% (1/5 of 10%)


def test_timelogger_tool(circuit):
    """Check the TimeLogger."""
    logger = TimeLogger('logger')
    mini_init(circuit)
    logger.log('A')
    time.sleep(0.1)
    logger.log('B')
    time.sleep(0.05)
    logger.log('C')
    logger.compare([(0, 'A'), (100, 'B'), (150, 'C')])


def test_timelogger_marks(circuit):
    """TimeLogger adds start and stop marks if enabled."""
    logger = TimeLogger('logger', mstart=True, mstop=True)
    logger.compare([])
    mini_init(circuit)
    logger.compare([(0, '--start--')])
    time.sleep(0.05)
    logger.rz_stop()
    logger.compare([(0, '--start--'), (50, '--stop--')])
