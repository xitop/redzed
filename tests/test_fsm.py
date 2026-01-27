"""
Test FSM blocks.
"""

# pylint: disable=missing-class-docstring, protected-access
# pylint: disable=unused-variable, unused-argument, no-member

import pytest

import redzed

from .utils import mini_init, EventMemory, add_ts, strip_ts

Exc = pytest.RaisesExc
Grp = pytest.RaisesGroup


def test_basic_state_transition(circuit):
    """Test the basic FSM function."""
    class B123(redzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', ['S1'], 'S2'),
            ('step', ['S3'], 'S1'),
            ['step', ..., 'S3'],   # default rule has lower precedence
            ]

    b123x = B123('b123fsm_S1')
    b123y = B123('b123fsm_S3', initial='S3')  # test initial state
    mini_init(circuit)

    assert b123x.get() == 'S1'

    b123x.event('step')
    assert b123x.get() == 'S2'

    b123x.event('step')
    assert b123x.get() == b123y.get() == 'S3'

    b123x.event('step')
    b123y.event('step')
    assert b123x.get() == b123y.get() == 'S1'


def test_disallowed_state_transitions(circuit):
    """Test the basic FSM function."""
    class B123(redzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('stepX1', ..., 'S1'),    # * -> S1
            ('stepX3', ..., 'S3'),    # * -> S3 ...
            ('stepX3', ['S2'],  None),  #    ... but not S2 -> S3
            ('step12', ['S1'], 'S2'),   # S1 -> S2
            ['step12', ['S2'], 'S1'],   # S2 -> S1
            ]

    b123 = B123('b123')
    mini_init(circuit)

    assert b123.get() == 'S1'

    assert b123.event('step12') is True
    assert b123.get() == 'S2'
    assert b123.event('step12') is True
    assert b123.get() == 'S1'

    assert b123.event('stepX3') is True
    assert b123.get() == 'S3'
    assert b123.event('step12') is False
    assert b123.get() == 'S3'
    assert b123.event('step12') is False
    assert b123.get() == 'S3'

    assert b123.event('stepX1') is True
    assert b123.get() == 'S1'
    assert b123.event('step12') is True
    assert b123.get() == 'S2'
    assert b123.event('stepX3') is False
    assert b123.get() == 'S2'


def test_invalid_states(circuit):
    with pytest.raises(ValueError, match="non-empty sequence"):
        class No1(redzed.FSM):
            """no states"""

    with pytest.raises(ValueError, match="non-empty sequence"):
        class No2(redzed.FSM):
            STATES = "S1"

    with pytest.raises(ValueError, match="Duplicate"):
        class No3(redzed.FSM):
            STATES = ["S1", "S2", "S2"]

    with pytest.raises(ValueError, match="Duplicate"):
        class No4(redzed.FSM):
            STATES = [["S1", None, "S2"], "S2", ["S1", 1, "S2"]]


def test_unknown_states(circuit):
    with pytest.raises(ValueError, match="unknown"):
        class No1(redzed.FSM):
            STATES = ["S1", ["S2", 0, "S3"]]

    with pytest.raises(ValueError, match="unknown"):
        class No2(redzed.FSM):
            STATES = ["A", "B", "C"]
            EVENTS = [["e", ..., "nostate"]]

    with pytest.raises(ValueError, match="unknown"):
        class No3(redzed.FSM):
            STATES = ["A", "B", "C"]
            EVENTS = [["e", ["B", "nostate"], "A"]]


def test_invalid_names(circuit):
    with pytest.raises(ValueError, match='empty'):
        class ErrValue1(redzed.FSM):
            STATES = ['']

    with pytest.raises(ValueError, match='empty'):
        class ErrValue2(redzed.FSM):
            STATES = ['S']
            EVENTS = [('', 'S', 'S')]

    with pytest.raises(ValueError, match='Ambiguous'):
        class ErrValue3(redzed.FSM):
            STATES = ['S']
            EVENTS = [('FOO', 'S', 'S')]        # FSM event 'FOO'
            def _event_FOO(self, **kwargs):     # non-FSM event 'FOO'
                pass

    with pytest.raises(ValueError, match='identifier'):
        class ErrValue4(redzed.FSM):
            STATES = ['X']
            EVENTS = [("Start:X", 'X', 'X')]

    with pytest.raises(TypeError):
        class ErrType1(redzed.FSM):
            STATES = [5, 6]
            EVENTS = [('E', 5, 6)]

    with pytest.raises(TypeError):
        class ErrType2(redzed.FSM):
            STATES = ['X']
            EVENTS = [(None, 'X', 'Y')]


def test_goto(circuit):
    """Test the internal Goto special event."""
    class B123(redzed.FSM):
        STATES = ('S1', 'S2', 'S3')
        EVENTS = [
            ('step', ['S1'], 'S2'),
            ('step', ['S2'], 'S3'),
            ('step', ['S3'], 'S1')
            ]

    b123 = B123('b123fsm')
    mini_init(circuit)

    assert b123.state == 'S1'

    b123.event('step')
    assert b123.state == 'S2'

    b123._goto('S1')
    assert b123.state == 'S1'

    with pytest.raises(ValueError, match="is unknown"):
        b123._goto('S99')


def test_enter_exit_hooks(circuit):
    """Test the action hooks."""
    messages = []
    log = messages.append

    class B123(redzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', ['S1'], 'S2'),
            ('step', ['S2'], 'S3'),
            ('step', ['S3'], 'S1')
            ]
        def enter_S1(self):
            log('+S1m')
        def exit_S1(self):
            log('-S1m')
        def enter_S2(self):
            log('+S2m')
        def exit_S2(self):
            log('-S2m')

    b123 = B123(
        'b123fsm',
        enter_S2=lambda: log('+S2f'),
        enter_S3=lambda: log('+S3f'), exit_S3=lambda: log('-S3f'))

    mini_init(circuit)

    assert messages == ['+S1m']
    messages.clear()

    b123.event('step')
    # f (functions) are called after m (method)
    assert messages == ['-S1m', '+S2m', '+S2f']
    messages.clear()

    b123.event('step')
    assert messages == ['-S2m', '+S3f']
    messages.clear()

    b123.event('step')
    assert messages == ['-S3f', '+S1m']


def test_no_hook_without_state():
    """Test the state action hooks."""
    class B123(redzed.FSM):
        STATES = ['S0']

    with pytest.raises(TypeError, match="invalid keyword argument"):
        B123('wrong_hook1', enter_S99=lambda: None)
    with pytest.raises(TypeError, match="invalid keyword argument"):
        B123('wrong_hook2', exit_S7=lambda: None)


def test_cond(circuit):
    """Test the cond_EVENT."""
    enable = True
    class B123(redzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', ['S1'], 'S2'),
            ('step', ['S2'], 'S3'),
            ('step', ['S3'], 'S1')
            ]
        def cond_step(self, data):
            return data.get('passwd') == 'secret123'

    b123 = B123('b123fsm', cond_step=lambda: enable)
    mini_init(circuit)

    assert b123.state == 'S1'

    assert not b123.event('step')   # rejected
    assert b123.state == 'S1'
    assert not b123.event('step', passwd='guess')   # rejected
    assert b123.state == 'S1'
    assert b123.event('step', passwd='secret123')   # accepted
    assert b123.state == 'S2'
    enable = False
    assert not b123.event('step', passwd='secret123')   # rejected
    assert b123.state == 'S2'


recursion_test_data = [
    {'x_cond': True,  'x_enter': False, 'x_exit': False},
    {'x_cond': False, 'x_enter': True,  'x_exit': False},
    {'x_cond': False, 'x_enter': False, 'x_exit': True},
    ]
@pytest.mark.parametrize("x_kwargs", recursion_test_data)
def test_no_event_in_hooks_1(circuit, x_kwargs):
    """Hooks (methods) may not call event."""
    class TestFSM(redzed.FSM):
        STATES = ["A", "B", "C"]
        EVENTS = [
            ["ab", ["A"], "B"],
            ["gotoC", ..., "C"],
            ]
        def cond_ab(self):
            if self.x_cond:
                self.log_info("COND_AB called")
                self.event("gotoC")
            return True
        def enter_B(self):
            if self.x_enter:
                self._goto("C")     # _goto sends the special "Goto:C" event
        def exit_A(self):
            if self.x_exit:
                indirect()

    fsm = TestFSM("test_fsm", **x_kwargs)
    def indirect():
        fsm.event("gotoC")

    mini_init(circuit)
    with Exc(RuntimeError):
        fsm.event('ab')


@pytest.mark.parametrize("x_kwargs", recursion_test_data)
def test_no_event_in_hooks_2(circuit, x_kwargs):
    """Hooks (external functions) may not call event."""
    class TestFSM(redzed.FSM):
        STATES = ["A", "B", "C"]
        EVENTS = [
            ["ab", ["A"], "B"],
            ["gotoC", ..., "C"],
            ]

    def cond_ab():
        if fsm.x_cond:
            fsm._goto("C")
        return True
    def enter_B():
        if fsm.x_enter:
            fsm.event("gotoC")
    def exit_A():
        if fsm.x_exit:
            indirect()

    fsm = TestFSM("test_fsm", **x_kwargs, cond_ab=cond_ab, enter_B=enter_B, exit_A=exit_A)
    def indirect():
        fsm.event("gotoC")

    mini_init(circuit)
    with Exc(RuntimeError):
        fsm.event('ab')


def test_persistent_state(circuit):
    class Dummy(redzed.FSM):
        STATES = list("ABCDEF")

    def forbidden():
        assert False

    mem = EventMemory('mem')
    fsm = Dummy(
        'test', initial=redzed.RestoreState(checkpoints='event'),
        enter_D=[forbidden, lambda: mem.event('D', '+enter')],
        exit_D=lambda: mem.event('D', '-exit')
        )
    assert fsm.rz_key == "Dummy:test"
    # FSM state = [state, timer, sdata]
    storage = add_ts({fsm.rz_key: ['D', None, {'x':'y', '_z':3}] })
    circuit.set_persistent_storage(storage)
    # enter_D will be suppressed
    mini_init(circuit)
    assert fsm.sdata == {'x':'y', '_z':3}

    assert fsm.state == 'D'
    assert mem.get() is None

    fsm._goto('F')
    assert mem.get() == ('D', '-exit')
    del fsm.sdata['x']
    assert strip_ts(storage) == {fsm.rz_key: ('F', None, {'_z':3})}


def test_read_only_data(circuit):
    class Simple(redzed.FSM):
        STATES = ['st0', 'st1']
        EVENTS = [('ev01', ..., 'st1')]

        def cond_ev01(self, data):
            with pytest.raises(TypeError):
                data['new_item'] = 0
            assert data['a'] == 1
            return True

    simple = Simple('simple')
    mini_init(circuit)
    assert simple.state == 'st0'
    simple.event('ev01', a=1)
    assert simple.state == 'st1'


def test_edata(circuit):
    """Each event being handled has its own data."""
    class Simple(redzed.FSM):
        STATES = ['st0', 'st1']
        EVENTS = [('ev01', ..., 'st1')]

        def cond_ev01(self, data):
            assert data['sent_to'] == self.name
            return True

    afsm = Simple('A', enter_st1=lambda: bfsm.event('ev01', sent_to='B'))
    bfsm = Simple('B', enter_st1=lambda: cfsm.event('ev01', sent_to='C'))
    cfsm = Simple('C')

    mini_init(circuit)
    assert cfsm.state == 'st0'
    afsm.event('ev01', sent_to='A')     # A -> B -> C
    assert cfsm.state == 'st1'


def test_dispatch_table(circuit):
    """No bogus entries in the dispatch table."""
    class EvHandler(redzed.FSM):
        STATES = ['fixed']

        def _event_abc(self, _evalue, **_extra):
            pass

    eh = EvHandler('ctx')
    edt_keys = {name for name in eh._edt_handlers if not name.startswith("_get_")}
    assert edt_keys == {'abc'}


def test_enter_exit(circuit):
    """
    When enter/exit hooks for a state are called, that state must be the current state.
    Also check the sequence of hook calls.
    """
    trace = []
    class TestFSM(redzed.FSM):
        STATES = ["A", "B"]
        EVENTS = [
            ["ab", ["A"], "B"],
            ]

        def cond_ab(self):
            trace.append(0)
            assert self.get() == self.state == "A"
            return True
        def exit_A(self):
            trace.append(10)
            assert self.get() == self.state == "A"
        def enter_B(self):
            trace.append(20)
            assert self.get() == self.state == "B"

    def cond_ab():
        trace.append(1)
        assert fsm.get() == fsm.state == "A"
        return True
    def exit_A():
        trace.append(11)
        assert fsm.get() == fsm.state == "A"
    def enter_B1():
        trace.append(21)
        assert fsm.get() == fsm.state == "B"
    def enter_B2():
        trace.append(22)
        assert fsm.get() == fsm.state == "B"


    fsm = TestFSM("test_fsm", cond_ab=cond_ab, enter_B=[enter_B1, enter_B2], exit_A=exit_A)
    mini_init(circuit)
    fsm.event('ab')
    assert trace == [0, 1, 10, 11, 20, 21, 22]
