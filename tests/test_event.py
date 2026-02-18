"""
Test Block events.
"""

# pylint: disable=missing-class-docstring, protected-access, unused-argument

import pytest

import redzed

from .utils import mini_init, EventMemory


def test_delivery(circuit):
    """Test basic event delivery and EventMemory."""
    dest = EventMemory('dest')

    assert dest.get() is redzed.UNDEF
    dest.event('store', 1)
    assert dest.get() == ('store', 1)
    dest.event('store', 2)
    assert dest.get() == ('store', 2)
    dest.event('new', 3, first=None, second="x")
    assert dest.get() == ('new', 3, {'first': None, 'second': "x"})
    dest.event('move', 4, left=redzed.UNDEF, right=True)
    assert dest.get() == ('move', 4, {'right': True})
    dest.event('move', 5, left=True, right=redzed.UNDEF)
    assert dest.get() == ('move', 5, {'left': True})


def test_retval(circuit):
    """Test the value returned by event()."""
    class LB1(redzed.Block):
        def _event_len(self, edata):
            return len(edata['evalue'])

    lb1 = LB1("testblock")
    assert lb1.event('len', "a") == 1
    assert lb1.event('len', "bb") == 2
    assert lb1.event('len', [10, 20, 30]) == 3


def test_extra_data(circuit):
    """Test passing extra data."""
    class LB1(redzed.Block):
        def _event_concat(self, edata):
            return edata['evalue'] + edata.get('suffix', "!")

    lb1 = LB1("testblock")
    assert lb1.event('concat', "a", suffix="-A") == "a-A"
    assert lb1.event('concat', "bb", suffix="-2B") == "bb-2B"
    assert lb1.event('concat', "ccc") == "ccc!"


def test_call_error(circuit):
    """Test incorrect event() calls."""
    dest = redzed.Memory("testblock")

    with pytest.raises(TypeError, match="string"):
        dest.event(333, None)
    with pytest.raises(ValueError, match="empty"):
        dest.event("", None)
    for ev in ["%%", "Goto:Home", "7up"]:
        with pytest.raises(ValueError, match="identifier"):
            dest.event(ev, None)
    with pytest.raises(redzed.UnknownEvent):
        dest.event("no_such_event", None)
    # check that abort was not called
    assert not circuit._errors


def test_error_note(circuit):
    """Test the presence of added error notes."""
    class LB1(redzed.Block):
        def _event_value(self, edata):
            return edata['evalue']
        def _event_error(self, _edata):
            raise ValueError("all wrong")

    lb1 = LB1("testblock")
    with pytest.raises(KeyError, match="almost certainly missing"):
        assert lb1.event('value')
    with pytest.raises(redzed.UnknownEvent):
        assert lb1.event('jump')
    with pytest.raises(ValueError, match="during handling of event 'error'"):
        assert lb1.event('error')
    # check that abort was not called
    assert not circuit._errors


def test_reserved_edata_name(circuit):
    """Except *evalue* there are no other reserved kwarg names in event()."""
    dest = EventMemory('dest')

    # pylint: disable=kwarg-superseded-by-positional-arg
    dest.event('ET', 'EV', self='SELF', etype='ETYPE', edata='anything')
    assert dest.get() == ('ET', 'EV', {'self': 'SELF', 'etype': 'ETYPE', 'edata': 'anything'})

    with pytest.raises(TypeError, match="multiple"):
        # pylint: disable-next=redundant-keyword-arg
        dest.event('ET', 'either here', evalue='or here')


def test_event_handlers(circuit):
    """Test event dispatch table."""
    class B0:
        # not defined as a Block subclass -> ignored
        def _event_X(self, *_args, **_kwargs):
            return

    class B1(redzed.Block):
        def _event_add(self, edata):
            self._set_output(self.get() + edata['evalue'])

        def _event_sub(self, edata):
            self._set_output(self.get() - edata['evalue'])

    class B2(B0, B1):
        def _event_div(self, edata):
            self._set_output(self.get() / edata['evalue'])

        def _event_sub(self, edata):
            # redefining sub
            self._set_output(self.get() - 2 * edata['evalue'])

        def rz_init_default(self):
            self._set_output(0)


    addsub = B2('addsub')
    mini_init(circuit)

    edt_keys = {name for name in addsub._edt_handlers if not name.startswith("_get_")}
    assert edt_keys == {'add', 'sub', 'div'}

    with pytest.raises(redzed.UnknownEvent):
        addsub.event('X')
    assert addsub.get() == 0
    addsub.event('add', 10)
    assert addsub.get() == 0 + 10
    addsub.event('sub', 3)
    assert addsub.get() == 10 - 2*3
    addsub.event('div', 4)
    assert addsub.get() == 4 / 4
