
from datetime import datetime, timezone

import pytest

from app.repository import _parse_datetime


def test_parse_datetime_none():
    assert _parse_datetime(None) is None


def test_parse_datetime_already_datetime():
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert _parse_datetime(dt) == dt


def test_parse_datetime_iso_with_z():
    result = _parse_datetime("2024-06-01T12:00:00Z")
    assert result is not None
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 1


def test_parse_datetime_iso_with_offset():
    result = _parse_datetime("2024-06-01T12:00:00+00:00")
    assert result is not None
    assert result.year == 2024


def test_parse_datetime_naive_iso():
    result = _parse_datetime("2024-06-01T12:00:00")
    assert result is not None
    assert result.year == 2024


def test_parse_datetime_invalid_string():
    assert _parse_datetime("not-a-date") is None


def test_parse_datetime_invalid_type():
    assert _parse_datetime([1, 2, 3]) is None


def test_parse_datetime_empty_string():
    assert _parse_datetime("") is None