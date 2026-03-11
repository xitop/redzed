"""
Logic Blocks.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Project home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['Block', 'CircuitShutDown', 'EventData', 'UnknownEvent']

import asyncio
from collections.abc import Callable
import logging
import typing as t

from .base_block import BlockOrFormula

from .debug import get_debug_level
from . import initializers
from .undef import UNDEF
from .utils import check_identifier, is_multiple, time_period

_logger = logging.getLogger(__package__)
_DEFAULT_STOP_TIMEOUT = 10.0


EventData: t.TypeAlias = dict[str, t.Any]


class UnknownEvent(Exception):
    """Event type not supported."""


class CircuitShutDown(RuntimeError):
    """Cannot perform an action after shutdown."""


_INIT_TYPES = (initializers.SyncInitializer, initializers.AsyncInitializer)


class Block(BlockOrFormula):
    """
    A circuit block maintaining its own state.

    Logic blocks accept events and modify their state in response
    to them. They have one output depending solely on the state.
    """

    _edt_handlers: dict[str, Callable[[t.Self, EventData], object]]
                                # event handling methods _event_NAME
    RZ_PERSISTENCE: bool        # class attr: is persistent state supported?


    def __init_subclass__(cls, *args, **kwargs) -> None:
        """
        Create event dispatch table (edt) of all specialized event handlers.

        Add flag if persistent state is supported.
        """
        super().__init_subclass__(*args, **kwargs)
        cls._edt_handlers = {}
        for mro in cls.__mro__:
            if issubclass(mro, Block):
                for mname, method in vars(mro).items():
                    if not callable(method):
                        continue    # it's a plain attr
                    # When multiple handlers exist, save only the first one, because it has
                    # the highest rank in the MRO hierarchy.
                    if len(mname) > 7 and mname.startswith('_event_'):
                        cls._edt_handlers.setdefault(mname[7:], method)

        cls.RZ_PERSISTENCE = (callable(getattr(cls, 'rz_export_state', None))
            and callable(getattr(cls, 'rz_restore_state', None)))

    def __init__(
            self, *args,
            initial: object = UNDEF,
            stop_timeout: float|str|None = None,
            always_trigger: bool = False,
            **kwargs
            ) -> None:
        """
        Process arguments.

        Check if given arguments are valid for the particular block type.
        """
        cls = type(self)
        if cls is Block:
            raise TypeError("Cannot instantiate the base class 'Block'")
        # remove x_arg=... and X_ARG=... from kwargs before calling super().__init__
        for key in list(kwargs):
            if key.startswith(('x_', 'X_')):
                setattr(self, key, kwargs.pop(key))
        super().__init__(*args, **kwargs)

        if initial is UNDEF:
            self.rz_initializers = []
        else:
            if not self.has_method('rz_init'):
                raise TypeError(
                    f"{self}: Keyword argument 'initial' is not supported by this block type")
            if not is_multiple(initial):
                if not isinstance(initial, _INIT_TYPES):
                    initial = initializers.InitValue(initial)
                self.rz_initializers = [initial]
            elif any(isinstance(init, _INIT_TYPES) for init in initial):
                self.rz_initializers = [
                    init if isinstance(init, _INIT_TYPES) else initializers.InitValue(init)
                    for init in initial]
            else:
                # single value which happens to be a sequence
                self.rz_initializers = [initializers.InitValue(initial)]

        restore_initializers = [
            init for init in self.rz_initializers
            if isinstance(init, initializers.PersistentState)]
        if not restore_initializers:
            self.rz_save_flags = initializers.SaveFlags(0)
        else:
            if not cls.RZ_PERSISTENCE:
                raise TypeError(
                    f"{self}: 'PersistentState' initializer is not supported "
                    + "by this block type")
            if len(restore_initializers) != 1:
                raise ValueError("Multiple 'PersistentState' initializers are not allowed")
            restore = restore_initializers[0]
            if restore.rz_save_flags is not None:
                self.rz_save_flags = restore.rz_save_flags | initializers.SaveFlags.ENABLED
            else:
                # autoconfig
                if getattr(cls, 'RZ_STATE_IS_OUTPUT', False):
                    self.rz_save_flags = initializers.SaveFlags.OUTPUT
                else:
                    self.rz_save_flags = initializers.SaveFlags.EVENT
                if restore.rz_expiration is not None:
                    self.rz_save_flags |= initializers.SaveFlags.INTERVAL

        self.rz_key = f"{self.type_name}:{self.name}"

        has_astop = self.has_method('rz_astop')
        self.rz_stop_timeout: float|None
        if stop_timeout is None:
            if has_astop:
                self.log_debug2("Using default: stop_timeout=%.1f", _DEFAULT_STOP_TIMEOUT)
                self.rz_stop_timeout = _DEFAULT_STOP_TIMEOUT
            else:
                self.rz_stop_timeout = None
        else:
            if not has_astop:
                raise TypeError(
                    f"{self}: Keyword argument 'stop_timeout' "
                    + "is not supported by this block type")
            self.rz_stop_timeout = time_period(stop_timeout)
        self._etypes_active: set[str] = set()   # events in-progress, disallow event recursion
        self._always_trigger = bool(always_trigger)
        self._init_task: asyncio.Task[object]|None = None

    def rz_set_inittask(self, task: asyncio.Task[object]) -> None:
        """
        Give a reference to the task initializing this block.

        We will cancel it when the initialization is done.
        """
        self._init_task = task

    def _set_output(self, output: object) -> bool:
        """
        Set output, recalculate dependent formulas, run affected triggers.
        """
        if self._output is UNDEF and self._init_task is not None:
            if not self._init_task.done():
                self._init_task.cancel()
            self._init_task = None
        if not super()._set_output(output):
            if self._always_trigger:
                self._output_prev = output
                self.log_debug("Output: %r (same as before)", output)
            else:
                return False
        if self.rz_save_flags & initializers.SaveFlags.OUTPUT:
            self.circuit.save_persistent_state(self)
        triggers = self._dependent_triggers.copy()
        for frm in self._dependent_formulas:
            triggers |= frm.evaluate()
        for trg in triggers:
            trg.run()
        return True

    def rz_init_default(self) -> None:
        """
        Set output to None for blocks that do not have init functions.

        It is assumed that such blocks do not use their output.
        """
        if not self.is_initialized() and not self.has_method('rz_init'):
            self._set_output(None)

    def _default_event_handler(self, etype: str, edata: EventData) -> object:
        """Default event handler."""
        raise UnknownEvent(f"{self}: Unknown event type {etype!r}")

    # note the double underscore: _event_ + _get...
    def _event__get_info(self, _edata: EventData) -> dict[str, object]:
        """Handle '_get_info' monitoring event."""
        info: dict[str, object] = {
            'name': self.name, 'comment': self.comment, 'type': self.type_name
            }
        cur, prev = self.get(with_previous=True)
        if cur is not UNDEF:
            info['output'] = cur
        if prev is not UNDEF:
            info['previous'] = prev
        return info

    def _event__get_state(self, _edata: EventData) -> object:
        """Handle '_get_state' monitoring event."""
        if not self.has_method('rz_export_state'):
            raise UnknownEvent(f"{self.type_name} blocks do not support this event")
        if not self.is_initialized():
            raise RuntimeError("Not initialized yet")
        # pylint: disable-next=no-member
        return self.rz_export_state()         # type: ignore[attr-defined]

    def rz_is_shut_down(self) -> bool:
        return self.circuit.is_shut_down()

    def event(self, etype: str, /, evalue: object = UNDEF, **edata: object) -> object:
        """
        An entry point for events.

        Call the specialized _event_ETYPE() method if it exists.
        Otherwise call the _default_event_handler() as the last resort.
        """
        check_identifier(etype, "Event type")
        if (not_monitoring := not etype.startswith('_get_')) and self.rz_is_shut_down():
            raise CircuitShutDown("The circuit was shut down")

        if evalue is not UNDEF:
            edata['evalue'] = evalue

        for key in [k for k,v in edata.items() if v is UNDEF]:
            del edata[key]

        if get_debug_level() >= 1:
            if not edata:
                self.log_debug("Got event '%s'", etype)
            elif len(edata) == 1 and 'evalue' in edata:
                self.log_debug("Got event '%s', evalue: %r", etype, edata['evalue'])
            else:
                self.log_debug("Got event '%s', edata: %s", etype, edata)
        if etype in self._etypes_active:
            # we must report the error both to the caller and to the runner
            exc = RuntimeError(
                f"{self}: Event '{etype}' generated another event of the same type")
            self.circuit.abort(exc)
            raise exc
        self._etypes_active.add(etype)
        try:
            if not self.is_initialized() and not_monitoring:
                # We will allow the event, because:
                #   - some blocks need an event for their initialization
                #   - this event could have arrived during initialization by chance or race
                self.log_debug2("Pending event, initializing now")
                self.circuit.init_block_sync(self)
            handler = type(self)._edt_handlers.get(etype)
            try:
                if handler:
                    # handler is an unbound method => must add 'self'
                    retval = handler(self, edata)
                else:
                    retval = self._default_event_handler(etype, edata)
            except UnknownEvent:
                self.log_debug1("Unknown event error raised")
                raise
            except Exception as err:
                err.add_note(f"Error occurred in {self} during handling of event '{etype}'; "
                    + f"event data was: {edata if edata else '<EMPTY>'}")
                if isinstance(err, KeyError) and err.args[0] == 'evalue':
                    err.add_note("A required event value is almost certainly missing")
                raise
            if (self.rz_save_flags & initializers.SaveFlags.EVENT
                    and not_monitoring and self.is_initialized()):
                self.circuit.save_persistent_state(self)
            self.log_debug2("Event '%s' returned: %r", etype, retval)
            return retval
        finally:
            self._etypes_active.remove(etype)
