"""Tests for SOAP serialization and MS-AJAX date conversion."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

import pytest

from mastr_mcp.serialization import (
    convert_msajax_date,
    normalize_json_dates,
    to_jsonable,
)


# ─── MS-AJAX date conversion ───────────────────────────────────────────────


class TestConvertMsajaxDate:
    """'/Date(...)/' → ISO-8601 conversion."""

    def test_midnight_utc_gives_date_only(self):
        # 2017-09-01 00:00:00 UTC = 1504224000000ms
        assert convert_msajax_date("/Date(1504224000000)/") == "2017-09-01"

    def test_non_midnight_gives_full_iso(self):
        # 2017-09-01 12:00:00 UTC = 1504267200000ms
        result = convert_msajax_date("/Date(1504267200000)/")
        assert result.startswith("2017-09-01T")

    def test_with_timezone_offset_ignored(self):
        """The +0200 display offset is ignored — timestamp is always UTC."""
        result = convert_msajax_date("/Date(1504224000000+0200)/")
        assert result == "2017-09-01"

    def test_negative_timestamp(self):
        """Negative timestamps (before 1970) should work on Windows too."""
        # 1960-01-01 00:00:00 UTC = -315619200000ms
        result = convert_msajax_date("/Date(-315619200000)/")
        assert result == "1960-01-01"

    def test_non_matching_string_unchanged(self):
        assert convert_msajax_date("2024-01-15") == "2024-01-15"
        assert convert_msajax_date("hello") == "hello"
        assert convert_msajax_date("") == ""

    def test_zero_epoch(self):
        assert convert_msajax_date("/Date(0)/") == "1970-01-01"


class TestNormalizeJsonDates:
    """Recursive date normalization in JSON trees."""

    def test_nested_dict(self):
        data = {"date": "/Date(1504224000000)/", "name": "Test"}
        result = normalize_json_dates(data)
        assert result["date"] == "2017-09-01"
        assert result["name"] == "Test"

    def test_list_of_dicts(self):
        data = [{"d": "/Date(0)/"}, {"d": "/Date(86400000)/"}]
        result = normalize_json_dates(data)
        assert result[0]["d"] == "1970-01-01"
        assert result[1]["d"] == "1970-01-02"

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": "/Date(1504224000000)/"}}}
        result = normalize_json_dates(data)
        assert result["a"]["b"]["c"] == "2017-09-01"

    def test_non_date_strings_unchanged(self):
        data = {"s": "hello", "n": 42, "f": 3.14, "b": True, "x": None}
        assert normalize_json_dates(data) == data


# ─── SOAP → JSON-safe conversion ───────────────────────────────────────────


class TestToJsonable:
    """zeep objects → JSON-friendly Python dicts."""

    def test_decimal_to_float(self):
        assert to_jsonable(Decimal("123.456")) == 123.456

    def test_datetime_to_iso(self):
        dt = datetime(2024, 3, 15, 10, 30, 0)
        assert to_jsonable(dt) == "2024-03-15T10:30:00"

    def test_ordered_dict_to_dict(self):
        od = OrderedDict([("a", 1), ("b", "x")])
        result = to_jsonable(od)
        assert result == {"a": 1, "b": "x"}
        assert isinstance(result, dict)

    def test_wert_unwrapped(self):
        """MaStR wraps some values in {'Wert': X, ...} — these get unwrapped."""
        data = {"field": OrderedDict([("Wert", "hello"), ("Id", 42)])}
        result = to_jsonable(data)
        assert result["field"] == "hello"

    def test_nested_wert(self):
        data = OrderedDict([
            ("Name", OrderedDict([("Wert", "Solar Park")])),
            ("Leistung", OrderedDict([("Wert", Decimal("5000.5"))])),
        ])
        result = to_jsonable(data)
        assert result["Name"] == "Solar Park"
        assert result["Leistung"] == 5000.5

    def test_list_of_werts(self):
        data = [
            OrderedDict([("Wert", "a")]),
            OrderedDict([("Wert", "b")]),
        ]
        result = to_jsonable(data)
        assert result == ["a", "b"]

    def test_none_passthrough(self):
        assert to_jsonable(None) is None

    def test_primitives_passthrough(self):
        assert to_jsonable("hello") == "hello"
        assert to_jsonable(42) == 42
        assert to_jsonable(3.14) == 3.14
        assert to_jsonable(True) is True

    def test_tuple_to_list(self):
        result = to_jsonable((1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)
