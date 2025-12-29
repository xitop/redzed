"""
Test basic circuit block related functionality.
"""

# pylint: disable=unused-argument

import pytest

import redzed


class Noop(redzed.Block):
    """A dummy block for testing."""


def test_undef():
    """Check UNDEF."""
    undef = redzed.UNDEF
    assert bool(undef) is False
    assert str(undef) == repr(undef) == '<UNDEF>'
    # pylint: disable-next=unidiomatic-typecheck
    assert type(undef) is redzed.UndefType
    # pylint: disable-next=no-value-for-parameter
    assert redzed.UndefType() is redzed.UndefType()     # is a singleton


def test_no_dup(circuit):
    """Names must be unique."""
    Noop('dup')
    with pytest.raises(ValueError, match="Duplicate"):
        Noop('dup')


def test_invalid_names(circuit):
    """Names must be valid identifiers."""
    with pytest.raises(TypeError):
        Noop(3.14)
    with pytest.raises(TypeError):
        Noop(Noop('name'))
    with pytest.raises(ValueError, match="empty"):
        Noop('')
    with pytest.raises(ValueError, match="valid identifier"):
        Noop('0tolerance')


def test_generated_names(circuit):
    """Generated names are unused"""
    for _ in range(6):
        redzed.Memory(redzed.unique_name())
    for prefix in ("one", "two", "TH3_"):
        for _ in range(4):
            Noop(redzed.unique_name(prefix))
    assert sum(1 for x in circuit.get_items(redzed.Block)) == 6 + 3*4


def test_reserved_names(circuit):
    """All _foo style names (starting with an underscore) are reserved."""
    for name in ['_this_name_is_not_ok', '_', '__', redzed.unique_name("_auto")]:
        with pytest.raises(ValueError, match="reserved"):
            Noop(name)


def test_name_comment_str_key(circuit):
    """Test various string values."""
    blk1 = Noop('test1', comment='with comment')
    blk2 = Noop('test2')
    blk3 = redzed.Memory('test3', initial=redzed.RestoreState())
    assert blk1.name == 'test1'
    assert blk1.comment == "with comment"
    assert str(blk1) == "<Noop test1 comment='with comment'>"
    assert blk1.rz_key == "Noop:test1"

    assert blk2.name == 'test2'
    assert str(blk2) == "<Noop test2>"
    assert blk2.comment == ""
    assert blk2.rz_key == "Noop:test2"

    assert blk3.name == 'test3'
    assert str(blk3) == "<Memory test3>"
    assert blk3.comment == ""
    assert blk3.rz_key == "Memory:test3"


def test_x_attributes(circuit):
    """Test that x_name attributes are accepted and stored."""
    blk = Noop('test', x_attr1='space', X_YEAR=2001)
    # pylint: disable=no-member
    assert blk.x_attr1 == 'space'
    assert blk.X_YEAR == 2001
    # no other x_attr
    assert sum(1 for name in vars(blk) if name.startswith('x_') or name.startswith('X_')) == 2


def test_get_items_1(circuit):
    """Test get_items() and resolve_name()."""
    resolve_name = circuit.resolve_name
    get_items = circuit.get_items
    m1 = redzed.Memory('Mem1', initial=1)
    m2 = redzed.Memory('Mem2', initial=2)
    n1 = Noop('N1')
    n2 = Noop('N2')
    f1 = redzed.Formula("F1", func=lambda m1:m2)
    t1 = redzed.Trigger(lambda f1: None)
    assert resolve_name('Mem1') is resolve_name(m1) is m1
    assert resolve_name('N2') is n2
    assert resolve_name('F1') is f1
    assert set(get_items(redzed.Trigger)) == {t1}
    assert set(get_items(redzed.Formula)) == {f1}
    assert set(get_items(redzed.Memory)) == {m1, m2}
    assert set(get_items(Noop)) == {n1, n2}
    assert set(get_items(redzed.Block)) == {m1, m2, n1, n2}


def test_get_items_2(circuit):
    """Test get_items() and resolve_name()."""
    with pytest.raises(TypeError, match="circuit component type"):
        circuit.get_items(int)
    with pytest.raises(KeyError):
        circuit.resolve_name("Phantom")
    with pytest.raises(TypeError):
        circuit.resolve_name(0)
