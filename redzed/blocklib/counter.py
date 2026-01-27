"""
Counter.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""

from __future__ import annotations

import redzed

__all__ = ['Counter']


class Counter(redzed.Block):
    """
    Counter. If modulo is set to a number M, count modulo M.
    """

    def __init__(self, *args, modulo: int|None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if modulo == 0:
            raise ValueError("modulo must not be zero")
        self._mod = modulo

    def _setmod(self, value: int) -> int:
        output = value if self._mod is None else value % self._mod
        self._set_output(output)
        return output

    def _event_inc(self, edata: redzed.EventData) -> int:
        return self._setmod(self._output + edata.get('evalue', 1))

    def _event_dec(self, edata: redzed.EventData) -> int:
        return self._setmod(self._output - edata.get('evalue', 1))

    def _event_put(self, edata: redzed.EventData) -> int:
        return self._setmod(edata['evalue'])

    def rz_init_default(self) -> None:
        self._set_output(0)

    rz_init = _setmod

    def rz_export_state(self):
        return self.get()

    rz_restore_state = _setmod
