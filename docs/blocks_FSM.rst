.. currentmodule:: redzed

=====================
Finite-State Machines
=====================

A Finite-State Machine (**FSM**) is a highly customizable logic block.
A basic understanding of the Finite-State Machine concept is helpful.
There are many tutorials available on the Internet.

A Finite-State Machine is defined by:

- set of possible states, one of them is the initial state
- set of recognized events; events trigger transitions from one state to another
- a control table called a transition table

An FSM block implements several additional features:

- persistent state across restarts
- timed states
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

FSM introduction
================

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
turnstile is 'unlocked', the 'coin' event will have no effect.
We may say that an event is not accepted, not allowed or even rejected
in certain state, but it's a normal FSM operation - not an error.


Creating FSM types
==================

A new FSM is type created by subclassing the base class.
:ref:`Instances <Creating FSM blocks>` of this subclass will be circuit blocks.

.. class:: FSM

  Base class for creating FSMs.

  Subclasses must define two class attributes:

  - :obj:`FSM.STATES`
  - :obj:`FSM.EVENTS`

  and may define these hooks:

  - :ref:`state entry and exit actions <State entry and exit actions>`
  - :ref:`conditions for event acceptance <Conditional events>`
  - :ref:`timed state duration setters <Timed state duration>`


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

In Redzed, there are also *timed states*. A timed state has a timer
associated with it. After certain time, the timer generates a synthetic event
causing a transition to another state.


.. attribute:: FSM.STATES
  :type: Sequence[str|Sequence]

  Class attribute.

  A :abbr:`sequence (a list or tuple)` of all valid states, timed and non-timed.
  The very first item in this list is the default initial state.

  A regular state is given by its name (string). A timed state is defined by
  a sequence of three values::

    # timed_state: str
    # default_duration: str | float | None
    # next_state: str
    [timed_state, default_duration, next_state]

  The default duration can be overridden statically in an instance
  and also dynamically at runtime. Refer to: :ref:`Duration of timed state`.

.. attribute:: FSM.EVENTS
  :type: Sequence[Sequence]

  Class attribute.

  The transition table as a sequence of transition rules. Each rule in
  the sequence has three items::

    # event: str
    # states: Sequence[str] | Literal[...]
    # next_state: str | None
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


Duration of timed state
-----------------------

When a timed state is entered, its timer is set. The duration of this time period
is taken from the first available source that is not :const:`None`. From the
highest priority to the lowest:

1. the ``'duration'`` item in the event data of the event that
   caused the transfer to a timed state
2. result of :meth:`FSM.duration_TSTATE` call
3. duration set in the instance with a *t_TSTATE* :ref:`parameter <FSM parameters>`
4. default set in the :data:`FSM.TIMED_STATES` table

If none of these sources produces a valid duration, an exception is raised.

When the timer expires, the *next_state* (as defined in the :data:`FSM.TIMED_STATES` table)
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
  :type: dict[str, Any]

  In some cases the internal state consists of more values than just the current
  FSM state and the timer state. This additional data should be stored here
  as key=value pairs. All keys must be strings.

  Because the :attr:`FSM.sdata` dict is by definition a part of the internal state,
  it is automatically saved and restored when the :ref:`persistent state <Persistent state>`
  is turned on. Note that the underlying persistent data storage must be able to serialize
  the data types used in :attr:`!FSM.sdata`.


Current state and output
------------------------

.. data:: FSM.state

  The current FSM state. A read-only property.

The output is by default equal to the current state. If a different output is required,
override the :meth:`Block._set_output` method. See the :ref:`examples <FSM examples>`.


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

FSM hooks can exist as methods having the appropriate hook name defined within the class.
With exception of the ``duration_TSTATE`` hooks, they can be defined also per instance
as external functions. Use the hook name as a keyword argument and pass a function
or a sequence of functions.

.. important::

  Hooks may not initiate a state transition of their FSM.
  It is an error to call own ``.event(fsm_event)`` within block's hook.


Call arguments
++++++++++++++

Hooks are called either with zero or with exactly one argument depending on
how they were defined. The `self` parameter in methods is disregarded.
The parameter must be positional. i.e. not keyword-only,
nor :abbr:`variadic (*args or **kwargs)`.

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

  .. method:: FSM.enter_STATE() -> Any
  .. method:: FSM.enter_STATE(edata) -> Any
    :noindex:

    Optional entry action for ``STATE``.

  .. method:: FSM.exit_STATE() -> Any
  .. method:: FSM.exit_STATE(edata) -> Any
    :noindex:

    Optional exit action for ``STATE``.

- external functions defined in an instance with a keyword argument
  (e.g. ``enter_STATE=my_func``). The argument is a function or a sequence
  of functions. They will be all called in given order, but after
  the class method.

The return values are ignored.


Conditional events
++++++++++++++++++

Optional functions deciding if an event will be accepted or rejected.

Hooks named ``cond_EVENT`` are called when ``EVENT`` arrives. It will be accepted
only if *all* ``cond_EVENT`` return boolean true value.

These functions may be defined as:

- a method:

  .. method:: FSM.cond_EVENT() -> bool
  .. method:: FSM.cond_EVENT(edata) -> bool
    :noindex:

    Check a condition for event ``EVENT`` acceptance.

- external functions defined in an instance with a keyword argument
  (e.g. ``cond_EVENT=my_func``). The argument is a function or a sequence
  of functions.

If there exist multiple functions, the evaluation is short-circuited.
When one function returns boolean false, the event is immediately rejected and
no other functions will be called. These functions should have no side effects.


Timed state duration
++++++++++++++++++++

- this hook can be defined only as a method:

  .. method:: FSM.duration_TSTATE() -> float | str | None
  .. method:: FSM.duration_TSTATE(edata) -> float | str | None
    :noindex:

    An optional method computing the duration of a timed state.
    It should return either the duration of the ``TSTATE`` in seconds
    or :const:`None` to indicate that the default duration
    should be used instead. See also: :ref:`Duration of timed state`.


FSM examples
===============

**Timer**

:class:`Timer` source (some checks omitted for brevity)::

  class Timer(fsm.FSM):
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


``'STATE'``, ``'TSTATE'`` and ``'EVENT'`` are placeholders to be substituted by real
state and event names.

- ``t_TSTATE=duration``
    See: :obj:`FSM.TIMED_STATES`

- ``cond_EVENT=function``
    (sequence of functions is also accepted, e.g. ``cond_EVENT=[func1, func2, ... ]``)

    See: :ref:`Conditional events`

- ``enter_STATE=function``
- ``exit_STATE=function``
    (sequence of functions is also accepted)

    See: :ref:`State entry and exit actions`

- ``initial=...``
    This parameter sets the initial FSM state. Default is the first state
    listed in :obj:`FSM.STATES`. The *initial* argument also controls
    the persistent state which can be enabled using :class:`RestoreState`.

    See: :ref:`Block initializers <Initializers>`


FSM Initialization rules
========================

During initialization, i.e. when the very first state is entered:

- ``exit_STATE`` is not executed, because there is no ``STATE`` to exit.
- ``cond_EVENT`` is not executed, because the first state needs
  to be entered unconditionally.
- ``enter_STATE`` is executed except when initializing from saved (persistent)
  state. Initialization from saved state is a continuation of work
  in a state that was already entered in the past.
