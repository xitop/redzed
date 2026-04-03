"""
Test the debug level.
"""

import logging
import os
from unittest import mock

import redzed


def test_debug_level_envvar(caplog):
    """test REDZED_DEBUG env variable"""
    caplog.set_level(logging.WARNING)
    for env_lvl in range(-2, 6):
        with mock.patch.dict(os.environ, values=[('REDZED_DEBUG', str(env_lvl))]):
            rz_lvl = redzed.debug.get_level_from_env()
        assert rz_lvl == (env_lvl if 0 <= env_lvl <= 3 else None)
    assert len(caplog.messages) == 8   # 1 warning + 1 error for each error

    caplog.clear()
    for env_str in ["on", "off", ""]:
        with mock.patch.dict(os.environ, values=[('REDZED_DEBUG', env_str)]):
            assert redzed.debug.get_level_from_env() is None
    assert len(caplog.messages) == 4   # empty string is silently ignored
