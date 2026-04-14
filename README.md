# MaStR MCP Server

An MCP server for the **Marktstammdatenregister** (MaStR) — the German energy market master data register operated by the Bundesnetzagentur (Federal Network Agency). Enables Claude Desktop, Cowork, and Claude Code to directly access the German energy plant registry.

[Deutsche Version / German version](README_de.md)

## Features

### 21 Tools — 14 SOAP (with credentials), 7 Public (always available)

| Tool | API | Auth | Description |
|---|---|---|---|
| `get_unit` | SOAP | Yes | Full unit details + EEG + CHP + permit + storage in one call |
| `search_power_generation_soap` | SOAP | Yes | Filtered search for power generation (all 20 energy carriers, postcode, capacity) |
| `get_actor` | SOAP | Yes | Market actor details by MaStR number |
| `get_api_quota` | SOAP | Yes | Daily API quota (used / limit) |
| `get_recent_changes` | SOAP | Yes | Delta sync: changes since date (EEG, CHP, permit, location, storage) |
| `search_power_consumption_soap` | SOAP | Yes | Filtered search for power consumers (postcode, state, status, etc.) |
| `search_gas_production_soap` | SOAP | Yes | Filtered search for gas production (capacity, postcode, etc.) |
| `search_gas_consumption_soap` | SOAP | Yes | Filtered search for gas consumers (capacity, postcode, etc.) |
| `search_actors_soap` | SOAP | Yes | Filtered search for market actors (function, role, postcode, etc.) |
| `get_location` | SOAP | Yes | Location details incl. linked units + grid connection points |
| `get_catalog_values` | SOAP | Yes | Catalog/enum values (legal form, manufacturer, etc.) by category ID |
| `get_catalog_categories` | SOAP | Yes | List all available catalog categories |
| `get_balancing_areas` | SOAP | Yes | Balancing areas (Y-EIC codes, control areas), optionally by DSO |
| `get_grid_connection` | SOAP | Yes | Grid connection points for a unit (voltage level, location, co-located units) |
| `search_power_generation_public` | JSON | No | Power generation units (27 filter keys) |
| `search_actors_public` | JSON | No | Market actors (23 filter keys) |
| `search_power_consumption_public` | JSON | No | Power consumption units (29 filter keys) |
| `search_gas_production_public` | JSON | No | Gas production / gas storage (30 filter keys) |
| `search_gas_consumption_public` | JSON | No | Gas consumption units (30 filter keys) |
| `search_grid_connections_public` | JSON | No | Grid connection points & locations (4 types, 12-20 filter keys) |
| `get_local_time` | SOAP | No | Connection test (always available) |

### 10 Filter Operators

| Suffix | Operator | Description |
|---|---|---|
| *(none)* / `=` | eq | Equal (default) |
| `!=` | neq | Not equal |
| `%` | ct | Contains |
| `!%` | nct | Does not contain |
| `:` | sw | Starts with |
| `$` | ew | Ends with |
| `>` | gt | Greater than |
| `<` | lt | Less than |
| `?` | null | Is NULL |
| `!` / `!?` | nn | Is NOT NULL |

### 20 Energy Carriers

All technology keywords are available in English (German aliases also work):

`wind`, `solar`, `biomass`, `hydro`, `storage`, `geo`, `mine_gas`, `sewage_sludge`,
`solar_thermal`, `pressure_relief_gas`/`pressure_relief_water`, `natural_gas`, `hard_coal`, `lignite`,
`mineral_oil`, `other_gases`, `waste`, `heat`, `hydrogen`, `nuclear`.

**Without credentials**, 7 public tools are available (search power generation, power consumption, gas production, gas consumption, market actors, grid connections + connection test). **With credentials** (.env), 14 additional SOAP tools are registered (detail queries, filtered searches, catalogs, balancing areas, etc.).

## Installation

### Prerequisites
- Python >= 3.10
- `uv` (recommended) or `pip`
- MaStR web service account (for SOAP API tools, optional): https://www.marktstammdatenregister.de

### Step 1: Clone / copy project

```bash
git clone https://github.com/UliRCS/mastr-mcp-server.git
cd mastr-mcp-server
```

### Step 2: Install dependencies

**With uv (recommended):**
```bash
uv sync
```

**With pip:**
```bash
pip install -e .
```

### Step 3: Store credentials in `.env`

The server automatically loads credentials from a `.env` file **in the project directory** (via `python-dotenv`). This is the recommended approach.

```bash
cp .env.example .env
# Edit .env and fill in your values:
# MASTR_USER=SEM123456789012
# MASTR_TOKEN=your-webservice-token-540-chars
```

`.env` is excluded via `.gitignore` — your token will not end up in the repo.

**Alternative**: You can also set the variables as OS environment variables or in the `env` block of the Claude Desktop config — OS values take precedence.

### Step 4: Test

```bash
# Quick test
uv run mastr_mcp_server.py

# Or with the MCP Inspector
npx @modelcontextprotocol/inspector uv run mastr_mcp_server.py
```

## Configuration for Claude Desktop / Cowork

Open the Claude Desktop configuration file:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

If `.env` is in the project directory, you can omit the `env` block:

```json
{
  "mcpServers": {
    "mastr": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/mastr-mcp-server",
        "mastr_mcp_server.py"
      ]
    }
  }
}
```

**Important:** Adjust the path under `--directory` to the actual location on your system.

## Configuration for Claude Code

```bash
claude mcp add mastr \
  --command "uv" \
  --args "run" "--directory" "/path/to/mastr-mcp-server" "mastr_mcp_server.py" \
  --env "MASTR_USER=SOM123456789012" \
  --env "MASTR_TOKEN=your-webservice-token"
```

## Usage Examples

- *"Show me the details of wind turbine SEE966095906064"*
  -> `get_unit`
- *"Find all solar plants in postcode 49074"*
  -> `search_power_generation_public({'tech': 'solar', 'postcode': '49074'})`
- *"Wind turbines between 1200 and 3500 kW in postcode area 23..."*
  -> `search_power_generation_public({'tech': 'wind', 'capacity>': 1200, 'capacity<': 3500, 'postcode:': '23'})`
- *"Wind turbines WITHOUT EEG key"*
  -> `search_power_generation_public({'tech': 'wind', 'eeg_key?': ''})`
- *"All non-wind units in postcode 49074"*
  -> `search_power_generation_public({'tech!=': '2497', 'postcode': '49074'})`
- *"Power-to-Gas hydrogen plants"*
  -> `search_gas_production_public({'gas_technology': 'Power-to-Gas (Wasserstoff)'})`
- *"High-voltage consumers in Bavaria"*
  -> `search_power_consumption_public({'bundesland': 'Bayern', 'voltage_level': 'Hochspannung'})`
- *"Gas consumers with H-Gas that generate electricity"*
  -> `search_gas_consumption_public({'gas_quality': 'H-Gas', 'gas_for_power': True})`
- *"DSOs with more than 100,000 connected customers in Lower Saxony"*
  -> `search_actors_public({'function': 'Stromnetzbetreiber', 'dso_large': True, 'bundesland': 'Niedersachsen'})`
- *"Grid connection points for power generation in postcode 49074 at medium voltage"*
  -> `search_grid_connections_public('power_generation', {'postcode': '49074', 'voltage_level': 'Mittelspannung'})`
- *"Gas feed-in points with H-Gas"*
  -> `search_grid_connections_public('gas_production', {'gas_quality': 'H-Gas'})`

## Project Structure

```
mastr-mcp-server/
├── mastr_mcp_server.py           # Entry point (imports package, starts server)
├── mastr_mcp/                     # Main package
│   ├── __init__.py               # Package init, conditional tool registration
│   ├── config.py                 # Constants, env vars, technology mappings
│   ├── serialization.py          # SOAP->JSON, MS-AJAX date conversion
│   ├── client.py                 # SOAP client, HTTP fetch, retry helper
│   ├── filters.py                # Filter builder, column mappings, dropdown loading
│   ├── server.py                 # FastMCP instance with instructions
│   ├── tools_soap.py             # SOAP tools (14)
│   ├── tools_public.py           # Public JSON tools (7)
│   └── resources.py              # MCP Resources (4)
├── *_dropdowns.json               # Dropdown ID mappings (5 files, from live API)
├── pyproject.toml                 # Dependencies and metadata
├── .env                           # Credentials (not in git)
└── .env.example                  # Credential template
```

## Security Notes

- The MaStR token is confidential — it belongs in `.env`, **never** in the repo.
- The server only performs read operations (no registrations or modifications)
- Daily limit: 100,000 SOAP API calls per user (public JSON is unlimited)
- Only TLS 1.2 connections are accepted

## License

MIT
