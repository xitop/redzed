.. currentmodule:: redzed

=====================
Finite-State Machines
=====================


FSM introduction
================

A basic understanding of the Finite-State Machine concept is assumed.
There are many tutorials available on the Internet.

A Finite-State Machine ("**FSM**") is defined by:

- set of possible states, one of them is the initial state
- set of recognized events; events trigger transitions from one state to another
- a control table called a transition table

Redzed's :class:`FSM` block implements several additional features and extensions:

- persistent state across restarts
- timed states
- dynamically selected states
- conditionally accepted events
- entry and exit actions

.. note::

  Every logic block has its internal state and can process events.
  An FSM also defines states and events. Their relationship is:

  - FSM state is a subset of a broader logic block's internal state,
    which contains for instance also the timer's state.
  - FSM events are a subset of all events accepted by the underlying
    logic block. E.g. :ref:`monitoring events <Monitoring events>`
    are not FSM events.

  In this chapter by 'state' and 'event' we usually mean an FSM state
  and an FSM event respectively.

Let's start with a simple example::

  class Turnstile(redzed.FSM):
      STATES = ['locked', 'unlocked']
      EVENTS = [
          ['coin', ['locked'], 'unlocked'],
          ['push', ['unlocked'], 'locked'],
      ]

  t1 = Turnstile('t1', comment="example turnstile #1")
  t2 = Turnstile('t2', comment="example turnstile #2")

We have defined a new FSM and created two circuit blocks.

:class:`Turnstile` has two states: 'locked' and 'unlocked',
the first one is the initial state by default.

It accepts two events: 'coin' and 'push'.

When the event 'coin' occurs in the 'locked' state, the FSM
makes a transition to the 'unlocked' state.

When the event 'push' occurs in the 'unlocked' state, the FSM
makes a transition to the 'locked' state.

There are no other state transitions defined. For example, when the
turnstile is 'locked', the 'push' event will have no effect.
We may say that an event is not accepted, not allowed or even rejected
in certain state, but it's a normal FSM operation - not an error.


Creating FSM types
==================

A new FSM is type created by subclassing the base class.
:ref:`Instances <Creating FSM blocks>` of this subclass will be circuit blocks.

.. class:: FSM

  Base class for creating FSMs. An :class:`!FSM` block is a highly customizable
  logic block. In circuit theory, a Finite-State Machine is a mathematical model
  of *sequential logic*.

  Subclasses must define two class attributes:

  - :attr:`FSM.STATES`
  - :attr:`FSM.EVENTS`

  and may define these hooks:

  - :ref:`state entry and exit actions <State entry and exit actions>`
  - :ref:`conditions for event acceptance <Conditional events>`
  - :ref:`timed state duration setters <Timed state duration>`
  - :ref:`dynamic state selector <Dynamic state>`


States, events, transitions
---------------------------

An FSM has a current state. A transition from the current state
to the next state is triggered by a received event. The next state
is determined by a transition table lookup:

    (event, current_state) --> next_state

All states and events are represented by a name (string) which must
be a valid identifier. States and events form two separate namespaces,
but using the same name for both is discouraged.

The :meth:`FSM.event` method returns :const:`True` for accepted FSM events
and :const:`False` for rejected FSM events.


Dynamically selected states
+++++++++++++++++++++++++++

A dynamically selected state ("dynamic state" for short) is a pseudo-state that
acts as a placeholder for a computed next state. A dynamic state is identified
by its name (string) just like any other state, but it is not a valid FSM state.
It cannot become a current state and cannot have enter or exit actions.

Every time a transition to some dynamic state ``"DSTATE"`` should take place,
a corresponding :ref:`method <Dynamic state>` is called to compute the real
(i.e. non-dynamic) state to be entered instead. The existence of the
special :meth:`FSM.select_DSTATE` method makes a state dynamic.


Control tables
--------------

The transition table is defined by :attr:`STATES` and :attr:`EVENTS`:

.. attribute:: FSM.STATES
  :type: Sequence[str|Sequence]

  Class attribute.

  A non-empty :abbr:`sequence (a list or tuple)` of all valid states, both regular and timed.
  Do not list dynamic states here. The very first item in this list is the default
  initial state.

  **Regular states**

  Regular states are given by their name (string).

  **Timed states**

  A timed state has a timer associated with it. After certain time,
  the timer generates a synthetic event causing an unconditional transition
  to next state.

  A timed state is defined by a sequence of three values::

    # timed state definition
    #   timed_state_name: str
    #   default_duration: str|float|None
    #   next_state (may be dynamic): str
    (timed_state_name, default_duration, next_state)

  The default duration can be overridden statically in an instance
  and also dynamically at runtime. Refer to: :ref:`Duration of timed state`.

.. attribute:: FSM.EVENTS
  :type: Sequence[Sequence]

  Class attribute.

  The transition table as a sequence of transition rules. Each rule in
  the sequence has three items::

    # event: str
    # states: Sequence[str]|Literal[...]
    # next_state (may be dynamic): str|None
    [event, states, next_state]

  *states* (item 2) define in which states will the *event* (item 1)
  trigger a transition to the *next_state* (item 3).
  The order of rules does not matter, but the transition table must be deterministic.
  Only one next state may be defined for any combination of event and state.
  In detail:

  - *event* is the name of an event. Only events present in this :attr:`!EVENTS` table
    are valid events for the given FSM.

  - *states* must be one of:

    - a sequence of states (strings)
    - a literal *...* (a.k.a. the Ellipsis) as a special value for any state.
      An entry with *...* has lower priority than entries with explicitly
      listed states.

  - *next_state* must be:

    - a single state (string), or
    - :const:`None` to make a transition explicitly disallowed.

  Examples of :attr:`!EVENTS` entries::

    # when an FSM is in state 'sleep' or 'on',
    # the event 'start' changes its state to 'off'
    ('start', ['sleep', 'on'], 'off'),

    # a single state must be given as a sequence too
    ('push', ['unlocked'], 'locked'),

    # If there exist only states 'sleep', 'on', and 'off', then the following
    # two lines have the same meaning, because the symbol ... means any state.
    # However the former (with ... = lower priority) can be overridden,
    # but the latter (with explicitly listed states = higher priority) cannot:
    ('start', ..., 'on'),
    ('start', ['sleep', 'on', 'off'], 'on'),

    ["finish", ..., "off"],     # default rule for 'finish' event and all states except
                                # more specific rules for 'not_ready' and 'pause' below
    ["finish", ["not_ready"], "error"],   # override: rule for state2 -> 'error'
    ["finish", ["pause"], None],          # override: finish is ignored in 'pause'


'**_get_config**' monitoring event
++++++++++++++++++++++++++++++++++

FSM blocks support the ':ref:`_get_config`' monitoring event. It returns the internal
control tables.


Event error handling
--------------------

The important point for handling of exceptions during state transitions
is when exactly they were raised.

**Non-fatal exceptions**:
  If the state transition was initiated by an explicit :meth:`Block.event`
  call and the exception occurred during preparations, the :meth:`!event`
  call is terminated by that exception, the current FSM state remains unchanged
  and the FSM continues its work.

  Examples: :exc:`UnknownEvent`; transition to a timed state
  with an unknown duration; exception in :meth:`FSM.cond_EVENT`.

**Fatal exceptions**:
  If the exception has interrupted a state transition already in progress, the
  error is deemed critical and causes an immediate :meth:`Circuit.abort`.

  Examples: exceptions in :ref:`entry and exit actions <State entry and exit actions>`;
  errors in transitions not initiated explicitly, e.g. by expired timed states.


Duration of timed state
-----------------------

When a timed state is entered, its timer is set. The timer's duration
is taken from the first available source that is not :const:`None`.
Each of them is suitable for a different use case type. From highest
priority to the lowest:

1. the ``'duration'`` item in the event data of the event that
   caused the transition to a timed state
2. result of :meth:`FSM.duration_TSTATE` call
3. duration set in the block with a *t_TSTATE* :ref:`parameter <FSM parameters>`
4. default set in the :attr:`FSM.STATES` table

If none of these sources produces a valid duration, the timed state
is not entered and an exception is raised instead.

When the timer expires, the *next_state* (as defined in the :attr:`FSM.STATES` table)
is entered. If the timed state is exited before the timer expiration, the timer is cancelled.
This means that a transition from a timed state to the same state restarts
the timer. If this is unwanted, disallow the transition.

Duration 0.0 is accepted, but the timed state will be entered for
a brief moment just due to the overhead.

If the duration is :const:`float("inf")` (infinite time to expiration),
the timer won't be set at all.

In all four cases the timer duration may be given as:
  - non-negative number of seconds,
  - a :ref:`string with time units <Time durations with units>`
  - :const:`float("inf")` a.k.a. :const:`math.inf`
  - :const:`None` to indicate the duration is not set here
    and must be obtained from other source


Additional internal state data
------------------------------

.. attribute:: FSM.sdata
  :type: dict[str, object]

  In some cases the internal state consists of more values than just the current
  FSM state and the timer state. This additional data should be stored here
  as key=value pairs. All keys must be strings.

  :attr:`sdata` is created empty. If need be, its contents can be set
  during initialization. See the *initial* option in :ref:`FSM parameters`.

  Because the :attr:`FSM.sdata` dict is by definition a part of the internal state,
  it is automatically saved and restored when the :ref:`persistent state <Persistent state>`
  is turned on. Note that the underlying persistent data storage must be able to serialize
  the data types used in :attr:`!FSM.sdata`.


Current state and output
------------------------

.. method:: FSM.fsm_state() -> str|redzed.UndefType

  Get the current FSM state. Uninitialized FSMs return :const:`UNDEF`.

The output (:meth:`Block.get()`) is by default equal to the current state.
If a different output is required, override the :meth:`Block._set_output` method.
See the :ref:`examples <FSM examples>`.


Hooks
-----

Hooks (a.k.a. callbacks) are optional functions called under certain circumstances.
Supported are:

- :ref:`State entry and exit actions <State entry and exit actions>`.
  These hooks are named ``enter_STATE`` and ``exit_STATE`` respectively.
  ``STATE`` represents a state name.
- :ref:`Conditional events <Conditional events>`.
  These hooks are named ``cond_EVENT`` where ``EVENT`` is an event name.
- :ref:`Computation of timed state duration<Timed state duration>`.
  These hooks are named ``duration_TSTATE`` where ``TSTATE``
  is a timed state name.
- :ref:`Dynamic state selectors <Dynamic state>`.
  These hooks are named ``select_DSTATE`` where ``DSTATE``
  is a dynamic pseudo-state name.

FSM hooks are methods defined within the class and having the appropriate hook name.
Additionally, ``enter_STATE`` and ``exit_STATE`` can be defined also per instance
as external functions. Use the hook name as a keyword argument and pass a function
or a sequence of functions.

Incorrectly formed names (e.g. ``enter_foo``, where ``foo`` is not a state)
will be rejected with an error.

.. important::

  Hooks may not initiate a state transition of their FSM.
  It is an error to call own ``.event(fsm_event)`` within block's hook.


Call arguments
++++++++++++++

Hooks are called either with no arguments or with one argument depending on
how they were defined. The `self` parameter in methods is not counted.
The parameter must be positional (not keyword-only,
not :abbr:`variadic (*args or **kwargs)`).

Obviously, hooks not taking any arguments are called without arguments.
Hooks taking one argument are called with a *read-only* proxy of the
:ref:`event data <Event type and data>` belonging to the currently processed event.
Following sections list both call signature alternatives.


State entry and exit actions
++++++++++++++++++++++++++++

Optional functions acting as entry and exit actions have the names:

- ``enter_STATE``
    entry action for state ``STATE``. It is called when the ``STATE``
    has been just entered.

- ``exit_STATE``
    exit action for state ``STATE``. It is called just before the ``STATE``
    is going to be exited.

The actions may be defined as:

- methods:

  .. method:: FSM.enter_STATE() -> object
  .. method:: FSM.enter_STATE(edata) -> object
    :noindex:

    Optional entry action for ``STATE``.

  .. method:: FSM.exit_STATE() -> object
  .. method:: FSM.exit_STATE(edata) -> object
    :noindex:

    Optional exit action for ``STATE``.

- external functions defined in an instance with a keyword argument
  (e.g. ``enter_STATE=my_func``). The argument is a function or a sequence
  of functions. They will be all called in given order, but after
  the class method.

The return values are ignored.


Conditional events
++++++++++++++++++

If a hook named ``cond_EVENT`` exists, it will be called each time
an event named ``EVENT`` arrives. The hook decides if the event will
be accepted.

.. method:: FSM.cond_EVENT() -> bool
.. method:: FSM.cond_EVENT(edata) -> bool
  :noindex:

  Optional method specifying a condition for event ``EVENT`` acceptance.
  The event will be accepted if the method returns boolean true
  value and rejected otherwise. The code may even raise an exception
  (e.g. a :exc:`ValidationError`), if it is appropriate for the application.
  The exception will be propagated according to
  the :ref:`rules <Event error handling>`.


Timed state duration
++++++++++++++++++++

.. method:: FSM.duration_TSTATE() -> float|str|None
.. method:: FSM.duration_TSTATE(edata) -> float|str|None
  :noindex:

  Optional method computing the duration of a timed state.
  It should return either the duration of the ``TSTATE`` in seconds
  or :const:`None` to indicate that the default duration
  should be used instead. See also: :ref:`Duration of timed state`.

  Note that this method is called when the transition to ``TSTATE``
  is being prepared, so the current state is not set to ``TSTATE`` yet.


Dynamic state
+++++++++++++

.. method:: FSM.select_DSTATE() -> str
.. method:: FSM.select_DSTATE(edata) -> str
  :noindex:

  This method defines a :ref:`dynamic pseudo-state <Dynamically selected states>`
  named ``DSTATE``. When called, it must return the name of a real state
  to be entered instead of ``DSTATE``. The new state cannot be dynamic.
  An FSM cannot continue without having a valid state, that's why
  a problem in :meth:`!FSM.select_DSTATE` always aborts the circuit runner.


FSM examples
===============

**Timer**

:class:`Timer` source (some checks omitted for brevity)::

  class Timer(redzed.FSM):
      STATES = [
          ['off', float("inf"), 'on'],
          ['on', float("inf"), 'off']]
      EVENTS = [
          ['start', ..., 'on'],
          ['stop', ..., 'off'],
          ['toggle', ['on'], 'off'],
          ['toggle', ['off'], 'on']]

      def __init__(self, *args, restartable: bool = True, **kwargs):
          if 't_period' in kwargs:
              period = time_period(kwargs.pop('t_period'))
              kwargs['t_on'] = kwargs['t_off'] = period / 2
          super().__init__(*args, **kwargs)
          self._restartable = bool(restartable)

      def cond_start(self) -> bool:
          return self._restartable or self._state != 'on'

      def cond_stop(self) -> bool:
          return self._restartable or self._state != 'off'

      def _set_output(self, output) -> bool:
          return super()._set_output(output == 'on')

----

**AfterRun**

In the following example, the output is :const:`True` between the ``start`` and ``stop``
events and also during the following after-run period. The after-run duration is
calculated as a percentage of the regular run duration. :attr:`FSM.sdata` is used
to hold the timestamp necessary for the calculation::

  class AfterRun(redzed.FSM):
      STATES = [
          'off',
          'on',
          ['afterrun', None, 'off'],
      ]
      EVENTS = [
          ['start', ['off'], 'on'],
          ['stop', ['on'], 'afterrun'],
      ]

      def enter_on(self):
          self.sdata['started'] = time.time()

      def duration_afterrun(self):
          return (time.time() - self.sdata.pop('started')) * (self.x_percentage / 100.0)

      def _set_output(self, output):
          return super()._set_output(output != 'off')

  AfterRun('after_run', x_percentage=50)


Creating FSM blocks
===================

FSM parameters
--------------

Summary of common parameters accepted as keyword arguments by classes derived
from the :class:`FSM` class.

``'STATE'`` and ``'TSTATE'`` are placeholders to be substituted by real state names.

- ``t_TSTATE=duration``
    Override for the default duration of ``TSTATE``; see "timed states" in :attr:`FSM.STATES`.
    The value must be a number of seconds
    or a :ref:`string with time units <Time durations with units>`.

- ``enter_STATE=function``
- ``exit_STATE=function``
    (sequence of functions is also accepted)

    See: :ref:`State entry and exit actions`

- ``initial=...``
    This parameter sets the initial FSM state. Optionally, the additional
    data (:attr:`!sdata`) can be initialized as well. Default FSM state is the first state
    listed in :attr:`FSM.STATES`. The *initial* argument also controls
    the state persistence which can be enabled by using
    :class:`PersistentState` as a :ref:`block initializer <Initializers>`.

    The initialization value is usually a single string - the initial state.
    It can be also a :abbr:`sequence (list or tuple)` containing two values:
    the initial state (type: `str`) and the initial :attr:`FSM.sdata`
    contents (type: `dict[str, object]`).


FSM Initialization rules
========================

During initialization, i.e. when the very first state is entered:

- ``exit_STATE`` is not executed, because there is no ``STATE`` to exit.
- ``cond_EVENT`` is not executed, because the first state is
  entered unconditionally.
- ``enter_STATE`` is executed except when initializing from saved (persistent)
  state. Initialization from saved state is a continuation of work
  in a state that was already entered in the past.
