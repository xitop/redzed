"""
Test FSM blocks.
"""

# pylint: disable=missing-class-docstring, protected-access
# pylint: disable=unused-variable, unused-argument, no-member

import logging

import pytest

import redzed

from .utils import Exc, mini_init, EventMemory, add_ts, strip_ts


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
    with Exc(redzed.UnknownEvent):
        b123x.event('tsep')
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
    with Exc(TypeError, match="control tables"):
        class No0(redzed.FSM):
            """no table"""
            EVENTS=[]

    with Exc(ValueError, match="non-empty sequence"):
        class No1(redzed.FSM):
            """no states"""
            STATES=[]
            EVENTS=[]

    with Exc(ValueError, match="non-empty sequence"):
        class No2(redzed.FSM):
            STATES = "S1"
            EVENTS=[]

    with Exc(ValueError, match="Duplicate"):
        class No3(redzed.FSM):
            STATES = ["S1", "S2", "S2"]
            EVENTS=[]

    with Exc(ValueError, match="Duplicate"):
        class No4(redzed.FSM):
            STATES = [["S1", None, "S2"], "S2", ["S1", 1, "S2"]]
            EVENTS=[]


def test_unknown_states(circuit):
    with Exc(ValueError, match="unknown"):
        class No1(redzed.FSM):
            STATES = ["S1", ["S2", 0, "S3"]]
            EVENTS=[]

    with Exc(ValueError, match="unknown"):
        class No2(redzed.FSM):
            STATES = ["A", "B", "C"]
            EVENTS = [["e", ..., "nostate"]]

    with Exc(ValueError, match="unknown"):
        class No3(redzed.FSM):
            STATES = ["A", "B", "C"]
            EVENTS = [["e", ["B", "nostate"], "A"]]


def test_invalid_names(circuit):
    with Exc(ValueError, match='empty'):
        class ErrValue1(redzed.FSM):
            STATES = ['']
            EVENTS=[]

    with Exc(ValueError, match='empty'):
        class ErrValue2(redzed.FSM):
            STATES = ['S']
            EVENTS = [('', ..., 'S')]

    with Exc(ValueError, match='Ambiguous'):
        class ErrValue3(redzed.FSM):
            STATES = ['S']
            EVENTS = [('FOO', ..., 'S')]        # FSM event 'FOO'
            def _event_FOO(self, **kwargs):     # non-FSM event 'FOO'
                pass

    with Exc(ValueError, match='valid identifier'):
        class ErrValue4(redzed.FSM):
            STATES = ['X']
            EVENTS = [("Start:X", ..., 'X')]

    with Exc(TypeError, match="must be a string"):
        class ErrType1(redzed.FSM):
            STATES = [5, 6]
            EVENTS = [('E', 5, 6)]

    with Exc(TypeError, match="must be a string"):
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

    assert b123.fsm_state() == 'S1'

    b123.event('step')
    assert b123.fsm_state() == 'S2'

    b123._goto('S1')
    assert b123.fsm_state() == 'S1'

    with Exc(ValueError, match="is unknown"):
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


def test_bogus_hooks_kw(circuit):
    """Test incorrect hook names (protection against typos)."""
    class B123(redzed.FSM):
        STATES = ['S0', ('S1', None, 'S0')]
        EVENTS = [('E0', ..., 'S0')]

    B123('OK', enter_S0=lambda: None, exit_S1=lambda: None, t_S1=1)
    with Exc(TypeError, match="invalid keyword argument"):
        B123('wrong_hook1', enter_Sx=lambda: None)
    with Exc(TypeError, match="invalid keyword argument"):
        B123('wrong_hook2', exit_Sx=lambda: None)

    # hooks not available as kwargs
    with Exc(TypeError, match="unexpected keyword argument"):
        B123('wrong_hook3', cond_E0=lambda: True)
    with Exc(TypeError, match="unexpected keyword argument"):
        B123('wrong_hook4', select_Sx=lambda: 'S1')
    with Exc(TypeError, match="unexpected keyword argument"):
        B123('wrong_hook5', duration_S1=lambda: None)

    # actually not a hook, but similar
    with Exc(TypeError, match="invalid keyword argument"):
        B123('wrong_hook6', t_S0=1)


def test_bogus_hooks_meth(circuit):
    """Test incorrect hook names (protection against typos)."""
    class B123(redzed.FSM):
        STATES = ['S0', ('S1', None, 'S0')]
        EVENTS = [('E0', ..., 'S0')]

    # pylint: disable=multiple-statements
    class OK1(B123):
        def enter_S0(self): pass
        def exit_S1(self): pass
        def cond_E0(self): pass
        def duration_S1(self): return 1
    OK1('ok_fsm1')

    with Exc(ValueError, match="Method name 'enter_Sx' is not valid"):
        class Wrong1(B123):
            def enter_Sx(self): pass
    with Exc(ValueError, match="Method name 'exit_Sx' is not valid"):
        class Wrong2(B123):
            def exit_Sx(self): pass
    with Exc(ValueError, match="Method name 'cond_Ex' is not valid"):
        class Wrong3(B123):
            def cond_Ex(self): return True

    with Exc(ValueError, match="in the STATES table"):
        class Wrong4(B123):
            def select_S0(self): return 'S1'
    with Exc(ValueError, match="Method name 'duration_S0' is not valid"):
        class Wrong5(B123):
            def duration_S0(self): return 1
    with Exc(ValueError, match="not a reachable state"):
        class Wrong6(B123):
            def select_S2(self): return 'S1'


def test_incompatible_hooks(circuit):
    """Test incorrect hook signature."""
    class B123(redzed.FSM):
        STATES = ['S0', 'S1']
        EVENTS = [
            ('step', ['S0'], 'S1'),
            ('step', ['S1'], 'S0'),
            ]
        def enter_S1(self, arg1, arg2):
            pass

    test_fsm = B123('b123')
    errors = circuit.get_errors()

    mini_init(circuit)
    assert not errors
    with Exc(TypeError, match="incompatible"):
        test_fsm.event('step')
    # check that abort() was called
    assert len(errors) == 1 and isinstance(errors[0], TypeError)


async def test_dstate_error(circuit):
    """Dynamic state selection errors are fatal."""
    class TestFSM(redzed.FSM):
        STATES = ["A", "B", "C"]
        EVENTS = [
            ("dyn", ..., "D"),
            ]
        def select_D(self):
            return dest

    fsm = TestFSM('myfsm')

    mini_init(circuit)
    for dest in ["D", "E", "x.y", False]:
        with Exc((TypeError, ValueError)):
            fsm.event("dyn")
    dest = "A"
    assert fsm.event("dyn") is True


def test_cond(circuit):
    """Test the cond_EVENT."""
    class B123(redzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', ['S1'], 'S2'),
            ('step', ['S2'], 'S3'),
            ('step', ['S3'], 'S1')
            ]
        def cond_step(self, data):
            return data.get('passwd') == 'secret123'

    b123 = B123('b123fsm')
    mini_init(circuit)

    assert b123.fsm_state() == 'S1'

    assert not b123.event('step')   # rejected
    assert b123.fsm_state() == 'S1'
    assert not b123.event('step', passwd='guess')   # rejected
    assert b123.fsm_state() == 'S1'
    assert b123.event('step', passwd='secret123')   # accepted
    assert b123.fsm_state() == 'S2'


recursion_test_data_1 = [
    {'x_cond': True,  'x_enter': False, 'x_exit': False},
    {'x_cond': False, 'x_enter': True,  'x_exit': False},
    {'x_cond': False, 'x_enter': False, 'x_exit': True},
    ]
@pytest.mark.parametrize("x_kwargs", recursion_test_data_1)
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


recursion_test_data_2 = [
    {'x_enter': True,  'x_exit': False},
    {'x_enter': False, 'x_exit': True},
    ]
@pytest.mark.parametrize("x_kwargs", recursion_test_data_2)
def test_no_event_in_hooks_2(circuit, x_kwargs):
    """Hooks (external functions) may not call event."""
    class TestFSM(redzed.FSM):
        STATES = ["A", "B", "C"]
        EVENTS = [
            ["ab", ["A"], "B"],
            ["gotoC", ..., "C"],
            ]

    def enter_B():
        if fsm.x_enter:
            fsm.event("gotoC")
    def exit_A():
        if fsm.x_exit:
            indirect()

    fsm = TestFSM("test_fsm", **x_kwargs, enter_B=enter_B, exit_A=exit_A)
    def indirect():
        fsm.event("gotoC")

    mini_init(circuit)
    with Exc(RuntimeError):
        fsm.event('ab')


def test_persistent_state(circuit):
    class Dummy(redzed.FSM):
        STATES = list("ABCDEF")
        EVENTS = []

    def forbidden():
        assert False

    mem = EventMemory('mem')
    fsm = Dummy(
        'test', initial=redzed.PersistentState(save_flags=redzed.SF_EVENT),
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

    assert fsm.fsm_state() == 'D'
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
            with Exc(TypeError):
                data['new_item'] = 0
            assert data['a'] == 1
            return True

    simple = Simple('simple')
    mini_init(circuit)
    assert simple.fsm_state() == 'st0'
    simple.event('ev01', a=1)
    assert simple.fsm_state() == 'st1'


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
    assert cfsm.fsm_state() == 'st0'
    afsm.event('ev01', sent_to='A')     # A -> B -> C
    assert cfsm.fsm_state() == 'st1'


def test_dispatch_table(circuit):
    """No bogus entries in the dispatch table."""
    class EvHandler(redzed.FSM):
        STATES = ['fixed']
        EVENTS = []

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
            assert self.get() == self.fsm_state() == "A"
            return True
        def exit_A(self):
            trace.append(10)
            assert self.get() == self.fsm_state() == "A"
        def enter_B(self):
            trace.append(20)
            assert self.get() == self.fsm_state() == "B"

    def exit_A():
        trace.append(11)
        assert fsm.get() == fsm.fsm_state() == "A"
    def enter_B1():
        trace.append(21)
        assert fsm.get() == fsm.fsm_state() == "B"
    def enter_B2():
        trace.append(22)
        assert fsm.get() == fsm.fsm_state() == "B"


    fsm = TestFSM("test_fsm", enter_B=[enter_B1, enter_B2], exit_A=exit_A)
    mini_init(circuit)
    fsm.event('ab')
    assert trace == [0, 10, 11, 20, 21, 22]


def test_sdata_init(circuit):
    """Test sdata initial contents"""
    class TestFSM(redzed.FSM):
        STATES = ["A", "B"]
        EVENTS = []

    f1 = TestFSM('f1')
    f2 = TestFSM('f2', initial='B')
    init_sdata = {'first': 1, 'second': 2}
    f3 = TestFSM('f3', initial=('A', init_sdata))

    mini_init(circuit)
    del init_sdata['first']     # f3.sdata is a copy
    assert f1.fsm_state() == 'A'
    assert f1.sdata == {}
    assert f2.fsm_state() == 'B'
    assert f2.sdata == {}
    assert f3.fsm_state() == 'A'
    assert f3.sdata == {'first': 1, 'second': 2} != init_sdata


def test_warnings(circuit, caplog):
    """Test warnings about suspicious rules"""
    caplog.set_level(logging.WARNING)
    dbg = redzed.get_debug_level()
    redzed.set_debug_level(2)
    class TestFSM1(redzed.FSM):
        STATES = ['A', 'B']
        EVENTS = [
            # this rule is useless, because what is says is:
            # disallow not allowed transitions
            ('E', ..., None)
            ]

    class TestFSM2(redzed.FSM):
        STATES = ['A', 'B', 'C']
        EVENTS = [
            ('E1', ['B', 'C'], 'A'),
            ('E1', ['C'], 'A'),
            ]

    redzed.set_debug_level(dbg)
    assert len(caplog.record_tuples) == 2
    _, level, msg = caplog.record_tuples[0]
    assert level == logging.WARNING
    assert msg == "Useless transition rule: [E, ..., None]"
    _, level, msg = caplog.record_tuples[1]
    assert level == logging.WARNING
    assert msg == "Duplicate transition rule for event 'E1' in state 'C'"


def test_ambiguous_tables(circuit):
    """Test non-deterministic tables."""
    with Exc(ValueError, match="Multiple transition rules"):
        class TestFSM1(redzed.FSM):
            STATES = ['A', 'B', 'C']
            EVENTS = [
                ('E1', ['B', 'C'], 'A'),
                ('E1', ['A', 'B'], 'C'),
                # event E1, state B --> A or C ?!
                ]

    with Exc(ValueError, match="Multiple transition rules"):
        class TestFSM2(redzed.FSM):
            STATES = ['A', 'B', 'C']
            EVENTS = [
                ('E1', ..., 'A'),
                ('E1', ..., 'C'),
                # event E1, any state --> A or C ?!
                ]

    # but these rules are OK
    class TestFSM3(redzed.FSM):
        STATES = ['A', 'B', 'C']
        EVENTS = [
            ('E1', ...,   'A'),     # lower priority
            ('E1', ['B'], 'C'),     # higher priority
            ]


def test_get_config(circuit):
    """Test config info."""
    class TestFSM(redzed.FSM):
        STATES = [
            "A", "B", ("C", 10, "D")]
        EVENTS = [
            ("evb", ["A", "C"], "B"),
            ]
        def select_D(self):
            return "A"

    TestFSM('myfsm', t_C = 3)
    mini_init(circuit)

    config = redzed.send_event('myfsm', '_get_config')
    CONFIG = {
        'durations': {"C": 3},
        'dynamic_states':["D"],
        'events': ["evb"],
        'states': ["A", "B", "C"],
        'timed_transitions': {"C": "D"},
        'transitions': [["evb", "A", "B"], ["evb", "C", "B"]],
        # 'config' may contain additional items
    }
    for k, v in CONFIG.items():
        assert config[k] == v
