"""
A timer for general use.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['Timer']

from redzed.utils import time_period
from .fsm import FSM


class Timer(FSM):
    """
    A timer.
    """

    ALL_STATES = ['off', 'on']
    TIMED_STATES = [
        ['on', float("inf"), 'off'],
        ['off', float("inf"), 'on']]
    EVENTS = [
        ['start', ..., 'on'],
        ['stop', ..., 'off'],
        ['toggle', ['on'], 'off'],
        ['toggle', ['off'], 'on']]

    def __init__(self, *args, restartable: bool = True, **kwargs) -> None:
        if 't_period' in kwargs:
            if ('t_on' in kwargs or 't_off' in kwargs):
                raise TypeError("t_period and t_on/t_off are mutually exclusive.")
            period = time_period(kwargs.pop('t_period'))
            kwargs['t_on'] = kwargs['t_off'] = period / 2
        super().__init__(*args, **kwargs)
        if self._t_duration.get('on') == self._t_duration.get('off') == 0.0:
            raise ValueError(
                f"{self}: Durations for timer states 'on' and 'off' cannot be both zero")
        self._restartable = bool(restartable)

    def cond_start(self) -> bool:
        return self._restartable or self._state != 'on'

    def cond_stop(self) -> bool:
        return self._restartable or self._state != 'off'

    def _set_output(self, output) -> bool:
        return super()._set_output(output == 'on')
