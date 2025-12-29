"""
Check version numbers.
"""

import warnings

import redzed

def test_version():
    version = redzed.__version__
    version_info = redzed.__version_info__
    assert isinstance(version, str)
    assert isinstance(version_info, tuple)
    if 'NEXT' in version:
        warnings.warn("version not set")
        return
    y, m, d = version_info
    assert y >= 25 and 1 <= m <= 12 and 1 <= d <= 31
