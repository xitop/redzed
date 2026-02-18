"""
Base class of logic Blocks and Formulas.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Project home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

import inspect
import logging
import textwrap
import typing as t

from . import circuit
from .debug import get_debug_level
from .undef import UNDEF
from .utils import check_identifier

_logger = logging.getLogger(__package__)


class BlockOrFormula:
    """
    The common part of a logic Block or Formula.

    Check the name and register the new item.
    """

    def __init__(self, name: str, *, comment: str = "") -> None:
        """Create new circuit component. Add it to the circuit."""
        # These are the only two allowed concrete subsclasses
        if not isinstance(self, (block.Block, formula_trigger.Formula)):
            raise TypeError("Cannot instantiate an abstract class")
        self.circuit = circuit.get_circuit()
        check_identifier(name, "Block/Formula name")
        if name.startswith('_') and not getattr(type(self), 'RZ_RESERVED', False):
            raise ValueError(f"Name '{name}' is reserved (starting with an underscore)")
            # reserved blocks cannot be created by simple mistake,
            # because types of reserved blocks (e.g. Cron) are not public
        self.name = name
        self.comment = str(comment)
        self._str_cached: str|None = None   # cache for __str__ value
        self.circuit.rz_add_item(self)
        self._dependent_formulas: set[formula_trigger.Formula] = set()
        self._dependent_triggers: set[formula_trigger.Trigger] = set()
        self._output = self._output_prev = UNDEF

    @property
    def type_name(self) -> str:
        return type(self).__name__

    def has_method(self, method_name: str, async_method: bool = False) -> bool:
        if not callable(method := getattr(self, method_name, None)):
            return False
        if async_method and not inspect.iscoroutinefunction(method):
            return False
        return True

    def rz_add_formula(self, formula: formula_trigger.Formula) -> None:
        """Add a formula block depending on our output value."""
        self._dependent_formulas.add(formula)

    def rz_add_trigger(self, trigger: formula_trigger.Trigger) -> None:
        """Add a trigger block depending on our output value."""
        self._dependent_triggers.add(trigger)

    def _set_output(self, output: t.Any) -> bool:
        """Set output."""
        if output is UNDEF:
            raise ValueError(f"{self}: Cannot set output to <UNDEF>.")
        if output == self._output:
            return False
        self._output_prev, self._output = self._output, output
        if get_debug_level() >= 1:
            self.log_debug("Output: %r -> %r", self._output_prev, output)
        return True

    def get(self) -> t.Any:
        return self._output

    def get_previous(self) -> t.Any:
        return self._output_prev

    def is_initialized(self) -> bool:
        return self._output is not UNDEF

    def log_msg(self, msg: str, *args: t.Any, level: int, **kwargs: t.Any) -> None:
        """Add own name and log the message with given severity level."""
        _logger.log(level, f"{self} {msg}", *args, **kwargs)

    def log_debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with DEBUG severity."""
        self.log_msg(msg, *args, level=logging.DEBUG, **kwargs)

    def log_debug1(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message if debugging is enabled."""
        if get_debug_level() >= 1:
            self.log_msg(msg, *args, level=logging.DEBUG, **kwargs)

    def log_debug2(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message if verbose debugging is enabled."""
        if get_debug_level() >= 2:
            self.log_msg(msg, *args, level=logging.DEBUG, **kwargs)

    def log_info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with _INFO_ severity."""
        self.log_msg(msg, *args, level=logging.INFO, **kwargs)

    def log_warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with _WARNING_ severity."""
        self.log_msg(msg, *args, level=logging.WARNING, **kwargs)

    def log_error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log a message with _ERROR_ severity."""
        self.log_msg(msg, *args, level=logging.ERROR, **kwargs)

    def __str__(self) -> str:
        if self._str_cached is not None:
            return self._str_cached
        if not hasattr(self, 'name'):
            # a subclass did not call super().__init__(name, ...) yet
            return f"<{self.type_name} N/A id={hex(id(self))}>"
        parts = [self.type_name, self.name]
        if self.comment:
            short_comment = textwrap.shorten(self.comment, width=40, placeholder="...")
            parts.append(f"comment='{short_comment}'")
        self._str_cached = f"<{' '.join(parts)}>"
        return self._str_cached

# Importing at the end resolves a circular import issue.
# formula_trigger.Formula and block.Block are subclasses of BlockOrFormula defined here.
# pylint: disable=wrong-import-position
from . import formula_trigger
from . import block
