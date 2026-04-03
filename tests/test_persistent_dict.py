"""
Test PersistentDict.
"""

import json
import logging
import random
import pickle

import pytest

import redzed


@pytest.mark.parametrize('file_format', ['json', 'pickle', 'pkl'])
def test_file_format(tmp_path, file_format):
    """Test file format guess from filename suffix."""
    TEST_DATA = {'key1': [random.randint(0, 999_999)]}
    path = tmp_path / f'infile.{file_format}'
    if file_format == 'pkl':
        file_format = 'pickle'  # pkl is recognized only as a suffix
    if file_format == 'json':
        path.write_text(json.dumps(TEST_DATA), encoding="utf-8")
    else:
        path.write_bytes(pickle.dumps(TEST_DATA))
    # sync_time > 0 would require asyncio
    pdata = redzed.utils.PersistentDict(path, sync_time=0)
    assert pdata == TEST_DATA
    pdata['new'] = 123
    # pdata.flush not necessary with sync_time=0
    del pdata

    path = path.replace(tmp_path / 'infile.dat')
    with pytest.raises(ValueError, match="either 'json' or 'pickle'"):
        redzed.utils.PersistentDict(path, sync_time=0)
    pdata2 = redzed.utils.PersistentDict(path, sync_time=0, format=file_format)
    assert pdata2.pop('new') == 123
    assert pdata2 == TEST_DATA
    path.unlink()


def test_empty_file_OK(tmp_path):
    """An empty file is always accepted."""
    path = tmp_path / 'emptyfile.dat'
    path.touch(exist_ok=False)
    pdata1 = redzed.utils.PersistentDict(path, sync_time=0, format='json')
    assert not pdata1
    del pdata1
    assert path.stat().st_size == 0
    pdata2 = redzed.utils.PersistentDict(path, sync_time=0, format='pickle')
    assert not pdata2
    path.unlink()


def test_damaged_file(tmp_path, caplog):
    """Test garbage datafile."""
    caplog.set_level(logging.INFO)
    TEST_DATA = {'key2': [random.randint(0, 999_999)]}
    errlog = []

    def log_err(exc):
        errlog.append(type(exc))

    path = tmp_path / 'broken.json'
    path.write_text("123?ABC")
    pdata1 = redzed.utils.PersistentDict(path, sync_time=0, error_callback=log_err)
    pdata1.update(TEST_DATA)
    del pdata1

    assert len(errlog) == 1
    assert issubclass(errlog[0], json.JSONDecodeError)
    errlog.clear()
    mlog = caplog.messages
    assert len(mlog) == 2
    assert "Error loading data from " in mlog[0]
    assert "Offending PersistentDict file renamed to " in mlog[1]
    caplog.clear()

    pdata2 = redzed.utils.PersistentDict(path, sync_time=0, error_callback=log_err)
    assert pdata2 == TEST_DATA
    assert not errlog
    assert not caplog.messages

    saved = next(iter(path.parent.glob("broken.json.????????_??????~")))
    saved.unlink()


def test_absolute_path():
    """Test the filename check"""
    with pytest.raises(ValueError, match="absolute path"):
        redzed.utils.PersistentDict("./rela/tive/path", format="json")


async def test_callback(circuit):
    """Test the error callback."""
    storage = redzed.utils.PersistentDict(
        "/the.quick.brown.fox/jumps/over/the.lazy.dog",
        format="json", error_callback=circuit.abort)
    with pytest.raises(RuntimeError, match="closed"):
        circuit.set_persistent_storage(storage, close_callback=storage.flush)
    errors = circuit.get_errors()
    assert len(errors) == 1
    assert isinstance(errors[0], FileNotFoundError)


def test_missing_dir(tmp_path, caplog):
    """Test missing directory."""
    caplog.set_level(logging.WARNING)
    errlog = []

    def log_err(exc):
        errlog.append(type(exc))

    path = tmp_path / 'missing' / 'file.json'
    pdata1 = redzed.utils.PersistentDict(path, sync_time=0, error_callback=log_err)
    pdata1.update({'any_key': 0})
    mlog = caplog.messages
    assert len(mlog) == 2
    assert " is missing" in mlog[0]
    assert "Could not create a temporary file " in mlog[1]

    assert len(errlog) == 2
    # missing datafile + missing dir for tmp file
    assert errlog[0] == errlog[1] == FileNotFoundError
