"""
Formulas and Triggers.
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Project home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

__all__ = ['Formula', 'formula', 'Trigger', 'triggered']

from collections.abc import Callable
import inspect
import logging
import typing as t

from . import base_block
from . import block
from . import circuit
from .debug import get_debug_level
from .undef import UNDEF
from .utils import func_call_string

_logger = logging.getLogger(__package__)


class _ExtFunction:
    """
    Manage calls to a function associated with a Trigger or a Formula.
    """

    def __init__(self, func: Callable[..., t.Any], owner: Formula|Trigger) -> None:
        """Check if the function's signature is compatible."""
        self._owner = owner
        self._func = func
        self._parameters: list[str] = []
        self._inputs: list[str|block.Block|Formula] = []
            # names (strings) must be resolved to objects before start
        arglist = []
        Param = inspect.Parameter
        try:
            for name, param in inspect.signature(func).parameters.items():
                # support of positional-only arguments is possible,
                # but the benefit would be minimal
                if param.kind not in [Param.POSITIONAL_OR_KEYWORD, Param.KEYWORD_ONLY]:
                    raise ValueError(
                        "Function takes *args or **kwargs or positional-only arguments")
                self._parameters.append(name)
                if (default := param.default) is Param.empty:
                    self._inputs.append(name)
                    arglist.append(name)
                else:
                    self._inputs.append(default)
                    if isinstance(default, str):
                        arglist.append(f"{name}='{default}'")
                    elif isinstance(default, (block.Block, Formula)):
                        arglist.append(f"{name}='{default.name}'")
                    else:
                        raise ValueError(
                            f"The default value in '{name}={default!r}' "
                            + "does not specify a circuit block")
            if not arglist:
                raise ValueError("Function does take any arguments")
        except ValueError as inspect_error:
            # Re-raise with more descriptive message and with the original message as a note.
            # The owner is not initialized yet, so do not try to print e.g. its name.
            exc = ValueError(f"{owner.type_name} cannot accept function {func.__qualname__}()")
            exc.add_note(inspect_error.args[0])
            raise exc from None
        self.signature = f"{self._func.__name__}({', '.join(arglist)})"

    def resolve_names(self) -> list[block.Block|Formula]:
        """Resolve names to block or formula objects."""
        resolve_name = self._owner.circuit.resolve_name
        self._inputs = [resolve_name(ref) for ref in self._inputs]
        return t.cast(list[block.Block|Formula], self._inputs)

    def run_function(self) -> t.Any:
        """Run with output values of referenced blocks."""
        # union-attr: after pre-init the _inputs does not contain strings
        kwargs = dict(zip(
            self._parameters,
            (blk.get() for blk in self._inputs),    # type: ignore[union-attr]
            strict=True))
        if UNDEF in kwargs.values():
            assert self._owner.circuit.get_state() < circuit.CircuitState.RUNNING
            if get_debug_level() >= 2:
                undef = next(iter(param for param, value in kwargs.items() if value is UNDEF))
                _logger.debug(
                    "%s: NOT calling the function, because '%s' is UNDEF", self._owner, undef)
            return UNDEF
        if get_debug_level() >= 1:
            _logger.debug(
                "%s: Calling %s", self._owner, func_call_string(self._func, (), kwargs))
        try:
            return self._func(**kwargs)
        except Exception as err:
            err.add_note(f"Failed function call originated from {self._owner}")
            self._owner.circuit.abort(err)
            raise


# Triggers do not have a name nor an output.
@t.final
class Trigger:
    """
    A circuit item monitoring output changes of selected blocks.
    """
    def __init__(self, func: Callable[..., t.Any]) -> None:
        self._ext_func = _ExtFunction(func, owner=self)
        self._str = f"<{self.type_name} for {self._ext_func.signature}>"
        self.circuit = circuit.get_circuit()
        self.circuit.rz_add_item(self)
        self._enabled = False

    def __str__(self) -> str:
        return self._str

    # for compatibility with Blocks and Formulas
    @property
    def type_name(self) -> str:
        return type(self).__name__

    def rz_pre_init(self) -> None:
        for inp in self._ext_func.resolve_names():
            inp.rz_add_trigger(self)

    def run(self) -> None:
        if self._enabled:
            self._ext_func.run_function()

    def rz_start(self) -> None:
        self._enabled = True
        self.run()

    def rz_stop(self) -> None:
        self._enabled = False


_FUNC = t.TypeVar("_FUNC", bound=Callable[..., t.Any])
def triggered(func: _FUNC) -> _FUNC:
    """
    @triggered adds a trigger to a function.

    The function *func* itself it not changed.

    All parameters of the decorated function refer to blocks with
    the same name. When the output of any of those block changes
    and none of them is UNDEF, the function will be called
    with corresponding output values passed as arguments.
    """
    Trigger(func)
    return func


@t.final
class Formula(base_block.BlockOrFormula):
    """
    A block with its output computed from other blocks` outputs.

    The output is computed on demand with a provided function.
    The function should be a pure function, i.e. without side effects.

    The most convenient way to create a Formula block is the
    @formula decorator.
    """
    def __init__(self, *args, func: Callable[..., t.Any], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ext_func = _ExtFunction(func, self)
        self._evaluate_active = False

    def rz_pre_init(self) -> None:
        for inp in self._ext_func.resolve_names():
            inp.rz_add_formula(self)

    def rz_start(self) -> None:
        self.evaluate()

    def evaluate(self) -> set[Trigger]:
        """
        Evaluate this formula and dependent formulas.

        Return a set of affected triggers.
        """
        if self._evaluate_active:
            raise RuntimeError(f"{self}: detected a dependency loop")
        result = self._ext_func.run_function()
        if result is UNDEF or not self._set_output(result):
            return set()
        triggers = self._dependent_triggers.copy()
        self._evaluate_active = True
        for frm in self._dependent_formulas:
            triggers |= frm.evaluate()
        self._evaluate_active = False
        return triggers

def formula(name: str, *args, **kwargs) -> Callable[[_FUNC], _FUNC]:
    """@formula() creates a Formula block with the decorated function."""
    if 'func' in kwargs:
        # Argument func=... will be supplied by us
        raise TypeError("@formula() got an unexpected keyword argument 'func='")
    def decorator(func: _FUNC) -> _FUNC:
        Formula(name, *args, func=func, **kwargs)
        return func
    return decorator
