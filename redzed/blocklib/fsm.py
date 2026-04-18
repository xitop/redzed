"""
Event driven finite-state machine (FSM) extended with optional timers.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['FSM']

import asyncio
from collections.abc import Callable, Iterable, Mapping, Sequence
import functools
import inspect
import logging
import time
import types
import typing as t

import redzed
from redzed.utils import check_identifier, is_multiple, time_period, to_tuple


_logger = logging.getLogger(__package__)


def _loop_to_unixtime(looptime: float) -> float:
    """Convert event loop time to standard Unix time."""
    unixtime_func = time.time
    looptime_func = asyncio.get_running_loop().time
    unixbefore = unixtime_func()
    loopnow = looptime_func()
    unixafter = unixtime_func()
    timediff = (unixbefore + unixafter) / 2 - loopnow
    return looptime + timediff


_ALLOWED_KINDS = [inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD]

@functools.cache
def _hook_args(func: Callable[..., object]) -> int:
    """Check if *func* takes 0 or 1 argument."""
    params = inspect.signature(func).parameters
    plen = len(params)
    if plen > 1 or plen == 1 and next(iter(params.values())).kind not in _ALLOWED_KINDS:
        raise TypeError(
            f"Function {func.__name__} is not usable as an FSM hook "
            + "(incompatible call signature)")
    return plen


_HookType: t.TypeAlias = t.Literal['cond', 'duration', 'enter', 'exit', 'select']
# Self type cannot be used in type alias target
_HookMethodType: t.TypeAlias = Callable[["FSM", str], object] \
    | Callable[["FSM", str, redzed.EventData], object]


class FSM(redzed.Block):
    """
    A base class for a Finite-state Machine with optional timers.
    """

    # subclasses must define:
    STATES: Sequence[str|Sequence]
        # each state: non-timed: state
        #             or timed: [state, duration, next_state]
    EVENTS: Sequence[Sequence]
        # each item: [event, [state1, state2, ..., stateN], next_state]
        #        or: [event, ..., next_state] <- literal ellipsis
    # --- and redzed will translate that to: ---
    _ct_default_state: str
        # the default initial state (first item of STATES)
    _ct_duration: dict[str, float]
        # {timed_state: default_duration_in_seconds}
    _ct_dynamic_states: dict[str, _HookMethodType]
        # {dynamic_state: selector}
    _ct_events: set[str]
        # all valid events
    _ct_methods: dict[_HookType, dict[str, _HookMethodType]]
        # summary of cond_EVENT, duration_TSTATE, enter_STATE,
        # exit_STATE and select_DSTATE methods
    _ct_valid_names: dict[str, Iterable[str]]
        # helper for parsing
    _ct_states: set[str]
        # all valid states
    _ct_timed_states: dict[str, str]
        # {timed_state: following_state}
        # keys: all timed states
    _ct_transition: dict[tuple[str, str|None], str|None]
        # the transition table - higher priority: {(event, state): next_state}
        # the transition table - lower priority: {(event, None): next_state}

    @classmethod
    def _check_state(cls, state: object, dynamic_ok: bool = False) -> None:
        if not isinstance(state, str):
            raise TypeError(f"FSM state must be a string, but got: {state!r}")
        if state in cls._ct_states:
            return
        if dynamic_ok and state in cls._ct_dynamic_states:
            return
        raise ValueError(f"FSM state '{state}' is unknown")

    @classmethod
    def _add_transition(cls, event: str, state: str|None, next_state: str|None) -> None:
        if state is None and next_state is None and redzed.get_debug_level() >= 2:
            _logger.warning("Useless transition rule: [%s, ..., None]", event)
        key = (event, state)
        if key in cls._ct_transition:
            state_msg = "" if state is None else f" in state '{state}'"
            if cls._ct_transition[key] != next_state:
                raise ValueError(f"Multiple transition rules for event '{event}'{state_msg}")
            if redzed.get_debug_level() >= 2:
                _logger.warning("Duplicate transition rule for event '%s'%s", event, state_msg)
        cls._ct_transition[key] = next_state

    @classmethod
    def _build_tables(cls) -> None:
        """
        Build control tables from STATES and EVENTS.

        Control tables must be created for each subclass. The original
        tables are left unchanged. All control tables are class
        variables and have the '_ct_' prefix.
        """

        # dynamic pseudo-states
        cls._ct_dynamic_states = {}
        cls_members = []
        for method_name, method in inspect.getmembers(cls):
            if method_name.startswith('_') or not callable(method):
                continue
            if not method_name.startswith('select_'):
                # save for later
                cls_members.append((method_name, method))
                continue
            dstate = method_name[7:]    # remove 'select_'
            check_identifier(dstate, "dynamic state name")
            cls._ct_dynamic_states[dstate] = method

        # states
        if not is_multiple(cls.STATES) or not cls.STATES:
            raise ValueError("STATES: Expecting a non-empty sequence of states")
        cls._ct_states = set()
        timed_states: list[tuple[int, Sequence]] = []
        for i, entry in enumerate(cls.STATES, start=1):
            try:
                if is_multiple(entry):
                    if len(entry) != 3:
                        raise ValueError(
                            "Invalid timed state definition. "
                            + "Expected are three values: state, duration, next_state")
                    timed_states.append((i, entry))
                    state = entry[0]
                else:
                    state = entry
                check_identifier(state, "FSM state name")
                if i == 1:
                    cls._ct_default_state = state
                elif state in cls._ct_states:
                    raise ValueError(f"Duplicate definition for state '{state}'")
                if state in cls._ct_dynamic_states:
                    raise ValueError(
                        f"Dynamic pseudo-state '{state}' found in the STATES table.")
                cls._ct_states.add(state)
            except (ValueError, TypeError) as err:
                err.add_note(f"Offending entry: STATES table, item {i}")
                raise

        next_states = set()
        # timed states
        cls._ct_duration = {}
        cls._ct_timed_states = {}
        for i, (state, duration, next_state) in timed_states:
            try:
                # state was checked already, also for duplicates
                cls._check_state(next_state, dynamic_ok=True)
                next_states.add(next_state)
                if duration is not None:
                    try:
                        cls._ct_duration[state] = time_period(duration, zero_ok=True)
                    except (ValueError, TypeError) as err:
                        raise ValueError(
                            f"Could not convert duration of state '{state}' to seconds: {err}"
                            ) from None
                cls._ct_timed_states[state] = next_state
            except (ValueError, TypeError) as err:
                err.add_note(f"Offending entry: STATES table, item {i}")
                raise

        # events and state transitions
        cls._ct_transition = {}
        cls._ct_events = set()
        for i, (event, from_states, next_state) in enumerate(cls.EVENTS, start=1):
            try:
                j = 1
                check_identifier(event, "FSM event name")
                if event in cls._edt_handlers:
                    raise ValueError(
                        f"Ambiguous event '{event}': "
                        + "the name is used for both FSM and Block event")
                cls._ct_events.add(event)
                j = 2
                if from_states is ...:
                    # The ellipsis means any state. In control tables we are using None instead
                    cls._add_transition(event, None, next_state)
                else:
                    if not is_multiple(from_states):
                        if from_states in cls._ct_states:
                            hint = f" Did you mean: ['{from_states}'] ?"
                        else:
                            hint = ""
                        raise ValueError(
                            "Expected is a literal ellipsis (...) or a sequence of states, "
                            + f"got {from_states!r}{hint}")
                    for fstate in from_states:
                        cls._check_state(fstate)
                        cls._add_transition(event, fstate, next_state)
                j = 3
                if next_state is not None:
                    cls._check_state(next_state, dynamic_ok=True)
                    next_states.add(next_state)
            except (ValueError, TypeError) as err:
                # pylint: disable-next=used-before-assignment
                err.add_note(f"Offending entry: EVENTS table, item {i}, position: {j}/3")
                raise

        # check for unreachable dynamic states
        if (unreachable := cls._ct_dynamic_states.keys() - next_states):
            dstate = next(iter(unreachable))
            raise ValueError(
                f"Method 'select_{dstate}' is not valid; '{dstate}' is not a reachable state")

        # helper table: name 'prefix_suffix' is valid if prefix is a dict key
        # and suffix is listed in the corresponding dict value
        cls._ct_valid_names = {
            'cond': cls._ct_events,             # method or arg
            'duration': cls._ct_timed_states,   # method
            'enter': cls._ct_states,            # method or arg
            'exit': cls._ct_states,             # method or arg
            't': cls._ct_timed_states,          # arg
            # 'select' is processed separately
        }

        # class hooks
        cls._ct_methods = {
            'cond': {},             # data format: {EVENT: cond_EVENT method}
            'duration': {},         # {TSTATE: duration_TSTATE method}
            'enter': {},            # {STATE: enter_STATE method}
            'exit': {},             # {STATE: exit_STATE method}
            'select': cls._ct_dynamic_states,  # {DSTATE: select_DSTATE method}
            }
        for method_name, method in cls_members:
            try:
                # ValueError in assignment if split into two pieces fails:
                hook_type, name = method_name.split('_', 1)
                hook_dict = cls._ct_methods[hook_type]      # type: ignore[index]
            except (ValueError, KeyError):
                continue
            if name in cls._ct_valid_names[hook_type]:
                hook_dict[name] = method
            else:
                exc = ValueError(
                    f"Method name '{method_name}' is not valid; "
                    + f"please check the '{name}' symbol")
                name_list = ', '.join(
                    f"'{hook_type}_{n}'" for n in cls._ct_valid_names[hook_type])
                exc.add_note(f"Valid are: {name_list}")
                raise exc

    def __init_subclass__(cls, *args, **kwargs) -> None:
        """Build control tables."""
        # call super().__init_subclass__ first, we will then check for possible
        # event name clashes with the Block._edt_handlers
        super().__init_subclass__(*args, **kwargs)
        if not all(hasattr(cls, table) for table in ['STATES', 'EVENTS']):
            raise TypeError("An FSM requires two control tables: STATES and EVENTS")
        try:
            cls._build_tables()
        except Exception as err:
            err.add_note(
                f"Error occurred in FSM '{cls.__name__}' during validation of control tables")
            raise

    def __init__(self, *args, **kwargs) -> None:
        """
        Create FSM.

        Handle keyword arguments named t_TSTATE, cond_EVENT,
        enter_STATE and exit_STATE.
        """
        if type(self) is FSM:   # pylint: disable=unidiomatic-typecheck
            raise TypeError("Can't instantiate the 'FSM' base class")
        prefixed: dict[str, list[tuple[str, t.Any]]] = {
            'enter': [],
            'exit': [],
            't': [],
        }
        for arg in list(kwargs):
            try:
                hook_type, name = arg.split('_', 1)
                hook_list = prefixed[hook_type]
            except (ValueError, KeyError):
                continue
            valid_names = type(self)._ct_valid_names[hook_type]
            if name in valid_names:
                value = kwargs.pop(arg)
                if value is not redzed.UNDEF:
                    hook_list.append((name, value))
            else:
                err = TypeError(
                    f"'{arg}' is an invalid keyword argument for {self.type_name}")
                # Python 3.11 doesn't allow nested quotes in f-strings
                name_list = ', '.join(f"'{hook_type}_{n}'" for n in valid_names)
                err.add_note(f"Valid are: {name_list}")
                raise err
        # extra arguments are now removed from kwargs -> can call super().__init__
        super().__init__(*args, **kwargs)

        self._t_duration: dict[str, float] = {}   # values passed as t_TSTATE=duration
        for state, value in prefixed['t']:
            if (duration := time_period(value, passthrough=None, zero_ok=True)) is not None:
                self._t_duration[state] = duration
        self._instance_hooks = {
            hook_type: {name: to_tuple(value) for name, value in hooks}
            for hook_type in ['enter', 'exit'] if (hooks := prefixed[hook_type])}

        self._state: str|redzed.UndefType = redzed.UNDEF      # FSM state
        self.sdata: dict[str, object] = {}      # storage for additional internal state data
        # Restoring state differs in details from setting a new state.
        # _restore_timer values:
        #    UNDEF = no state to be restored
        #    None = restore a not-timed state
        #    float = restore a timed state and this is its expiration time (UNIX timestamp)
        self._restore_timer: float|None|redzed.UndefType = redzed.UNDEF
        self._active_timer: asyncio.Handle|None = None
        self._event_handler_lock = False    # detection of recursive calls
        self._edata: Mapping[str, t.Any]|None = None
            # read-only data of the currently processed event

    # DEPRECATED
    @property
    def state(self) -> str|redzed.UndefType:
        """Return the FSM state (string) or UNDEF if not initialized."""
        return self._state

    def fsm_state(self) -> str|redzed.UndefType:
        """Return the FSM state (string) or UNDEF if not initialized."""
        return self._state

    def rz_export_state(self) -> tuple[str, float|None, dict[str, object]]:
        """
        Return the block's internal state.

        The internal state is a broader term than the FSM state.
        Internal state consist of 3 items:
            - FSM state (str)
            - timer expiration timestamp or None if there is no timer.
              The timestamp uses UNIX time (float).
            - additional state data (sdata, a dict)
        """
        assert self._state is not redzed.UNDEF      # @mypy: contract
        timer = self._active_timer
        # we are using both plain Handle (call_soon) and TimerHandle (call_later)
        if isinstance(timer, asyncio.TimerHandle) and not timer.cancelled():
            timestamp = _loop_to_unixtime(timer.when())
        else:
            timestamp = None
        return (self._state, timestamp, self.sdata)

    def rz_restore_state(self, internal_state: Sequence, /) -> None:
        """
        Restore the internal state created by rz_export_state().

        cond_STATE and enter_STATE are not executed, because the state
        was already entered in the past. Now it is only restored.
        """
        if self._state is not redzed.UNDEF:
            raise RuntimeError(
                f"{self}: 'rz_restore_state' can be used only for initialization, "
                + "but this block has been initialized already")
        state, timestamp, sdata = internal_state
        self._check_state(state)
        if timestamp is not None:
            if state not in type(self)._ct_timed_states:
                self.log_debug2(
                    "Rejecting saved state: a timer was saved in FSM state '%s', "
                    + "but this state is now not timed", state)
                return
            if timestamp <= time.time():
                self.log_debug2("Rejecting saved timed state, because it has expired")
                return
        # state accepted
        self._restore_timer = timestamp
        self.sdata = sdata
        self._state = state
        self._set_output(self._state)

    def rz_init(self, init_value: str|Sequence, /) -> None:
        """Set the initial FSM state."""
        # Do not call self.event() for initialization.
        # It would try to initialize before processing the event.
        init_state, init_sdata = init_value if is_multiple(init_value) else (init_value, None)
        self._check_state(init_state)
        assert isinstance(init_state, str)  # @mypy
        self.log_debug1("initial state: %s", init_state)
        self._state = init_state
        if init_sdata is not None:
            self.log_debug1("initial sdata: %s", init_sdata)
            self.sdata = init_sdata.copy()
        self._set_output(self._state)

    def rz_init_default(self) -> None:
        """Initialize the internal state."""
        self.rz_init(type(self)._ct_default_state)

    def rz_start(self) -> None:
        """
        Start activities according to the initial state.

        Run 'enter' hooks unless the initial state was restored
        from the persistent storage, i.e. has been entered already
        in the past.

        Start the timer if the initial state is timed.
        """
        assert self._state is not redzed.UNDEF
        # restored state
        if self._restore_timer is not redzed.UNDEF:
            if self._restore_timer is not None:
                remaining = max(self._restore_timer - time.time(), 0.0)
                self._set_timer(remaining, type(self)._ct_timed_states[self._state])
            self._restore_timer = redzed.UNDEF     # value no longer needed
            return
        # new state
        self._start_now(self._state)

    def rz_stop(self) -> None:
        """Cleanup."""
        self._stop_timer()

    def _set_timer(self, duration: float, following_state: str) -> None:
        """Start the timer (low-level)."""
        if zero_delay := duration <= 0.0:
            duration = 0.0
        self.log_debug1("timer: %.3fs before entering '%s'", duration, following_state)
        loop = asyncio.get_running_loop()
        if zero_delay:
            self.log_debug2("note: zero delay is not possible due to overhead")
            self._active_timer = loop.call_soon(self._goto, following_state)
        else:
            self._active_timer = loop.call_later(duration, self._goto, following_state)

    def _get_timer_args(self, tstate: str) -> tuple[float, str]|None:
        """Get timer settings (_set_timer args) or None if no timer is to be set."""
        if (following_state := type(self)._ct_timed_states.get(tstate)) is None:
            return None     # not a timed state
        assert self._edata is not None      # @mypy
        duration = time_period(self._edata.get('duration'), passthrough=None, zero_ok=True)
        if duration is None:
            duration = time_period(
                self._run_hooks('duration', tstate, default=None),
                passthrough=None, zero_ok=True)
        if duration is None:
            duration = self._t_duration.get(tstate)
        if duration is None:
            duration = type(self)._ct_duration.get(tstate)
        if duration is None:    # not found or explicitly set to None
            raise RuntimeError(f"Timer duration for state '{tstate}' not set")
        if duration == float('inf'):
            return None
        return (duration, following_state)

    def _stop_timer(self) -> None:
        """Stop the timer, if any."""
        if (timer := self._active_timer) is not None:
            if not timer.cancelled():
                timer.cancel()
                # try not to log the cancellation if the timer has already fired, but
                # do not rely on the existence of the private attribute '_scheduled'
                if getattr(timer, '_scheduled', True):
                    self.log_debug2("timer: cancelled")
            self._active_timer = None

    def _run_hooks(
            self, hook_type: _HookType, name: str, default: object = redzed.UNDEF
            ) -> object:
        """
        Call hooks of given *hook_type* for given state/event *name*.

        Return the result of the hook defined as a method or *default*
        if such method doesn't exist. Results of hooks specified by
        an argument are ignored.
        """
        if (mhook := type(self)._ct_methods[hook_type].get(name)) is not None:
            self.log_debug2("Calling hook (class method) '%s_%s'", hook_type, name)
            # pylint: disable-next=unnecessary-dunder-call
            hook = mhook.__get__(self, type(self))
            retval = hook() if _hook_args(hook) == 0 else hook(self._edata)
        else:
            retval = default
        if (instance_hooks := self._instance_hooks.get(hook_type)) is not None:
            if (hooks := instance_hooks.get(name)) is not None:
                self.log_debug2(
                    "Calling %d hook(s) (external) '%s_%s'", len(hooks), hook_type, name)
                for hook in hooks:
                    # pylint: disable-next=expression-not-assigned
                    hook() if _hook_args(hook) == 0 else hook(self._edata)
        return retval

    def _event__get_config(self, _edata: redzed.EventData) -> dict[str, object]:
        """Debugging aid '_get_config'."""
        cls = type(self)
        # pylint: disable=protected-access
        return {
            # make values JSON serializable
            'durations': cls._ct_duration | self._t_duration,
            'dynamic_states': sorted(cls._ct_dynamic_states),
            'events': sorted(cls._ct_events),
            'states': sorted(cls._ct_states),
            'timed_transitions': cls._ct_timed_states,
            'transitions': [[ev, src, dest] for (ev, src), dest in cls._ct_transition.items()],
        }

    def _fsm_event_handler(self, etype: str) -> bool:
        """
        Handle event. Check validity and conditions.

        Timed states look for 'duration' key in 'edata'. If it is
        present, the value overrides the default timer duration.

        Return value:
            True = transition accepted and executed
            False = transition rejected
        """
        assert self._state is not redzed.UNDEF     # @mypy: tested in caller
        start_event = False     # special event used only when booting the FSM
        goto_event = False      # special event for ending a timed state
        dynamic_state = False
        next_state: str|None
        if etype.startswith("Goto:"):
            goto_event = True
            next_state = etype[5:]      # strip "Goto:" prefix
            self._check_state(next_state, dynamic_ok=True)
        elif etype.startswith("Start:"):
            start_event = True
            next_state = etype[6:]      # strip prefix
            if next_state != self._state:
                raise RuntimeError("Event 'Start:STATE' was used incorrectly")
        else:
            cls = type(self)
            # pylint: disable=protected-access
            if etype not in cls._ct_events:
                raise redzed.UnknownEvent("Unknown event type")
            # not using .get(key) because None and not found are different cases
            key: tuple[str, str|None]
            if (key := (etype, self._state)) not in cls._ct_transition:
                key = (etype, None)
            next_state = cls._ct_transition.get(key)
            if next_state is None:
                self.log_debug2(
                    "No transition defined for event '%s' in state '%s'", etype, self._state)
                return False
            if not self._run_hooks('cond', etype, default=True):
                self.log_debug2(
                    "event '%s' (%s -> %s) was rejected by cond_%s",
                    etype, self._state, next_state, etype)
                return False

        try:
            if (selected := self._run_hooks('select', next_state, default=None)) is not None:
                self._check_state(selected)
                assert isinstance(selected, str)    # @mypy: passed _check_state
                dynamic_state = True
                self.log_debug2("dynamic state '%s' -> '%s'", next_state, selected)
                next_state = selected
        except Exception as err:
            err.add_note(f"{self}: Error occurred in {self.type_name}.select_{next_state}()")
            if start_event or goto_event:
                self.circuit.abort(err)
            raise

        try:
            timer_args = self._get_timer_args(next_state)
        except Exception as err:
            if start_event or goto_event or dynamic_state:
                self.circuit.abort(err)
            raise

        try:
            if not start_event:
                self._run_hooks('exit', self._state)
                self._stop_timer()
                self.log_debug1("state: %s -> %s (event: %s)", self._state, next_state, etype)
            self._state = next_state
            self._set_output(self._state)
            if timer_args is not None:
                self._set_timer(*timer_args)
            self._run_hooks('enter', self._state)
        except Exception as err:
            self.circuit.abort(err)
            raise
        return True

    def _default_event_handler(self, etype: str, edata: redzed.EventData) -> bool:
        """
        Wrapper creating a separate context.

        Refer to _fsm_event_handler().
        """
        if self._event_handler_lock:
            raise RuntimeError("Recursion error: Got an event while handling an event.")
        self._event_handler_lock = True
        self._edata = types.MappingProxyType(edata)
        try:
            return self._fsm_event_handler(etype)
        except Exception as err:
            err.add_note(f"{self}: Error occurred while handling event '{etype}'")
            raise
        finally:
            self._event_handler_lock = False
            self._edata = None

    def _send_synthetic_event(self, etype: str) -> None:
        """
        Send an synthetic event (implementation detail).

        To protect the FSM, the synthetic event names are not
        accepted by the .event() entry point.
        """
        self.log_debug2("Synthetic event '%s'", etype)
        # we must bypass .event()
        self._default_event_handler(etype, {})

    def _goto(self, state: str) -> None:
        """Unconditionally go to 'state'. To be used by the FSM itself only!"""
        if self.circuit.is_shut_down():
            # this should be unreachable, because the timer should have been cancelled
            # during shutdown, but just for the case some kind of a race is possible
            return
        self._send_synthetic_event(f"Goto:{state}")
        if self.rz_save_flags & redzed.SaveFlags.EVENT:
            self.circuit.save_persistent_state(self)

    def _start_now(self, state: str) -> None:
        """Start after initialization. To be used by the FSM itself only!"""
        self._send_synthetic_event(f"Start:{state}")
