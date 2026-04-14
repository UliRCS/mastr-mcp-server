"""Public JSON API tools (no authentication required)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from pydantic import Field

from mastr_mcp.client import client_general, fetch_public_json
from mastr_mcp.serialization import serialize_soap
from mastr_mcp.config import (
    MASTR_JSON_ACTOR_BASE,
    MASTR_JSON_NAP_BASE,
    MASTR_JSON_UNIT_BASE,
)
from mastr_mcp.filters import (
    ACTOR_BOOLEAN_KEYS,
    ACTOR_DROPDOWN_VALUES,
    ACTOR_FILTER_COLUMNS,
    CONSUMPTION_DROPDOWN_VALUES,
    CONSUMPTION_FILTER_COLUMNS,
    GAS_CONSUMPTION_BOOLEAN_KEYS,
    GAS_CONSUMPTION_DROPDOWN_VALUES,
    GAS_CONSUMPTION_FILTER_COLUMNS,
    GAS_PRODUCTION_DROPDOWN_VALUES,
    GAS_PRODUCTION_FILTER_COLUMNS,
    NAP_BOOLEAN_KEYS,
    NAP_TYPE_DISPATCH,
    UNIT_DROPDOWN_VALUES,
    UNIT_FILTER_COLUMNS,
    build_extended_filter,
)
from mastr_mcp.server import mcp

# ─── Shared helper ───────────────────────────────────────────────────────────

# Operator docs shared across all public search tools.
_OP_DOCS = (
    "Operators: '=' (eq, default), '!=' (neq), "
    "'%' (contains), '!%' (not contains), "
    "':' (starts with), '$' (ends with), "
    "'>' (gt), '<' (lt), "
    "'?' (is null), '!' or '!?' (is not null). "
)


def _public_search(
    base_url: str,
    endpoint: str,
    filters: dict[str, Any],
    column_map: dict[str, str],
    *,
    page: int = 1,
    page_size: int = 100,
    translate_tech: bool = False,
    dropdown_values: Optional[dict[str, dict[str, str]]] = None,
    boolean_keys: Optional[set[str]] = None,
) -> dict:
    """Execute a public MaStR JSON search and return a standardized result dict."""
    if not isinstance(filters, dict):
        return {"error": "filters must be a dict"}

    flt, unknown_keys = build_extended_filter(
        filters,
        column_map,
        translate_tech=translate_tech,
        dropdown_values=dropdown_values,
        boolean_keys=boolean_keys,
    )

    params = (
        f"sort=&page={int(page)}&pageSize={min(int(page_size), 5000)}"
        f"&group=&filter={flt}"
    )
    url = f"{base_url}/{endpoint}?{params}"

    try:
        data = fetch_public_json(url)
    except Exception as exc:
        return {"error": str(exc), "url": url}

    result: dict = {
        "total": data.get("Total", 0),
        "page": page,
        "page_size": page_size,
        "count": len(data.get("Data") or []),
        "results": data.get("Data") or [],
    }
    if unknown_keys:
        valid = sorted(column_map.keys())
        result["warnings"] = [
            f"Unknown filter key(s) ignored: {unknown_keys}. "
            f"Valid keys: {valid}"
        ]
    return result


# ─── Tool: search_power_generation_public (Stromerzeugung) ─────────────────


@mcp.tool()
def search_power_generation_public(
    filters: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Filter dict with optional operator suffixes on each key. "
                + _OP_DOCS
                + "Supported filter keys: "
                "tech, name, eeg_key, mastr_number, mastr_operator, "
                "capacity, capacity_netto, "
                "postcode, city, landkreis, street, bundesland, longitude, latitude, "
                "status, commission_date, eeg_commission_date, "
                "operator_name, "
                "wind_park, wind_manufacturer, hub_height, rotor_diameter, "
                "solar_park, "
                "storage_capacity, storage_mastr_number, storage_technology, "
                "battery_technology. "
                "tech shortcuts: 'wind', 'solar'/'pv', 'biomass', 'hydro', "
                "'storage', 'geo', 'natural_gas', 'nuclear', 'hydrogen', etc. "
                "German aliases also work (erdgas, kernkraft, wasserstoff, etc.). "
                "Dropdown fields (bundesland, status, wind_manufacturer, "
                "storage_technology, battery_technology) accept label or MaStR ID. "
                "Example: {'tech': 'wind', 'bundesland': 'Niedersachsen', "
                "'capacity>': 3000, 'eeg_key!?': ''}"
            ),
        ),
    ],
    page: Annotated[int, Field(description="1-based page number.")] = 1,
    page_size: Annotated[int, Field(description="Page size (max 5000).")] = 100,
) -> dict:
    """Search **power generation units** (Stromerzeugung) — no auth required.

    The primary tool for finding wind turbines, solar panels, biomass plants,
    hydro, storage, gas turbines, nuclear plants, etc. in the MaStR register.
    Supports all 20 energy carriers with 27 filter keys and 10 operators.

    Use this as the default search tool for power generation questions.
    For full unit details after finding a MaStR number, use get_unit (SOAP).
    """
    return _public_search(
        MASTR_JSON_UNIT_BASE,
        "GetErweiterteOeffentlicheEinheitStromerzeugung",
        filters,
        UNIT_FILTER_COLUMNS,
        page=page,
        page_size=page_size,
        translate_tech=True,
        dropdown_values=UNIT_DROPDOWN_VALUES,
    )


# ─── Tool: search_actors_public ─────────────────────────────────────────────


@mcp.tool()
def search_actors_public(
    filters: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Filter dict with optional operator suffixes on each key. "
                + _OP_DOCS
                + "Supported filter keys: "
                "name, mastr_number, bnetza_number, acer_code, vat_id, "
                "register_court, register_number, "
                "function, roles, industry_group, "
                "postcode, city, street, bundesland, nuts_region, "
                "status, registration_date, last_update, activity_start, activity_end, "
                "dso_large, dso_closed, sme_flag. "
                "Dropdown fields (bundesland, function, status, roles, "
                "nuts_region, industry_group) accept label or MaStR ID. "
                "Boolean fields (dso_large, dso_closed, sme_flag) accept "
                "true/false, ja/nein, 1/0. "
                "NOTE: MaStR stores '&' as fullwidth U+FF06 — use 'name%' "
                "with a substring without '&' for company name searches. "
                "Example: {'function': 'Stromnetzbetreiber', 'dso_large': True}"
            ),
        ),
    ],
    page: Annotated[int, Field(description="1-based page number.")] = 1,
    page_size: Annotated[int, Field(description="Page size (max 5000).")] = 100,
) -> dict:
    """Search **market actors** (Marktakteure) — no auth required.

    Find energy market participants: DSOs (Netzbetreiber), generators,
    suppliers, traders, and more. 23 filter keys for name, function, role,
    location, status, and DSO flags (large DSO, closed distribution network).

    NOTE: MaStR stores '&' as fullwidth U+FF06 in company names. Use
    'name%' with a substring without '&' for reliable company name searches.
    """
    return _public_search(
        MASTR_JSON_ACTOR_BASE,
        "GetOeffentlicheMarktakteure",
        filters,
        ACTOR_FILTER_COLUMNS,
        page=page,
        page_size=page_size,
        dropdown_values=ACTOR_DROPDOWN_VALUES,
        boolean_keys=ACTOR_BOOLEAN_KEYS,
    )


# ─── Tool: search_power_consumption_public (Stromverbrauch) ─────────────────


@mcp.tool()
def search_power_consumption_public(
    filters: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Filter dict with optional operator suffixes on each key. "
                + _OP_DOCS
                + "Supported filter keys: "
                "name, mastr_number, mastr_operator, location_mastr, dso_mastr, "
                "operator_name, dso_name, "
                "postcode, city, landkreis, street, bundesland, municipality, "
                "municipality_key, landmark, parcel, country, longitude, latitude, "
                "status, commission_date, current_location_date, shutdown_date, "
                "planned_date, registration_date, last_update, "
                "large_consumers, voltage_level, dso_check. "
                "Dropdown fields (status, bundesland, country, voltage_level, "
                "dso_check) accept label or MaStR ID. "
                "Example: {'bundesland': 'Bayern', 'voltage_level': 'Hochspannung'}"
            ),
        ),
    ],
    page: Annotated[int, Field(description="1-based page number.")] = 1,
    page_size: Annotated[int, Field(description="Page size (max 5000).")] = 100,
) -> dict:
    """Search **power consumption units** (Stromverbrauch) — no auth required.

    Find large electricity consumers registered in MaStR. 29 filter keys
    covering identification, location, dates, voltage level, and DSO checks.

    Use this when searching for electricity consumers (not generators).
    """
    return _public_search(
        MASTR_JSON_UNIT_BASE,
        "GetErweiterteOeffentlicheEinheitStromverbrauch",
        filters,
        CONSUMPTION_FILTER_COLUMNS,
        page=page,
        page_size=page_size,
        dropdown_values=CONSUMPTION_DROPDOWN_VALUES,
    )


# ─── Tool: search_gas_production_public (Gaserzeugung) ──────────────────────


@mcp.tool()
def search_gas_production_public(
    filters: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Filter dict with optional operator suffixes on each key. "
                + _OP_DOCS
                + "Supported filter keys: "
                "name, mastr_number, mastr_operator, location_mastr, dso_mastr, "
                "operator_name, dso_name, "
                "postcode, city, landkreis, street, bundesland, municipality, "
                "municipality_key, landmark, parcel, country, longitude, latitude, "
                "status, commission_date, current_location_date, shutdown_date, "
                "planned_date, registration_date, last_update, "
                "gas_production_capacity, gas_technology, unit_type, dso_check. "
                "Dropdown fields (status, bundesland, country, gas_technology, "
                "unit_type, dso_check) accept label or MaStR ID. "
                "gas_technology values: 'Biomethan-Erzeugung', "
                "'Förderung fossilen Erdgases', 'Liquefied Natural Gas', "
                "'Power-to-Gas (Methan)', 'Power-to-Gas (Wasserstoff)'. "
                "unit_type values: 'Gaserzeugungseinheit', 'Gasspeichereinheit'. "
                "Example: {'gas_technology': 'Power-to-Gas (Wasserstoff)', "
                "'status': 'In Betrieb'}"
            ),
        ),
    ],
    page: Annotated[int, Field(description="1-based page number.")] = 1,
    page_size: Annotated[int, Field(description="Page size (max 5000).")] = 100,
) -> dict:
    """Search **gas production and storage units** (Gaserzeugung) — no auth required.

    Find biogas plants, Power-to-Gas (hydrogen/methane), LNG terminals,
    fossil gas producers, and gas storage units. 30 filter keys including
    gas technology and unit type (producer vs. storage).
    """
    return _public_search(
        MASTR_JSON_UNIT_BASE,
        "GetErweiterteOeffentlicheEinheitGaserzeugung",
        filters,
        GAS_PRODUCTION_FILTER_COLUMNS,
        page=page,
        page_size=page_size,
        dropdown_values=GAS_PRODUCTION_DROPDOWN_VALUES,
    )


# ─── Tool: search_gas_consumption_public (Gasverbrauch) ─────────────────────


@mcp.tool()
def search_gas_consumption_public(
    filters: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Filter dict with optional operator suffixes on each key. "
                + _OP_DOCS
                + "Supported filter keys: "
                "name, mastr_number, mastr_operator, location_mastr, dso_mastr, "
                "operator_name, dso_name, "
                "postcode, city, landkreis, street, bundesland, municipality, "
                "municipality_key, landmark, parcel, country, longitude, latitude, "
                "status, commission_date, current_location_date, shutdown_date, "
                "planned_date, registration_date, last_update, "
                "max_gas_capacity, gas_quality, gas_for_power, dso_check. "
                "Dropdown fields (status, bundesland, country, gas_quality, "
                "dso_check) accept label or MaStR ID. "
                "gas_quality values: 'H-Gas', 'L-Gas'. "
                "gas_for_power is a boolean (true/false, ja/nein). "
                "Example: {'gas_quality': 'H-Gas', 'gas_for_power': True}"
            ),
        ),
    ],
    page: Annotated[int, Field(description="1-based page number.")] = 1,
    page_size: Annotated[int, Field(description="Page size (max 5000).")] = 100,
) -> dict:
    """Search **gas consumption units** (Gasverbrauch) — no auth required.

    Find registered gas consumers. 30 filter keys covering identification,
    location, dates, gas quality (H-Gas/L-Gas), maximum capacity, and
    whether the gas is used for power generation (gas_for_power flag).
    """
    return _public_search(
        MASTR_JSON_UNIT_BASE,
        "GetErweiterteOeffentlicheEinheitGasverbrauch",
        filters,
        GAS_CONSUMPTION_FILTER_COLUMNS,
        page=page,
        page_size=page_size,
        dropdown_values=GAS_CONSUMPTION_DROPDOWN_VALUES,
        boolean_keys=GAS_CONSUMPTION_BOOLEAN_KEYS,
    )


# ─── Tool: search_grid_connections_public (Netzanschlusspunkte & Lokationen) ─


@mcp.tool()
def search_grid_connections_public(
    connection_type: Annotated[
        str,
        Field(
            description=(
                "Type of grid connection. One of: "
                "'power_generation' (Stromerzeugung), "
                "'power_consumption' (Stromverbrauch), "
                "'gas_production' (Gaserzeugung), "
                "'gas_consumption' (Gasverbrauch)."
            ),
        ),
    ],
    filters: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Filter dict with optional operator suffixes on each key. "
                + _OP_DOCS
                + "Shared filter keys (all 4 types): "
                "location_mastr, location_name, nap_mastr, nap_name, "
                "dso_mastr, dso_name, unit_mastr, "
                "postcode, city, municipality, municipality_key, "
                "capacity, planned. "
                "Power (Strom) types add: "
                "voltage_level, voltage_level_id, control_area, "
                "control_area_id, balancing_area, metering_location. "
                "power_generation also has: unit_types. "
                "Gas types add: "
                "gas_quality, gas_quality_id, market_area, market_area_id. "
                "planned is a boolean (true/false). "
                "Dropdown fields accept both label and numeric ID "
                "(e.g. voltage_level='Mittelspannung' or "
                "voltage_level_id='352'). "
                "Example: {'postcode': '49074', "
                "'voltage_level': 'Mittelspannung'}"
            ),
        ),
    ],
    page: Annotated[int, Field(description="1-based page number.")] = 1,
    page_size: Annotated[int, Field(description="Page size (max 5000).")] = 100,
) -> dict:
    """Search **grid connection points and locations** (Netzanschlusspunkte) — no auth required.

    Find where units connect to the grid. Returns location data, grid
    connection points, linked units, DSO info, and network parameters.
    Supports 4 connection types: power generation/consumption and gas
    production/consumption. Power types include voltage level, control area,
    and balancing area. Gas types include gas quality and market area.

    For grid connection details of a specific unit, use get_grid_connection (SOAP).
    """
    ct = connection_type.lower().strip()
    if ct not in NAP_TYPE_DISPATCH:
        return {
            "error": (
                f"Unknown connection_type '{connection_type}'. "
                f"Valid: {sorted(NAP_TYPE_DISPATCH.keys())}"
            )
        }

    endpoint, column_map = NAP_TYPE_DISPATCH[ct]
    return _public_search(
        MASTR_JSON_NAP_BASE,
        endpoint,
        filters,
        column_map,
        page=page,
        page_size=page_size,
        boolean_keys=NAP_BOOLEAN_KEYS,
    )


# ─── Tool: get_local_time (connection test, no auth) ────────────────────────


@mcp.tool()
def get_local_time() -> dict:
    """Connection test — returns current server time if MaStR SOAP service is reachable.

    No authentication required. Use this to verify network connectivity.
    """
    try:
        raw = client_general().GetLokaleUhrzeit()
        data = serialize_soap(raw)
        return {"status": "connected", "response": data}
    except Exception as exc:
        return {"error": str(exc), "status": "connection_failed"}
