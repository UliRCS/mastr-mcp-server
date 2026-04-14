"""MaStR MCP Server — Marktstammdatenregister integration for Claude."""

from mastr_mcp.server import mcp  # noqa: F401 — FastMCP instance
from mastr_mcp.config import MASTR_USER, MASTR_TOKEN

# Always register public tools (no auth required) and resources.
import mastr_mcp.tools_public  # noqa: F401
import mastr_mcp.resources  # noqa: F401

# Register SOAP tools only when credentials are configured.
if MASTR_USER and MASTR_TOKEN:
    import mastr_mcp.tools_soap  # noqa: F401
