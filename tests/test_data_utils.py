"""
Test internal utilities.
"""

import pytest

import redzed


def test_func_call_string():
    """Test the _args_as_string helper."""
    def test(func, *args, **kwargs):
        return redzed.utils.func_call_string(func, args, kwargs)

    assert test(None, ) == "()"
    assert test(sum, -1, "arg") == "sum(-1, 'arg')"
    assert test(print, f=False, t=True, n=[1, 2]) == "print(f=False, t=True, n=[1, 2])"
    assert test(None, 1, 2, None, a = 1, b = 'xy') == "(1, 2, None, a=1, b='xy')"


def test_func_name():
    """Test func_name."""
    func_name = redzed.utils.func_name

    class NcCs:
        """NOT callable class"""

    class ClCs:
        """Callable class"""
        def __call__(self):
            pass

    for nc in [0, "text", NcCs()]:
        with pytest.raises(TypeError, match="not callable"):
            func_name(nc)
    assert func_name(NcCs) == "NcCs"
    assert func_name(ClCs()) == "ClCs.__call__"


def test_is_multiple_and_to_tuple():
    """Check _is_multiple() and _to_tuple() helpers."""
    is_multiple = redzed.utils.is_multiple
    to_tuple = redzed.utils.to_tuple

    # set and str belong here, see the docs
    NOT_MULTI_VALUES = (None, 'name', b'bytestring', 10, {'a', 'b', 'c'}, set(), True, print)
    for arg in NOT_MULTI_VALUES:
        assert not is_multiple(arg)
        assert to_tuple(arg) == (arg,)

    MULTI_VALUES = ((1, 2, 3), [0], (), [])
    for arg in MULTI_VALUES:
        assert is_multiple(arg)
        assert to_tuple(arg) == tuple(arg)
