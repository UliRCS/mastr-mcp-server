"""Comprehensive end-to-end live test against the MaStR API.

Run with:  uv run python tests/test_e2e_live.py
Not in pytest (requires live credentials + network).
"""

from __future__ import annotations

import json
import sys

passed = 0
failed = 0
errors: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  FAIL {name}: {detail}")


def main() -> None:
    global passed, failed

    print("=== 1. PUBLIC JSON TOOLS ===")

    from mastr_mcp.tools_public import (
        search_power_generation_public,
        search_actors_public,
        search_power_consumption_public,
        search_gas_production_public,
        search_gas_consumption_public,
        search_grid_connections_public,
        get_local_time,
    )

    # 1a. search_power_generation_public
    r = search_power_generation_public({"tech": "wind", "postcode:": "26"}, page_size=2)
    check("units: wind+PLZ-prefix", r.get("total", 0) > 0)
    check("units: no warnings on valid keys", r.get("warnings") is None)

    r = search_power_generation_public({"tech": "solar", "bundesland": "Bayern", "capacity>": 5000}, page_size=2)
    check("units: solar+BL+capacity", r.get("total", 0) > 0)

    r = search_power_generation_public({"tech": "nuclear"}, page_size=2)
    check("units: nuclear", r.get("total", 0) > 0)

    r = search_power_generation_public({"tech": "hydrogen"}, page_size=2)
    check("units: hydrogen", r.get("total", 0) >= 0)

    r = search_power_generation_public({"postode": "12345"}, page_size=1)
    check("units: unknown key warning", r.get("warnings") is not None)
    check("units: warning mentions key", "postode" in str(r.get("warnings", "")))

    # 1b. search_actors_public
    r = search_actors_public({"function": "Stromnetzbetreiber", "dso_large": True}, page_size=2)
    check("actors: DSO large", r.get("total", 0) > 0)

    r = search_actors_public({"name%": "Stadtwerke"}, page_size=2)
    check("actors: name contains", r.get("total", 0) > 0)

    # 1c. search_power_consumption_public
    r = search_power_consumption_public({"bundesland": "Bayern"}, page_size=2)
    check("consumption: Bayern", r.get("total", 0) > 0)

    # 1d. search_gas_production_public
    r = search_gas_production_public({"gas_technology": "Power-to-Gas (Wasserstoff)"}, page_size=2)
    check("gas_prod: PtG H2", r.get("total", 0) > 0)

    # 1e. search_gas_consumption_public
    r = search_gas_consumption_public({"gas_quality": "H-Gas", "gas_for_power": True}, page_size=2)
    check("gas_cons: H-Gas + power", r.get("total", 0) > 0)

    # 1f. search_grid_connections_public (all 4 types)
    r = search_grid_connections_public("power_generation", {"postcode": "49074"}, page_size=2)
    check("nap_pg: PLZ", r.get("total", 0) > 0)

    r = search_grid_connections_public("power_consumption", {"voltage_level": "Mittelspannung"}, page_size=2)
    check("nap_pc: voltage_level", r.get("total", 0) > 0)

    r = search_grid_connections_public("gas_production", {}, page_size=2)
    check("nap_gp: all", r.get("total", 0) > 0)

    r = search_grid_connections_public("gas_consumption", {"gas_quality": "H-Gas"}, page_size=2)
    check("nap_gc: H-Gas", r.get("total", 0) > 0)

    r = search_grid_connections_public("invalid_type", {})
    check("nap: invalid type error", "error" in r)

    # 1g. get_local_time (no auth, now in tools_public)
    r = get_local_time()
    check("local_time: connected", r.get("status") == "connected")

    print()
    print("=== 2. SOAP TOOLS ===")

    from mastr_mcp.tools_soap import (
        get_unit,
        search_power_generation_soap,
        get_actor,
        get_api_quota,
        get_recent_changes,
        get_location,
        get_grid_connection,
        get_catalog_categories,
        get_catalog_values,
        get_balancing_areas,
        search_power_consumption_soap,
        search_gas_production_soap,
        search_gas_consumption_soap,
        search_actors_soap,
    )

    # 2a. get_api_quota
    r = get_api_quota()
    check("api_quota: has limit", r.get("limit", 0) > 0)
    check("api_quota: has used", "used" in r)

    # 2c. get_unit (Wind)
    r = get_unit("SEE966095906064", "wind")
    check("get_unit: wind", "EinheitMastrNummer" in r)

    # 2d. get_unit (Solar — use a known active unit in Munich)
    r = get_unit("SEE968062307997", "solar")
    check("get_unit: solar", "EinheitMastrNummer" in r)

    # 2e. search_power_generation_soap
    r = search_power_generation_soap(technology="wind", postcode="26624", limit=5)
    check("search_soap: wind+PLZ", isinstance(r, dict) and r.get("count", 0) > 0)

    # 2f. get_actor
    r = get_actor("ABR944375564166")
    check("get_actor: exists", "MastrNummer" in r)

    # 2g. get_recent_changes
    r = get_recent_changes("2026-04-01", "EEG", limit=5)
    check("recent_changes: EEG", isinstance(r, (list, dict)))

    # 2h. search_power_consumption_soap
    r = search_power_consumption_soap(postcode="49074", limit=5)
    check("power_consumers_soap", isinstance(r, (list, dict)))

    # 2i. search_gas_production_soap
    r = search_gas_production_soap(limit=5)
    check("gas_producers_soap", isinstance(r, (list, dict)))

    # 2j. search_gas_consumption_soap
    r = search_gas_consumption_soap(limit=5)
    check("gas_consumers_soap", isinstance(r, (list, dict)))

    # 2k. search_actors_soap
    r = search_actors_soap(market_function="Stromnetzbetreiber", limit=5)
    check("actors_soap", isinstance(r, (list, dict)))

    # 2l. get_location
    r = get_location("SEL978745131498")
    check("get_location", isinstance(r, dict) and "error" not in r)

    # 2m. get_catalog_categories
    r = get_catalog_categories()
    check("catalog_categories", isinstance(r, dict) and r.get("count", 0) > 0)

    # 2n. get_catalog_values
    r = get_catalog_values(16, limit=10)
    check("catalog_values: Rechtsform", isinstance(r, dict) and r.get("count", 0) > 0)

    # 2o. get_balancing_areas
    r = get_balancing_areas(limit=10)
    check("balancing_areas", isinstance(r, dict) and r.get("count", 0) > 0)

    # 2p. get_grid_connection
    r = get_grid_connection("SEE966095906064")
    check("get_grid_conn: wind unit", r.get("count", 0) > 0)
    if r.get("results"):
        nap = r["results"][0]
        check("get_grid_conn: has NAP MaStR", "NetzanschlusspunktMastrNummer" in nap)
        check("get_grid_conn: has Lokation", "LokationMastrNummer" in nap)

    print()
    print("=== 3. MCP RESOURCES ===")

    from mastr_mcp.resources import (
        energy_carriers,
        filter_keys,
        dropdown_values,
        filter_operators,
    )

    ec = json.loads(energy_carriers())
    check("resource: energy_carriers count", len(ec) == 20, f"got {len(ec)}")

    fk = json.loads(filter_keys("power_generation"))
    check("resource: filter_keys power_generation", len(fk) == 27, f"got {len(fk)}")

    fk_nap = json.loads(filter_keys("nap_power_generation"))
    check("resource: filter_keys nap_pg", len(fk_nap) == 20, f"got {len(fk_nap)}")

    fk_err = json.loads(filter_keys("invalid"))
    check("resource: filter_keys invalid", "error" in fk_err)

    dd = json.loads(dropdown_values("power_generation", "bundesland"))
    check("resource: dropdown bundesland", len(dd) > 10, f"got {len(dd)}")

    dd_err = json.loads(dropdown_values("power_generation", "xyz"))
    check("resource: dropdown invalid", "error" in dd_err)

    ops = json.loads(filter_operators())
    check("resource: filter_operators", len(ops) == 11, f"got {len(ops)}")

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
