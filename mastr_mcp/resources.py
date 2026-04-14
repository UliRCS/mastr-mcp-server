"""MCP Resources — structured reference data for Claude.

Exposes energy carrier lists, filter key documentation, and dropdown values
as MCP resources so Claude can look them up without parsing tool descriptions.
"""

from __future__ import annotations

import json
from typing import Any

from mastr_mcp.config import ENERGY_CARRIER_IDS, SOAP_TECHNOLOGY_MAP
from mastr_mcp.filters import (
    ACTOR_BOOLEAN_KEYS,
    ACTOR_FILTER_COLUMNS,
    CONSUMPTION_FILTER_COLUMNS,
    GAS_CONSUMPTION_BOOLEAN_KEYS,
    GAS_CONSUMPTION_FILTER_COLUMNS,
    GAS_PRODUCTION_FILTER_COLUMNS,
    NAP_BOOLEAN_KEYS,
    NAP_GAS_CONSUMPTION_COLUMNS,
    NAP_GAS_PRODUCTION_COLUMNS,
    NAP_POWER_CONSUMPTION_COLUMNS,
    NAP_POWER_GENERATION_COLUMNS,
    UNIT_DROPDOWN_VALUES,
    UNIT_FILTER_COLUMNS,
    ACTOR_DROPDOWN_VALUES,
    CONSUMPTION_DROPDOWN_VALUES,
    GAS_PRODUCTION_DROPDOWN_VALUES,
    GAS_CONSUMPTION_DROPDOWN_VALUES,
)
from mastr_mcp.server import mcp


# ─── Energy carriers ───────────────────────────────────────────────────────


@mcp.resource(
    "mastr://energy-carriers",
    name="energy_carriers",
    title="All 20 MaStR Energy Carriers",
    description=(
        "Complete list of all 20 energy carriers (Energieträger) with their "
        "numeric MaStR IDs, English primary keys, and German aliases. "
        "Use these IDs/aliases with the 'tech' filter in search_power_generation_public."
    ),
    mime_type="application/json",
)
def energy_carriers() -> str:
    # Group aliases by ID
    by_id: dict[str, list[str]] = {}
    for alias, eid in sorted(ENERGY_CARRIER_IDS.items()):
        by_id.setdefault(eid, []).append(alias)

    carriers = []
    for eid, aliases in sorted(by_id.items(), key=lambda x: int(x[0])):
        soap_value = None
        for a in aliases:
            if a in SOAP_TECHNOLOGY_MAP:
                soap_value = SOAP_TECHNOLOGY_MAP[a]
                break
        carriers.append({
            "id": eid,
            "aliases": aliases,
            "soap_value": soap_value,
        })
    return json.dumps(carriers, ensure_ascii=False, indent=2)


# ─── Filter keys per tool ──────────────────────────────────────────────────


def _filter_keys_doc(
    column_map: dict[str, str],
    boolean_keys: set[str] | None = None,
    dropdown_values: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Build a structured list of filter key docs."""
    keys: list[dict[str, Any]] = []
    for key, label in sorted(column_map.items()):
        entry: dict[str, Any] = {"key": key, "mastr_field": label}
        if boolean_keys and key in boolean_keys:
            entry["type"] = "boolean"
        elif dropdown_values and key in dropdown_values:
            entry["type"] = "dropdown"
            entry["values_count"] = len(dropdown_values[key])
        else:
            entry["type"] = "text"
        keys.append(entry)
    return keys


@mcp.resource(
    "mastr://filter-keys/{tool_name}",
    name="filter_keys",
    title="Filter Keys per Tool",
    description=(
        "Available filter keys for a specific public search tool. "
        "Use with tool names: power_generation, actors, power_consumption, gas_production, "
        "gas_consumption, nap_power_generation, nap_power_consumption, "
        "nap_gas_production, nap_gas_consumption."
    ),
    mime_type="application/json",
)
def filter_keys(tool_name: str) -> str:
    configs: dict[str, tuple[dict, set | None, dict | None]] = {
        "power_generation": (UNIT_FILTER_COLUMNS, None, UNIT_DROPDOWN_VALUES),
        "actors": (ACTOR_FILTER_COLUMNS, ACTOR_BOOLEAN_KEYS, ACTOR_DROPDOWN_VALUES),
        "power_consumption": (CONSUMPTION_FILTER_COLUMNS, None, CONSUMPTION_DROPDOWN_VALUES),
        "gas_production": (GAS_PRODUCTION_FILTER_COLUMNS, None, GAS_PRODUCTION_DROPDOWN_VALUES),
        "gas_consumption": (GAS_CONSUMPTION_FILTER_COLUMNS, GAS_CONSUMPTION_BOOLEAN_KEYS, GAS_CONSUMPTION_DROPDOWN_VALUES),
        "nap_power_generation": (NAP_POWER_GENERATION_COLUMNS, NAP_BOOLEAN_KEYS, None),
        "nap_power_consumption": (NAP_POWER_CONSUMPTION_COLUMNS, NAP_BOOLEAN_KEYS, None),
        "nap_gas_production": (NAP_GAS_PRODUCTION_COLUMNS, NAP_BOOLEAN_KEYS, None),
        "nap_gas_consumption": (NAP_GAS_CONSUMPTION_COLUMNS, NAP_BOOLEAN_KEYS, None),
    }
    if tool_name not in configs:
        return json.dumps({
            "error": f"Unknown tool '{tool_name}'",
            "valid_tools": sorted(configs.keys()),
        })
    col_map, bools, dropdowns = configs[tool_name]
    return json.dumps(
        _filter_keys_doc(col_map, bools, dropdowns),
        ensure_ascii=False,
        indent=2,
    )


# ─── Dropdown values ───────────────────────────────────────────────────────


@mcp.resource(
    "mastr://dropdowns/{tool_name}/{field_name}",
    name="dropdown_values",
    title="Dropdown Values for a Filter Field",
    description=(
        "All accepted label→ID mappings for a specific dropdown filter field. "
        "tool_name: power_generation, actors, power_consumption, gas_production, gas_consumption. "
        "field_name: the filter key (e.g. bundesland, status, wind_manufacturer)."
    ),
    mime_type="application/json",
)
def dropdown_values(tool_name: str, field_name: str) -> str:
    all_dropdowns: dict[str, dict[str, dict[str, str]]] = {
        "power_generation": UNIT_DROPDOWN_VALUES,
        "actors": ACTOR_DROPDOWN_VALUES,
        "power_consumption": CONSUMPTION_DROPDOWN_VALUES,
        "gas_production": GAS_PRODUCTION_DROPDOWN_VALUES,
        "gas_consumption": GAS_CONSUMPTION_DROPDOWN_VALUES,
    }
    if tool_name not in all_dropdowns:
        return json.dumps({
            "error": f"Unknown tool '{tool_name}'",
            "valid_tools": sorted(all_dropdowns.keys()),
        })
    tool_dd = all_dropdowns[tool_name]
    if field_name not in tool_dd:
        return json.dumps({
            "error": f"No dropdown values for field '{field_name}' in {tool_name}",
            "available_fields": sorted(tool_dd.keys()),
        })
    # Return as list of {label, id} for clarity
    entries = [
        {"label": label, "id": mid}
        for label, mid in sorted(tool_dd[field_name].items())
    ]
    return json.dumps(entries, ensure_ascii=False, indent=2)


# ─── Filter operators reference ─────────────────────────────────────────────


@mcp.resource(
    "mastr://filter-operators",
    name="filter_operators",
    title="Filter Operators Reference",
    description=(
        "All 10 filter operators with their key suffixes and Kendo tokens. "
        "Append the suffix to any filter key to change the comparison type."
    ),
    mime_type="application/json",
)
def filter_operators() -> str:
    operators = [
        {"suffix": "(none)", "operator": "eq", "description": "Equal (default)"},
        {"suffix": "=", "operator": "eq", "description": "Equal (explicit)"},
        {"suffix": "!=", "operator": "neq", "description": "Not equal"},
        {"suffix": "%", "operator": "ct", "description": "Contains"},
        {"suffix": "!%", "operator": "nct", "description": "Not contains"},
        {"suffix": ":", "operator": "sw", "description": "Starts with"},
        {"suffix": "$", "operator": "ew", "description": "Ends with"},
        {"suffix": ">", "operator": "gt", "description": "Greater than"},
        {"suffix": "<", "operator": "lt", "description": "Less than"},
        {"suffix": "?", "operator": "null", "description": "Is NULL (no value needed)"},
        {"suffix": "! or !?", "operator": "nn", "description": "Is NOT NULL (no value needed)"},
    ]
    return json.dumps(operators, ensure_ascii=False, indent=2)
