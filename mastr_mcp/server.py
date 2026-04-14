"""FastMCP server instance for the MaStR MCP Server."""

from mcp.server.fastmcp import FastMCP

from mastr_mcp.config import MASTR_USER, MASTR_TOKEN

_HAS_CREDENTIALS = bool(MASTR_USER and MASTR_TOKEN)

_INSTRUCTIONS = (
    "MaStR (Marktstammdatenregister) is the official German energy market register "
    "maintained by the Bundesnetzagentur. It contains master data for all power "
    "generation units (wind, solar, biomass, gas, nuclear, etc.), gas units, "
    "consumption units, market actors (DSOs, operators, suppliers), locations, "
    "and grid connection points in Germany.\n\n"
)

if _HAS_CREDENTIALS:
    _INSTRUCTIONS += (
        "This server has SOAP credentials configured. Both public JSON tools "
        "(no auth, flexible filters) and SOAP tools (authenticated, more detail) "
        "are available.\n\n"
        "Guidance for tool selection:\n"
        "- For SEARCHING units/actors/grid connections: prefer the public tools "
        "(search_*_public) — they have more filter keys and operators, and "
        "don't consume API quota.\n"
        "- For DETAILED DATA of a single unit: use get_unit (SOAP) — it returns "
        "full master data including EEG, CHP, permits, and storage in one call.\n"
        "- For DETAILED ACTOR DATA: use get_actor (SOAP).\n"
        "- For GRID CONNECTION details of a specific unit: use get_grid_connection (SOAP).\n"
        "- For DELTA SYNC, CATALOG LOOKUPS, BALANCING AREAS, or API QUOTA: "
        "use the corresponding SOAP tools (only available via SOAP)."
    )
else:
    _INSTRUCTIONS += (
        "No SOAP credentials configured — only public JSON tools are available. "
        "These cover searching power generation/consumption units, gas units, "
        "market actors, and grid connection points. For full unit details "
        "(EEG data, permits, CHP data), SOAP credentials (MASTR_USER + "
        "MASTR_TOKEN) must be configured in .env."
    )

mcp = FastMCP(
    "MaStR — Marktstammdatenregister",
    instructions=_INSTRUCTIONS,
    json_response=True,
)
