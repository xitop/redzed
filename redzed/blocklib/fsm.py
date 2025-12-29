"""
Event driven finite-state machine (FSM) extended with optional timers.

- - - - - -
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
def _hook_args(func: Callable[..., t.Any]) -> int:
    """Check if *func* takes 0 or 1 argument."""
    params = inspect.signature(func).parameters
    plen = len(params)
    if plen > 1 or any(p.kind not in _ALLOWED_KINDS for p in params.values()):
        raise TypeError(
            f"Function {func.__name__} is not usable as an FSM hook "
            + "(incompatible call signature)")
    return plen


class FSM(redzed.Block):
    """
    A base class for a Finite-state Machine with optional timers.
    """

    # subclasses should define:
    ALL_STATES: Sequence[str] = []
    TIMED_STATES: Sequence[Sequence] = []
        # each timed state: [state, duration, next_state]
    EVENTS: Sequence[Sequence] = []
        # each item: [event, [state1, state2, ..., stateN], next_state]
        #        or: [event, ..., next_state] <- literal ellipsis
    # --- and redzed will translate that to: ---
    _ct_default_state: str
        # the default initial state (first item of ALL_STATES)
    _ct_duration: dict[str, float]
        # {timed_state: default_duration_in_seconds}
    _ct_events: set[str]
        # all valid events
    _ct_methods: dict[str, dict[str, Callable[[t.Self, str], t.Any]]]
        # summary of cond_EVENT, duration_TIMED_STATE enter_STATE and exit_STATE methods
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
    def _check_state(cls, state: str) -> None:
        if state not in cls._ct_states:
            raise ValueError(f"FSM state '{state}' is unknown (missing in ALL_STATES)")

    @classmethod
    def _add_transition(cls, event: str, state: str|None, next_state: str|None) -> None:
        if state is None and next_state is None and redzed.get_debug_level() >= 2:
            _logger.warning("Useless transition rule: [%s, ..., None]", event)
        key = (event, state)
        if key in cls._ct_transition:
            state_msg = "..." if state is None else state
            raise ValueError(f"Multiple transitions rules ['{event}', {state_msg}, ???]")
        cls._ct_transition[key] = next_state

    @classmethod
    def _build_tables(cls) -> None:
        """
        Build control tables from ALL_STATES, TIMED_STATES and EVENTS.

        Control tables must be created for each subclass. The original
        tables are left unchanged. All control tables are class
        variables and have the '_ct_' prefix.
        """
        # states
        if not is_multiple(cls.ALL_STATES) or not cls.ALL_STATES:
            raise ValueError("ALL_STATES: Expecting non-empty sequence of names")
        for state in cls.ALL_STATES:
            check_identifier(state, "FSM state name")
        cls._ct_states = set(cls.ALL_STATES)
        cls._ct_default_state = cls.ALL_STATES[0]
        # timed states
        cls._ct_duration = {}
        cls._ct_timed_states = {}
        for state, duration, next_state in cls.TIMED_STATES:
            cls._check_state(state)
            cls._check_state(next_state)
            if state in cls._ct_timed_states:
                raise ValueError(f"TIMED_STATES: Multiple rules for timed state '{state}'")
            if duration is not None:
                try:
                    cls._ct_duration[state] = time_period(duration, zero_ok=True)
                except (ValueError, TypeError) as err:
                    raise ValueError(
                        f"TIMED_STATES: could not convert duration of state '{state}' "
                        + f"to seconds: {err}") from None
            cls._ct_timed_states[state] = next_state

        # events and state transitions
        cls._ct_transition = {}
        cls._ct_events = set()
        for event, from_states, next_state in cls.EVENTS:
            check_identifier(event, "FSM event name")
            if event in cls._edt_handlers:
                raise ValueError(
                    f"Ambiguous event '{event}': "
                    + "the name is used for both FSM and Block event")
            cls._ct_events.add(event)
            if next_state is not None:
                cls._check_state(next_state)
            if from_states is ...:
                # The ellipsis means any state. In control tables we are using None instead
                cls._add_transition(event, None, next_state)
            else:
                if not is_multiple(from_states):
                    exc = ValueError(
                        "Expected is a literal ellipsis (...) or a sequence of states, "
                        + f"got {from_states!r}")
                    exc.add_note(
                        f"Problem was found in the transition rule for event '{event}'")
                    if from_states in cls._ct_states:
                        exc.add_note(f"Did you mean: ['{from_states}'] ?")
                    raise exc
                for fstate in from_states:
                    cls._check_state(fstate)
                    cls._add_transition(event, fstate, next_state)

        # helper table: name 'prefix_suffix' is valid if prefix is a dict key
        # and suffix is listed in the corresponding dict value
        cls._ct_valid_names = {
            'cond': cls._ct_events,
            'duration': cls._ct_timed_states,
            'enter': cls._ct_states,
            'exit': cls._ct_states,
            't': cls._ct_timed_states,
        }

        # class hooks
        cls._ct_methods = {
            'cond': {},             # data format: {EVENT: cond_EVENT method}
            'duration': {},         # data format: {TIMED_STATE: duration_TIMED_STATE method}
            'enter': {},            # {STATE: enter_STATE method}
            'exit': {},             # {STATE: exit_STATE method}
            }
        for method_name, method in inspect.getmembers(cls):
            if method_name.startswith('_') or not callable(method):
                continue
            try:
                # ValueError in assignment if split into two pieces fails:
                hook_type, name = method_name.split('_', 1)
                hook_dict = cls._ct_methods[hook_type]
            except (ValueError, KeyError):
                continue
            if name in cls._ct_valid_names[hook_type]:
                hook_dict[name] = method
            elif redzed.get_debug_level() >= 2:
                _logger.warning(
                    "Method .%s() was not accepted by the FSM. "
                    "Check the name '%s' if necessary",
                    method_name, name)

    def __init_subclass__(cls, *args, **kwargs) -> None:
        """Build control tables."""
        # call super().__init_subclass__ first, we will then check for possible
        # event name clashes with the Block._edt_handlers
        super().__init_subclass__(*args, **kwargs)
        try:
            cls._build_tables()
        except Exception as err:
            err.add_note(
                f"Error occurred in FSM '{cls.__name__}' during validation of control tables")
            raise

    def __init__(self, *args, **kwargs) -> None:
        """
        Create FSM.

        Handle keyword arguments named t_TIMED_STATE, cond_EVENT,
        enter_STATE and exit_STATE.
        """
        if type(self) is FSM:   # pylint: disable=unidiomatic-typecheck
            raise TypeError("Can't instantiate abstract FSM class")
        prefixed: dict[str, list[tuple[str, t.Any]]] = {
            'cond': [],
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
                names_msg = ', '.join(f"'{hook_type}_{n}'" for n in valid_names)
                err.add_note(f"Valid are: {names_msg}")
                raise err
        # extra arguments are now removed from kwargs -> can call super().__init__
        super().__init__(*args, **kwargs)

        self._t_duration: dict[str, float] = {}   # values passed as t_TIMED_STATE=duration
        for state, value in prefixed['t']:
            if (duration := time_period(value, passthrough=None, zero_ok=True)) is not None:
                self._t_duration[state] = duration
        self._instance_hooks = {
            hook_type: {name: to_tuple(value) for name, value in prefixed[hook_type]}
            for hook_type in ['cond', 'enter', 'exit']}

        self._state: str|redzed.UndefType = redzed.UNDEF      # storage for FSM state
        self.sdata: dict[str, t.Any] = {}         # storage for additional internal state data
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

    @property
    def state(self) -> str|redzed.UndefType:
        """Return the FSM state (string) or UNDEF if not initialized."""
        return self._state

    def rz_export_state(self) -> tuple[str, float|None, dict[str, t.Any]]:
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
        assert self._state is redzed.UNDEF     # this is the very first init function
        state, timestamp, sdata = internal_state
        self._check_state(state)
        if timestamp is not None:
            if state not in self._ct_timed_states:
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

    def rz_init(self, init_value: str, /) -> None:
        """Set the initial FSM state."""
        # Do not call self.event() for initialization.
        # It would try to initialize before processing the event.
        self._check_state(init_value)
        self.log_debug1("initial state: %s", init_value)
        self._state = init_value
        self._set_output(self._state)

    def rz_init_default(self) -> None:
        """Initialize the internal state."""
        self.rz_init(self._ct_default_state)

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
                self._set_timer(remaining, self._ct_timed_states[self._state])
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

    def _start_timer(
            self, edata_duration: float|str|None, following_state: str) -> None:
        """Start the timer before enterint the following_state."""
        state = self._state
        assert state is not redzed.UNDEF   # starting a timer implies a timed state
        duration = time_period(edata_duration, passthrough=None, zero_ok=True)
        if duration is None:
            duration = self._run_hooks('duration', state)
        if duration is None:
            duration = self._t_duration.get(state)
        if duration is None:
            duration = type(self)._ct_duration.get(state)
        if duration is None:    # not found or explicitly set to None
            raise RuntimeError(f"Timer duration for state '{state}' not set")
        if duration == float('inf'):
            return
        self._set_timer(duration, following_state)

    def _stop_timer(self) -> None:
        """Stop the timer, if any."""
        if (timer := self._active_timer) is not None:
            if not timer.cancelled():
                timer.cancel()
                # do not rely on the existence of the private attribute '_scheduled'
                if getattr(timer, '_scheduled', True):
                    self.log_debug2("timer: cancelled")
            self._active_timer = None

    def _yield_hooks(
            self, hook_type: t.Literal['cond', 'duration', 'enter', 'exit'], name: str
            ) -> t.Iterator[Callable[[], t.Any]|Callable[[Mapping[str, t.Any]], t.Any]]:
        """
        Yield all hooks of given type for given state/event.
        """
        try:
            hook = self._ct_methods[hook_type][name]
        except KeyError:
            pass
        else:
            # class_hook is an unbound method -> bind self
            # pylint: disable-next=unnecessary-dunder-call
            yield hook.__get__(self, type(self))
        try:
            hooks = self._instance_hooks[hook_type][name]
        except KeyError:
            pass
        else:
            yield from hooks

    @t.overload
    def _run_hooks(self, hook_type: t.Literal['cond'], name: str) -> bool: ...
        # Return the logical conjunction of return values using short-circuit evaluation
    @t.overload
    def _run_hooks(self, hook_type: t.Literal['duration'], name: str) -> float|None: ...
        # There are no 'duration' instance hooks. Return the result of the class hook or None
    @t.overload
    def _run_hooks(self, hook_type: t.Literal['enter', 'exit'], name: str) -> list[t.Any]: ...
        # Return individual values (they are currently ignored).
    def _run_hooks(
            self, hook_type: t.Literal['cond', 'duration', 'enter', 'exit'], name: str
            ) -> bool|float|None|list[t.Any]:
        """Run hooks 'cond', 'duration', 'enter' or 'exit'."""
        called = False
        retvals = []
        for hook in self._yield_hooks(hook_type, name):
            if not called:
                self.log_debug2("Calling hooks '%s_%s'", hook_type, name)
                called = True
            assert self._edata is not None  # @mypy
            rv = hook() if _hook_args(hook) == 0 else hook(self._edata) # type: ignore[call-arg]
            retvals.append(rv)
            if not rv and hook_type == 'cond':
                break
        if not called:
            self.log_debug2("No '%s_%s' hooks found", hook_type, name)
        if hook_type == 'cond':
            return not retvals or bool(retvals[-1])
        if hook_type == 'duration':
            assert len(retvals) <= 1
            return time_period(retvals[0], passthrough=None, zero_ok=True) if retvals else None
        return retvals

    def _event__get_config(self, _edata: redzed.EventData) -> dict[str, t.Any]:
        """Debugging aid '_get_config'."""
        cls = type(self)
        # pylint: disable=protected-access
        return {
            'durations': cls._ct_duration | self._t_duration,
            'events': cls._ct_events,
            'states': cls._ct_states,
            'timed_transitions': cls._ct_timed_states,
            'transitions': cls._ct_transition,
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
        next_state: str|None
        if etype.startswith("Goto:"):
            next_state = etype[5:]      # strip "Goto:" prefix
            self._check_state(next_state)
        elif etype.startswith("Start:"):
            next_state = etype[6:]      # strip prefix
            if next_state != self._state:
                raise RuntimeError("Event 'Start:STATE' was used incorrectly")
            start_event = True
        else:
            if etype not in self._ct_events:
                raise redzed.UnknownEvent("Unknown event type")
            # not using .get(key) because None and not found are different cases
            key: tuple[str, str|None]
            if (key := (etype, self._state)) not in self._ct_transition:
                key = (etype, None)
            next_state = self._ct_transition.get(key)
            if next_state is None:
                self.log_debug2(
                    "No transition defined for event '%s' in state '%s'", etype, self._state)
                return False
            if not start_event and not self._run_hooks('cond', etype):
                self.log_debug2(
                    "event '%s' (%s -> %s) was rejected by cond_%s",
                    etype, self._state, next_state, etype)
                return False

        if not start_event:
            self._run_hooks('exit', self._state)
            self._stop_timer()
            self.log_debug1("state: %s -> %s (event: %s)", self._state, next_state, etype)
        self._state = next_state
        self._set_output(self._state)
        if (following_state := self._ct_timed_states.get(self._state)) is not None:
            assert self._edata is not None  # @mypy
            self._start_timer(self._edata.get('duration'), following_state)
        self._run_hooks('enter', self._state)
        return True

    def _default_event_handler(self, etype: str, edata: redzed.EventData) -> bool:
        """
        Wrapper creating a separate context.

        Refer to _fsm_event_handler().
        """
        if self._state is redzed.UNDEF:
            raise RuntimeError(f"{self}: Received event '{etype}' before initialization")
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

    def _send_synthetic_event(self, etype: str, edata: redzed.EventData|None = None) -> None:
        """
        Send an synthetic event (implementation detail).

        To protect the FSM, the used event names are not
        accepted by the .event() entry point.
        """
        if edata:
            self.log_debug2("Synthetic event '%s', edata: %s", etype, edata)
        else:
            self.log_debug2("Synthetic event '%s'", etype)
        # we muss bypass .event()
        self._default_event_handler(etype, {} if edata is None else edata)

    def _goto(self, state: str) -> None:
        """Unconditionally go to 'state'. To be used by the FSM itself only!"""
        self._send_synthetic_event(f"Goto:{state}")
        if self.rz_persistence & redzed.PersistenceFlags.EVENT:
            self.circuit.save_persistent_state(self)

    def _start_now(self, state: str) -> None:
        """Start after initialization. To be used by the FSM itself only!"""
        self._send_synthetic_event(f"Start:{state}")
