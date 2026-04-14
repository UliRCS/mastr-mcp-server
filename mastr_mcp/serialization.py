"""Serialization helpers: SOAP → JSON-safe dicts, MS-AJAX date normalization."""

from __future__ import annotations

import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any


# ─── MS-AJAX date normalization (public JSON API) ────────────────────────────

# MaStR's public JSON endpoints serialize timestamps in the legacy MS-AJAX
# format: '/Date(1504224000000)/' — milliseconds since the Unix epoch, UTC,
# optionally followed by a display-only timezone offset like '+0200'.
_MSAJAX_DATE_RE = re.compile(r"^/Date\((-?\d+)(?:[+\-]\d{4})?\)/$")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def convert_msajax_date(value: str) -> str:
    """Convert an MS-AJAX date string like '/Date(1504224000000)/' to ISO-8601.

    - Midnight UTC timestamps → 'YYYY-MM-DD' (pure dates).
    - Real timestamps → full ISO-8601 with timezone.
    - Negative timestamps work on Windows (via epoch + timedelta arithmetic).
    - Non-matching strings are returned unchanged.
    """
    match = _MSAJAX_DATE_RE.match(value)
    if not match:
        return value
    try:
        ms = int(match.group(1))
        dt = _EPOCH + timedelta(milliseconds=ms)
    except (OverflowError, ValueError):
        return value
    if ms % 86_400_000 == 0:
        return dt.date().isoformat()
    return dt.isoformat()


def normalize_json_dates(obj: Any) -> Any:
    """Recursively convert MS-AJAX date strings inside a decoded JSON tree."""
    if isinstance(obj, dict):
        return {k: normalize_json_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_json_dates(item) for item in obj]
    if isinstance(obj, str) and obj.startswith("/Date(") and obj.endswith(")/"):
        return convert_msajax_date(obj)
    return obj


# ─── SOAP serialization ─────────────────────────────────────────────────────


def _unwrap_wert(value: Any) -> Any:
    """Extract ``Wert`` from MaStR wrapper dicts like {'Wert': X, ...}."""
    if isinstance(value, (OrderedDict, dict)) and "Wert" in value:
        return value["Wert"]
    return value


def to_jsonable(obj: Any) -> Any:
    """Recursively convert a zeep-serialized object tree into JSON-safe primitives."""
    if obj is None:
        return None
    if isinstance(obj, (OrderedDict, dict)):
        return {k: to_jsonable(_unwrap_wert(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(_unwrap_wert(item)) for item in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(_unwrap_wert(item)) for item in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool)):
        return obj
    try:
        return obj.isoformat()  # type: ignore[attr-defined]
    except Exception:
        return str(obj)


def serialize_soap(obj: Any) -> Any:
    """zeep serialize → normalize Wert-wrappers → JSON-safe."""
    import zeep.helpers as zh

    return to_jsonable(zh.serialize_object(obj))
