"""SOAP client management and HTTP helpers for MaStR API access."""

from __future__ import annotations

import logging
from time import sleep
from typing import Any, Optional

import requests

from mastr_mcp.config import MASTR_TOKEN, MASTR_USER, MASTR_WSDL_URL
from mastr_mcp.serialization import normalize_json_dates, serialize_soap

logger = logging.getLogger("mastr-mcp")

# ─── SOAP client (lazy singleton) ───────────────────────────────────────────

_mastr_client = None  # zeep.Client instance


def _suppress_zeep_parsing_errors() -> None:
    """Suppress noisy ValueError from zeep when MaStR returns invalid seconds."""

    class _FilterParseSecond(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if record.exc_info is None:
                return True
            _, inst, _ = record.exc_info
            if (
                isinstance(inst, ValueError)
                and inst.args
                and inst.args[0] == "second must be in 0..59"
            ):
                return False
            return True

    zplogger = logging.getLogger("zeep.xsd.types.simple")
    if not any(isinstance(f, _FilterParseSecond) for f in zplogger.filters):
        zplogger.addFilter(_FilterParseSecond())


def _connect_mastr():
    """Build a robust zeep SOAP client for the MaStR WSDL."""
    from zeep import Client, Settings
    from zeep.cache import SqliteCache
    from zeep.transports import Transport

    session = requests.Session()
    session.max_redirects = 30
    adapter = requests.adapters.HTTPAdapter(
        max_retries=3, pool_connections=2000, pool_maxsize=2000
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    transport = Transport(cache=SqliteCache(), timeout=600, session=session)
    settings = Settings(strict=False, xml_huge_tree=True)
    client = Client(wsdl=MASTR_WSDL_URL, transport=transport, settings=settings)

    _suppress_zeep_parsing_errors()
    return client


def get_mastr_client():
    global _mastr_client
    if _mastr_client is None:
        _mastr_client = _connect_mastr()
    return _mastr_client


def client_plant():
    """SOAP port for plants/EEG (Service-Port: Anlage)."""
    return get_mastr_client().bind("Marktstammdatenregister", "Anlage")


def client_actor():
    """SOAP port for market actors (Service-Port: Akteur)."""
    return get_mastr_client().bind("Marktstammdatenregister", "Akteur")


def client_nap():
    """SOAP port for grid connection points (Service-Port: Netzanschlusspunkt)."""
    return get_mastr_client().bind("Marktstammdatenregister", "Netzanschlusspunkt")


def client_general():
    """SOAP port for general functions (no auth required)."""
    return get_mastr_client().bind("Marktstammdatenregister", "")


def require_credentials() -> None:
    if not MASTR_USER or not MASTR_TOKEN:
        raise RuntimeError(
            "MASTR_USER and MASTR_TOKEN environment variables must be set to use "
            "SOAP tools. Set them in your Claude Desktop / Code config or the shell."
        )


# ─── Retry helper ────────────────────────────────────────────────────────────


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception indicates an HTTP 429 / rate-limit SOAP fault."""
    msg = str(exc).lower()
    return "tomanyrequests" in msg or "too many requests" in msg or "429" in msg


def retry_soap(
    func,
    kwargs: dict[str, Any],
    *,
    max_attempts: int = 5,
    label: str = "SOAP call",
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    max_total_seconds: float = 300.0,
) -> Any:
    """Call a SOAP method with retries and exponential back-off.

    Implements BNetzA-recommended exponential backoff:
    - Starts at ``initial_delay`` seconds (default 0.1)
    - Doubles each retry (``backoff_factor`` = 2)
    - Aborts if cumulative wait exceeds ``max_total_seconds``
    - Rate-limit errors (HTTP 429 / ToManyRequests) get longer waits

    Returns the serialized result on success, or a dict with an ``error`` key
    on exhaustion.
    """
    last_exc: Optional[Exception] = None
    delay = initial_delay
    total_waited = 0.0

    for attempt in range(max_attempts):
        try:
            raw = func(**kwargs)
            return serialize_soap(raw)
        except Exception as exc:
            last_exc = exc

            if _is_rate_limit_error(exc):
                # Rate-limited: use longer backoff (min 5s, then double)
                delay = max(delay, 5.0) * backoff_factor
                logger.warning(
                    "%s: rate-limited (attempt %d/%d), waiting %.1fs",
                    label, attempt + 1, max_attempts, delay,
                )
            else:
                logger.debug(
                    "%s: error on attempt %d/%d: %s — retrying in %.1fs",
                    label, attempt + 1, max_attempts, exc, delay,
                )

            if total_waited + delay > max_total_seconds:
                break

            sleep(delay)
            total_waited += delay
            delay *= backoff_factor

    return {"error": f"{label} failed after {max_attempts} attempts: {last_exc}"}


# ─── Public JSON fetch ───────────────────────────────────────────────────────


def fetch_public_json(url: str) -> dict:
    """Fetch a MaStR public JSON endpoint with date normalization."""
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "User-Agent": "mastr-mcp-server/0.1 (+https://www.marktstammdatenregister.de)",
        "X-Requested-With": "XMLHttpRequest",
    }
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return normalize_json_dates(resp.json())
