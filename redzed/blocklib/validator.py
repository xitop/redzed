"""
Data validator
- - - - - -
Part of the redzed package.
Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""
from __future__ import annotations

from collections.abc import Callable

import redzed

class _Validate:
    """
    Add a value validator.

    To be used as a redzed.Block mix-in class.
    """

    def __init__(
            self, *args,
            validator: Callable[[object], object]|None = None,
            **kwargs) -> None:
        self._validator = validator
        super().__init__(*args, **kwargs)

# mypy: disable-error-code=attr-defined
# pylint: disable=no-member
    def _validate(self, value: object) -> object:
        """
        Return the value processed by the validator.

        Return the value unchanged if a validator was not configured.
        """
        if self._validator is None:
            return value
        try:
            validated = self._validator(value)
            if validated is redzed.UNDEF:
                raise ValueError("Validation error")
        except Exception as err:
            self.log_debug1(
                "Validator rejected value %r with %s: %s", value, type(err).__name__, err)
            err.add_note(f"Validated value was: {value!r}")
            raise

        if validated != value:
            self.log_debug2("Validator has rewritten %r -> %r", value, validated)
        return validated
