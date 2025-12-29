"""
Test time/date related utilities.
"""

import datetime as dt

import pytest

from redzed import utils


def test_tconst():
    assert utils.SEC_PER_MIN == 60
    assert utils.SEC_PER_HOUR == 60*60
    assert utils.SEC_PER_DAY == 24*60*60


def test_time_period():
    """Test time_period usage."""
    time_period = utils.time_period
    for val in [None, True, False, b"ascii", 1j]:
        assert time_period(val, passthrough=(None, bool, bytes, type(2j))) is val
    for v in (-128, -2.8):
        with pytest.raises(ValueError, match='negative'):
            time_period(v, zero_ok=False)
        with pytest.raises(ValueError, match='negative'):
            time_period(v, zero_ok=True)
    for v in (0, "0s"):
        with pytest.raises(ValueError, match='must be positive'):
            time_period(v)
        c = time_period(v, zero_ok=True)
        assert isinstance(c, float)
        assert c == 0.0
    for v in (2, 5, 33.33):
        c = time_period(v)
        assert isinstance(c, float)
        assert c == v
    for v in ("1s", "5s", "33.33s"):
        c = time_period(v)
        assert isinstance(c, float)
        assert c == float(v[:-1])
    for v in ("short", "-3s", "1"):     # "1s" would be correct
        with pytest.raises(ValueError, match='Invalid time'):   # regex not matched
            time_period(v)
    for v in ([1,2,3], ..., 1j, slice(0,1)):
        with pytest.raises(TypeError, match="Invalid type"):
            time_period(v)
    assert time_period("1h2s") == 3602.0
    assert time_period("1w3d") == utils.SEC_PER_DAY * 10
    assert time_period("2m50ms") == 120.05


def test_time_period_str():
    """Test string conversion with time_period."""
    time_period = utils.time_period
    assert isinstance(time_period('1m'), float)
    assert time_period('10500ms') == time_period('10.5s') == time_period('0m10.5s') == 10.5
    assert time_period('1.5D') == time_period('36.h') == time_period('1D720m') \
        == 36*utils.SEC_PER_HOUR
    assert time_period('P1.5D') == time_period('PT36H') == time_period('P1DT720M') \
        == 1.5*utils.SEC_PER_DAY
    assert time_period('PT10.5S') == time_period('PT10.5S') == time_period('P0DT0H10.50S') \
        == 10.5
    for duration in [
            '20h15m10s', ' 20 h 15 m 10 s', '19H75M10.000S', '20h910s',
            'P00YT20H15M10S', 'P0MT19H75M10.000S', 'PT20H910S',
            ]:
        assert time_period(duration) == 72910.0

    for duration in [
            '1d', '1.0d', '24h', '20h 240m', 'P1.0D', 'PT24H', 'P0DT86400S'
            ]:
        assert time_period(duration) == utils.SEC_PER_DAY

    for duration in [
            '', '1 0 0s', 'hello', '15m1h', '.', '0..1s', '5e-2', '0.5h0.5m', '1h1', '2',
            'P', 'PT', 'P1Y', 'P0s', 'P1M', 'PT0M0H',
            ]:
        with pytest.raises(ValueError):
            time_period(duration)


def test_fmt_period():
    """Test fmt_period."""

    fmt_period = utils.fmt_period
    with pytest.raises(ValueError):
        fmt_period(-1)
    assert fmt_period(0) == fmt_period(0.0) == '0s'
    for small in [0.000_001, 0.000_014, 0.000_149, 0.001_499]:
        assert fmt_period(small) == '1ms'      # values < 1ms are rounded up
    assert fmt_period(72910) == fmt_period(72910.0) == '20h15m10s'    # from int == from float
    assert fmt_period(60+59.9999) == '2m'      # test rounding, wrong answer is: "1m60s"
    assert fmt_period(5.0001) == '5s'
    assert fmt_period(5.0009) == '5s1ms'
    assert fmt_period(14 * utils.SEC_PER_DAY) == '2w'


def test_fmt_period_iso():
    """Test the iso8601 mode of fmt_period."""
    fmt_period = utils.fmt_period
    def fmt_iso(s):
        return fmt_period(s, iso8601=True)

    assert fmt_iso(0.1234) == 'PT0.123S'
    assert fmt_iso(0.1236) == 'PT0.124S'
    assert fmt_iso(0.5) == 'PT0.5S'
    assert fmt_iso(3.009) == 'PT3.009S'
    assert fmt_iso(3.99) == 'PT3.99S'
    assert fmt_iso(3.999) == 'PT3.999S'
    assert fmt_iso(3.9999) == 'PT4S'
    assert fmt_iso(60.01) == 'PT1M0.01S'
    assert fmt_iso(150.0) == 'PT2M30S'
    assert fmt_iso(3602) == 'PT1H0M2S'
    assert fmt_iso(2*86400+7200+660) == 'P2DT2H11M'
    assert fmt_iso(864000-43200-1799) == 'P9DT11H30M1S'
    assert fmt_iso(864000) == 'P10D'
    assert fmt_iso(864000+1799) == 'P10DT0H29M59S'
    assert fmt_iso(864000+1800) == 'P10DT0H30M'
    assert fmt_iso(8640000) == 'P100D'


def test_inverse_converions():
    """
    Test string -> float -> same string (except separators) -> equal float.
    """
    time_period = utils.time_period
    fmt_period = utils.fmt_period

    # pylint: disable=too-many-nested-blocks
    for w in (0, 99):
        for d in (3, 6):
            for h in (0, 3, 12):
                for m in (13, 59):
                    for s in (2, 45):
                        for ms in (0, 432):
                            for sep in('', '  ', '_', '@@'):
                                wu = f"{w}w" if w else ''
                                msu = f"{ms}mS" if ms else ''
                                in_str = f"{wu}{d}D{h}h{m}M{s}s{msu}"
                                duration = time_period(in_str)

                                wu = f"{w}w{sep}" if w else ''
                                msu = f"{sep}{ms}ms" if ms else ''
                                out_str = f"{wu}{d}d{sep}{h}h{sep}{m}m{sep}{s}s{msu}"
                                assert fmt_period(duration, sep=sep) == out_str
                                assert fmt_period(duration, sep=sep, upper=True) \
                                    == out_str.upper()
                                if not sep.strip():
                                    assert time_period(out_str) == duration
    for t in (0.01, 2, 300, 40_000, 5_000_000, 600_000_000):
        assert time_period(fmt_period(t)) == t


def test_timestr_approx():
    fmt_period = utils.fmt_period
    def fmt_approx(s):
        return fmt_period(s, approx=True)

    # S MMM (period < 3s)
    assert fmt_approx(0.1234) == fmt_period(0.1234) == '123ms'
    assert fmt_approx(0.1236) == fmt_period(0.1236) == '124ms'
    assert fmt_approx(0.5)    == fmt_period(0.5)    == '500ms'
    assert fmt_approx(0.9994) == fmt_period(0.9994) == '999ms'
    assert fmt_approx(0.9996) == fmt_period(0.9999) == '1s'
    assert fmt_approx(1.0)    == fmt_period(1.0)    == '1s'
    assert fmt_approx(2.009)  == fmt_period(2.009)  == '2s9ms'
    # S MM0 (3 <= period < 10s)
    assert fmt_approx(3.009) == '3s10ms'
    assert fmt_approx(3.999) == '4s'
    assert fmt_approx(9.994) == '9s990ms'
    assert fmt_approx(9.996) == '10s'
    # S M00 (10s <= period < 1m)
    assert fmt_approx(10.01) == '10s'
    assert fmt_approx(20.05) == '20s100ms'
    assert fmt_approx(30.949) == '30s900ms'
    assert fmt_approx(30.951) == '31s'
    assert fmt_approx(59.94) == '59s900ms'
    assert fmt_approx(59.95) == '1m'
    # M S (1m <= period < 1h)
    assert fmt_approx(60.01) == '1m'
    assert fmt_approx(150.0) == '2m30s'
    assert fmt_approx(3599.4) == '59m59s'
    # [D] H M (1h <= period < 3d)
    assert fmt_approx(3600.2) == '1h'
    assert fmt_approx(36000-30.0001) == '9h59m'
    assert fmt_approx(36000-29.9999) == '10h'
    assert fmt_approx(2*86400+7200+660) == '2d2h11m'
    # [W] [D] H (3d <= period)
    assert fmt_approx(3*86400+7200+660) == '3d2h'
    assert fmt_approx(864000-43200-1799) == '1w2d12h'
    assert fmt_approx(864000) == '1w3d'
    assert fmt_approx(864000+1799) == '1w3d'
    assert fmt_approx(864000+1800) == '1w3d1h'
    assert fmt_approx(8640000) == '14w2d'


def test_timestr_approx_iso8601():
    fmt_period = utils.fmt_period
    def fmt_approx_iso(s):
        return fmt_period(s, approx=True, iso8601=True)

    # S MMM (period < 3s)
    assert fmt_approx_iso(0.1234) == 'PT0.123S'
    assert fmt_approx_iso(0.1236) == 'PT0.124S'
    assert fmt_approx_iso(0.5) == 'PT0.5S'
    assert fmt_approx_iso(0.9994) == 'PT0.999S'
    assert fmt_approx_iso(0.9996) == 'PT1S'
    assert fmt_approx_iso(1.0) == 'PT1S'
    assert fmt_approx_iso(2.009) == 'PT2.009S'
    # S MM0 (3 <= period < 10s)
    assert fmt_approx_iso(3.009) == 'PT3.01S'
    assert fmt_approx_iso(3.999) == 'PT4S'
    assert fmt_approx_iso(9.994) == 'PT9.99S'
    assert fmt_approx_iso(9.996) == 'PT10S'
    # S M00 (10s <= period < 1m)
    assert fmt_approx_iso(10.01) == 'PT10S'
    assert fmt_approx_iso(20.05) == 'PT20.1S'
    assert fmt_approx_iso(30.949) == 'PT30.9S'
    assert fmt_approx_iso(30.951) == 'PT31S'
    assert fmt_approx_iso(59.94) == 'PT59.9S'
    assert fmt_approx_iso(59.95) == 'PT1M'
    # M S (1m <= period < 1h)
    assert fmt_approx_iso(60.01) == 'PT1M'
    assert fmt_approx_iso(150.0) == 'PT2M30S'
    assert fmt_approx_iso(3599.4) == 'PT59M59S'
    # [D] H M (1h <= period <3d)
    assert fmt_approx_iso(3600.2) == 'PT1H'
    assert fmt_approx_iso(36000-30.0001) == 'PT9H59M'
    assert fmt_approx_iso(36000-29.9999) == 'PT10H'
    assert fmt_approx_iso(2*86400+7200+660) == 'P2DT2H11M'
    # [W] [D] H
    assert fmt_approx_iso(3*86400+7200+660) == 'P3DT2H'
    assert fmt_approx_iso(864000-43200-1799) == 'P9DT12H'
    assert fmt_approx_iso(864000) == 'P10D'
    assert fmt_approx_iso(864000+1799) == 'P10D'
    assert fmt_approx_iso(864000+1800) == 'P10DT1H'
    assert fmt_approx_iso(8640000) == 'P100D'


def _iso_to_int7(iso):
    datetime = dt.datetime.fromisoformat(iso)
    return [*datetime.timetuple()[:6], datetime.microsecond]

def _strp_to_int7(strp):
    datetime = dt.datetime.strptime(strp, '%d/%m/%Y %H:%M:%S.%f')
    return [*datetime.timetuple()[:6], datetime.microsecond]


def test_interval():
    config1 = [[[2016,6,30,1,2,3,499_000], [2048,5,31,1,45,59,10_000]]]
    str1i = "2016-06-30T010203.4990  --  20480531T01:45:59,01"
    str1p = "30/06/2016 1:2:3.4990  --  31/5/2048 01:45:59.01"
    assert utils.parse_interval(str1i, sep="--", parser=_iso_to_int7) == \
        utils.parse_interval(str1p, sep="--", parser=_strp_to_int7) ==  config1


    config2 = [
        [[2024,3,1,12,0,0,0], [2024,3,7,18,30,1, 150_000]],
        [[2024,10,11,12,30,0,0], [2024,10,15,22,0,0,0]],
        ]
    str2i = "20240301T1200 / 20240307T183001.15; 2024-10-11T12:30 / 2024-10-15T22;"
    str2p = "1/3/2024 12:00:0.0 // 7/03/2024 18:30:01.15; " \
        + "11/10/2024 12:30:0.0 // 15/10/2024 22:0:00.0000;"
    assert utils.parse_interval(str2i, sep=["//", "/"], parser=_iso_to_int7) == \
        utils.parse_interval(str2p, sep=["//", "/"], parser=_strp_to_int7) == config2

    config3 = config1 + config2
    str3i = str1i.replace("--", "::") + "|" + str2i.replace(';', '|').replace("/", "::")
    assert utils.parse_interval(str3i, delim="|", sep="::", parser=_iso_to_int7) == config3
