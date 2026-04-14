# MaStR MCP Server

Ein MCP-Server für das **Marktstammdatenregister** (MaStR) der Bundesnetzagentur. Ermöglicht Claude Desktop, Cowork und Claude Code den direkten Zugriff auf das deutsche Energieanlagenregister.

## Features

### 21 Tools — 14 SOAP (mit Credentials), 7 Public (immer verfügbar)

| Tool | API | Auth | Beschreibung |
|---|---|---|---|
| `get_unit` | SOAP | Ja | Unit-Details + EEG + KWK + Genehmigung + Speicher in einem Aufruf |
| `search_power_generation_soap` | SOAP | Ja | Gefilterte Suche Stromerzeugung (alle 20 Energieträger, PLZ, Kapazität) |
| `get_actor` | SOAP | Ja | Marktakteur-Details per MaStR-Nr |
| `get_api_quota` | SOAP | Ja | Tägliches API-Kontingent (verbraucht / Limit) |
| `get_recent_changes` | SOAP | Ja | Delta-Sync: Änderungen seit Datum (EEG, KWK, Genehmigung, Lokation, Speicher) |
| `search_power_consumption_soap` | SOAP | Ja | Gefilterte Suche Stromverbrauch (PLZ, Bundesland, Status, etc.) |
| `search_gas_production_soap` | SOAP | Ja | Gefilterte Suche Gaserzeugung (Kapazität, PLZ, etc.) |
| `search_gas_consumption_soap` | SOAP | Ja | Gefilterte Suche Gasverbrauch (Kapazität, PLZ, etc.) |
| `search_actors_soap` | SOAP | Ja | Gefilterte Suche Marktakteure (Funktion, Rolle, PLZ, etc.) |
| `get_location` | SOAP | Ja | Lokations-Details inkl. Einheiten + Netzanschlusspunkte |
| `get_catalog_values` | SOAP | Ja | Katalogwerte (Rechtsform, Hersteller, etc.) per Kategorie-ID |
| `get_catalog_categories` | SOAP | Ja | Alle verfügbaren Katalogkategorien auflisten |
| `get_balancing_areas` | SOAP | Ja | Bilanzierungsgebiete (Y-EIC, Regelzonen), optional nach DSO |
| `get_grid_connection` | SOAP | Ja | Netzanschlusspunkte einer Einheit (Spannungsebene, Lokation, Co-Einheiten) |
| `search_power_generation_public` | JSON | Nein | Stromerzeugungseinheiten (27 Filter-Keys) |
| `search_actors_public` | JSON | Nein | Marktakteure (23 Filter-Keys) |
| `search_power_consumption_public` | JSON | Nein | Stromverbrauchseinheiten (29 Filter-Keys) |
| `search_gas_production_public` | JSON | Nein | Gaserzeugung/Gasspeicher (30 Filter-Keys) |
| `search_gas_consumption_public` | JSON | Nein | Gasverbrauchseinheiten (30 Filter-Keys) |
| `search_grid_connections_public` | JSON | Nein | Netzanschlusspunkte & Lokationen (4 Typen, 12-20 Filter-Keys) |
| `get_local_time` | SOAP | Nein | Verbindungstest (immer verfügbar) |

### 10 Filter-Operatoren

| Suffix | Operator | Beschreibung |
|---|---|---|
| *(keiner)* / `=` | eq | Gleich (Default) |
| `!=` | neq | Ungleich |
| `%` | ct | Enthält (contains) |
| `!%` | nct | Enthält nicht |
| `:` | sw | Beginnt mit |
| `$` | ew | Endet mit |
| `>` | gt | Größer als |
| `<` | lt | Kleiner als |
| `?` | null | Ist NULL |
| `!` / `!?` | nn | Ist NICHT NULL |

### 20 Energieträger

Alle Technologie-Keywords sind konsistent in Englisch verfügbar (deutsche Aliase funktionieren ebenfalls):

`wind`, `solar`, `biomass`, `hydro`, `storage`, `geo`, `mine_gas`, `sewage_sludge`,
`solar_thermal`, `pressure_relief_gas`/`pressure_relief_water`, `natural_gas`, `hard_coal`, `lignite`,
`mineral_oil`, `other_gases`, `waste`, `heat`, `hydrogen`, `nuclear`.

**Ohne Credentials** stehen 7 Public-Tools zur Verfügung (Suche Stromerzeugung, Stromverbrauch, Gaserzeugung, Gasverbrauch, Marktakteure, Netzanschlusspunkte + Verbindungstest). **Mit Credentials** (.env) werden zusätzlich 14 SOAP-Tools registriert (Detailabfragen, gefilterte Suchen, Kataloge, Bilanzierungsgebiete, etc.).

## Installation

### Voraussetzungen
- Python >= 3.10
- `uv` (empfohlen) oder `pip`
- MaStR Webdienst-Account (für SOAP-API Tools, optional): https://www.marktstammdatenregister.de

### Schritt 1: Projekt klonen / kopieren

```bash
git clone https://github.com/YOUR_USER/mastr-mcp-server.git
cd mastr-mcp-server
```

### Schritt 2: Abhängigkeiten installieren

**Mit uv (empfohlen):**
```bash
uv sync
```

**Mit pip:**
```bash
pip install -e .
```

### Schritt 3: Credentials in `.env` ablegen

Der Server lädt seine Credentials beim Start automatisch aus einer `.env` Datei
**im Projektordner** (über `python-dotenv`). Das ist der empfohlene Weg.

```bash
cp .env.example .env
# .env bearbeiten und Werte eintragen:
# MASTR_USER=SEM123456789012
# MASTR_TOKEN=dein-webdienst-token-540-zeichen
```

`.env` ist über `.gitignore` ausgeschlossen — der Token landet nicht im Repo.

**Alternative**: Du kannst die Variablen weiterhin als OS-Umgebungsvariablen
oder im `env`-Block der Claude Desktop Config setzen — OS-Werte haben Vorrang.

### Schritt 4: Testen

```bash
# Schnelltest
uv run mastr_mcp_server.py

# Oder mit dem MCP Inspector
npx @modelcontextprotocol/inspector uv run mastr_mcp_server.py
```

## Konfiguration für Claude Desktop / Cowork

Öffne die Claude Desktop Konfigurationsdatei:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Wenn `.env` im Projektordner liegt, kannst du den `env`-Block weglassen:

```json
{
  "mcpServers": {
    "mastr": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "C:\\Users\\DEIN_USER\\mastr-mcp-server",
        "mastr_mcp_server.py"
      ]
    }
  }
}
```

**Wichtig:** Passe den Pfad unter `--directory` an den tatsächlichen Speicherort an.

## Konfiguration für Claude Code

```bash
claude mcp add mastr \
  --command "uv" \
  --args "run" "--directory" "/pfad/zu/mastr-mcp-server" "mastr_mcp_server.py" \
  --env "MASTR_USER=SOM123456789012" \
  --env "MASTR_TOKEN=dein-webdienst-token"
```

## Beispiel-Nutzung in Claude

- *"Zeig mir die Details der Windanlage SEE966095906064"*
  → `get_unit`
- *"Suche alle Solaranlagen in PLZ 49074"*
  → `search_power_generation_public({'tech': 'solar', 'postcode': '49074'})`
- *"Windanlagen zwischen 1200 und 3500 kW im PLZ-Bereich 23..."*
  → `search_power_generation_public({'tech': 'wind', 'capacity>': 1200, 'capacity<': 3500, 'postcode:': '23'})`
- *"Windanlagen OHNE EEG-Schlüssel"*
  → `search_power_generation_public({'tech': 'wind', 'eeg_key?': ''})`
- *"Alle Nicht-Wind-Anlagen in PLZ 49074"*
  → `search_power_generation_public({'tech!=': '2497', 'postcode': '49074'})`
- *"Power-to-Gas Wasserstoff-Anlagen"*
  → `search_gas_production_public({'gas_technology': 'Power-to-Gas (Wasserstoff)'})`
- *"Hochspannungs-Verbraucher in Bayern"*
  → `search_power_consumption_public({'bundesland': 'Bayern', 'voltage_level': 'Hochspannung'})`
- *"Gasverbraucher mit H-Gas die Strom erzeugen"*
  → `search_gas_consumption_public({'gas_quality': 'H-Gas', 'gas_for_power': True})`
- *"DSOs mit mehr als 100.000 Kunden in Niedersachsen"*
  → `search_actors_public({'function': 'Stromnetzbetreiber', 'dso_large': True, 'bundesland': 'Niedersachsen'})`
- *"Netzanschlusspunkte Stromerzeugung in PLZ 49074 auf Mittelspannung"*
  → `search_grid_connections_public('power_generation', {'postcode': '49074', 'voltage_level': 'Mittelspannung'})`
- *"Gas-Einspeisepunkte mit H-Gas"*
  → `search_grid_connections_public('gas_production', {'gas_quality': 'H-Gas'})`

## Projektstruktur

```
mastr-mcp-server/
├── mastr_mcp_server.py           # Entry-Point (importiert Package, startet Server)
├── mastr_mcp/                     # Haupt-Package
│   ├── __init__.py               # Package-Init, Tool-Registrierung
│   ├── config.py                 # Konstanten, Env-Vars, Technologie-Mappings
│   ├── serialization.py          # SOAP→JSON, MS-AJAX-Datumskonvertierung
│   ├── client.py                 # SOAP-Client, HTTP-Fetch, Retry-Helper
│   ├── filters.py                # Filter-Builder, Spalten-Mappings, Dropdown-Laden
│   ├── server.py                 # FastMCP-Instanz
│   ├── tools_soap.py             # SOAP-Tools (14)
│   ├── tools_public.py           # Public JSON-Tools (7)
│   └── resources.py              # MCP Resources (4)
├── *_dropdowns.json               # Dropdown-ID-Mappings (5 Dateien, aus Live-API)
├── pyproject.toml                 # Abhängigkeiten
├── .env                           # Credentials (nicht in Git)
└── .env.example                  # Vorlage für Credentials
```

## Sicherheitshinweise

- Der MaStR-Token ist vertraulich — er gehört in `.env`, **niemals** ins Repo.
- Der Server macht nur lesende Zugriffe (keine Registrierungen oder Änderungen)
- Tageslimit: 100.000 SOAP-API-Aufrufe pro Benutzer (Public JSON unlimitiert)
- Nur TLS 1.2 Verbindungen werden akzeptiert

## Lizenz

MIT
