"""
Test the Timer block.
"""

# pylint: disable=unused-argument

import pytest

import redzed

from .utils import mini_init


def test_no_busy_loop(circuit):     # pylint: disable=unused-argument
    """Busy loop (zero period clock) is not allowed."""
    redzed.Timer('timer0_', t_on=0)
    redzed.Timer('timer_0', t_off=0)
    with pytest.raises(ValueError, match="both zero"):
        redzed.Timer('timer00', t_on=0, t_off=0)


def test_init_state(circuit):
    """Test initial state."""
    t1 = redzed.Timer('on_off', initial='on')
    f1 = redzed.Timer('off_on', initial='off')
    f2 = redzed.Timer('default')
    mini_init(circuit)
    assert t1.get() is True
    assert f1.get() is f2.get() is False


def test_timer_static(circuit):
    """Test states, events, output."""
    bis = redzed.Timer('timer')
    mini_init(circuit)

    def trans(event, state):
        bis.event(event)
        assert bis.state == 'on' if state else 'off'
        assert bis.get() is bool(state)

    assert bis.get() is False
    trans('start', True)
    trans('stop', False)
    trans('stop', False)
    trans('toggle', True)
    trans('start', True)
    trans('start', True)
    trans('toggle', False)
    trans('toggle', True)
    trans('start', True)
    trans('toggle', False)
    trans('start', True)


def test_timer_args(circuit):
    with pytest.raises(TypeError):
        redzed.Timer("A", t_on=1, t_period=1)
    with pytest.raises(TypeError):
        redzed.Timer("B", t_off=1, t_period=1)
    with pytest.raises(ValueError, match="period must be positive"):
        redzed.Timer('E', t_period=0)
    with pytest.raises(ValueError, match="both zero"):
        redzed.Timer('C1', t_on="0s", t_off=0)


def test_timer_period(circuit):
    a = redzed.Timer('timer_a', t_on=1, t_off=1)
    b = redzed.Timer('timer_b', t_period='2s')

    # pylint: disable=protected-access
    assert a._t_duration == b._t_duration == {'on': 1.0, 'off': 1.0}
