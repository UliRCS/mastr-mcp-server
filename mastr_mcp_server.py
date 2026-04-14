"""
MaStR MCP Server — Marktstammdatenregister integration for Claude.

Provides tools to query the German energy market register (Marktstammdatenregister)
via both the public JSON API (no auth) and the authenticated SOAP API.

Public tools (always available, 7 tools):
    - search_power_generation_public  — power generation units (27 filter keys, all 20 energy carriers)
    - search_actors_public            — market actors (23 filter keys)
    - search_power_consumption_public — power consumption units (29 filter keys)
    - search_gas_production_public    — gas production/storage units (30 filter keys)
    - search_gas_consumption_public   — gas consumption units (30 filter keys)
    - search_grid_connections_public  — grid connection points (4 types, 12-20 filter keys)
    - get_local_time                  — connection test

SOAP tools (require MASTR_USER + MASTR_TOKEN in .env, 14 tools):
    - get_unit                        — full unit details + EEG + CHP + permit + storage
    - search_power_generation_soap    — filtered search (technology, postcode, capacity, dates)
    - get_actor                       — market actor details by MaStR number
    - get_api_quota                   — daily API quota usage
    - get_recent_changes              — delta sync (changes since date)
    - search_power_consumption_soap   — search power consumers
    - search_gas_production_soap      — search gas producers
    - search_gas_consumption_soap     — search gas consumers
    - search_actors_soap              — search market actors
    - get_location                    — location details with linked units
    - get_catalog_values              — enum/catalog values by category
    - get_catalog_categories          — list all catalog categories
    - get_balancing_areas             — grid balancing areas (Y-EIC codes)
    - get_grid_connection             — grid connection points for a unit

Usage:
    uv run mastr_mcp_server.py
    python mastr_mcp_server.py
"""

from mastr_mcp import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
