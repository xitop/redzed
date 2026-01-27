"""
Data validator
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

from collections.abc import Callable
import typing as t

class _Validate:
    """
    Add a value validator.

    To be used as a redzed.Block mix-in class.
    """

    def __init__(
            self, *args,
            validator: Callable[[t.Any], t.Any]|None = None,
            **kwargs) -> None:
        self._validator = validator
        super().__init__(*args, **kwargs)

# mypy: disable-error-code=attr-defined
# pylint: disable=no-member
    def _validate(self, value: t.Any) -> t.Any:
        """
        Return the value processed by the validator.

        Return the value unchanged if a validator was not configured.
        The validator may raise to reject the value.
        """
        if self._validator is None:
            return value
        try:
            validated = self._validator(value)
        except Exception as err:
            self.log_debug1(
                "Validator rejected value %r with %s: %s", value, type(err).__name__, err)
            raise
        if validated != value:
            self.log_debug2("Validator has rewritten %r -> %r", value, validated)
        return validated
