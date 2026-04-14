"""Configuration, constants, and technology mappings for the MaStR MCP Server."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger("mastr-mcp")

# ─── .env and credentials ───────────────────────────────────────────────────

# Load .env from the *project root* (one level above this package).
# Existing OS env vars take precedence (override=False).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.is_file():
    load_dotenv(_ENV_PATH, override=False)
    logger.info("Loaded credentials from %s", _ENV_PATH)

MASTR_USER: str = os.environ.get("MASTR_USER", "")
MASTR_TOKEN: str = os.environ.get("MASTR_TOKEN", "")
MASTR_WSDL_URL: str = os.environ.get(
    "MASTR_WSDL_URL",
    "https://www.marktstammdatenregister.de/MaStRAPI/wsdl/mastr.wsdl",
)

# ─── Public JSON API base URLs ──────────────────────────────────────────────

MASTR_JSON_UNIT_BASE = (
    "https://www.marktstammdatenregister.de/MaStR/Einheit/EinheitJson"
)
MASTR_JSON_ACTOR_BASE = (
    "https://www.marktstammdatenregister.de/MaStR/Akteur/MarktakteurJson"
)
MASTR_JSON_NAP_BASE = (
    "https://www.marktstammdatenregister.de/MaStR/Einheit"
    "/NetzanschlusspunkteUndLokationenJson"
)

# ─── Energy carrier IDs (public JSON API) ────────────────────────────────────

# All 20 Energieträger from the
# GetFilterColumnsErweiterteOeffentlicheEinheitStromerzeugung endpoint.
# Multiple aliases point to the same ID for user convenience.
ENERGY_CARRIER_IDS: dict[str, str] = {
    # Erneuerbare
    "wind": "2497",
    "solar": "2495", "pv": "2495",
    "biomass": "2493", "biomasse": "2493",
    "hydro": "2498", "wasser": "2498",
    "storage": "2496", "speicher": "2496", "stromspeicher": "2496",
    "geo": "2403", "geothermie": "2403",
    "grubengas": "2406", "mine_gas": "2406",
    "klaerschlamm": "2405", "sewage_sludge": "2405",
    "solarthermie": "2404", "solar_thermal": "2404",
    "druckentspannung_gas": "2957", "pressure_relief_gas": "2957",
    "druckentspannung_wasser": "2958", "pressure_relief_water": "2958",
    # Konventionelle Stromerzeugung
    "erdgas": "2410", "natural_gas": "2410",
    "steinkohle": "2407", "hard_coal": "2407",
    "braunkohle": "2408", "lignite": "2408",
    "mineraloelprodukte": "2409", "mineraloel": "2409", "mineral_oil": "2409",
    "andere_gase": "2411", "other_gases": "2411",
    "abfall": "2412", "waste": "2412",
    "waerme": "2413", "heat": "2413",
    "wasserstoff": "3030", "hydrogen": "3030",
    "kernenergie": "2494", "kernkraft": "2494", "nuclear": "2494",
}

# ─── SOAP technology map (GetGefilterteListeStromErzeuger) ───────────────────

# Maps user-friendly keys → German SOAP parameter values.
SOAP_TECHNOLOGY_MAP: dict[str, str] = {
    # Erneuerbare
    "wind": "Wind",
    "solar": "SolareStrahlungsenergie", "pv": "SolareStrahlungsenergie",
    "biomass": "Biomasse", "biomasse": "Biomasse",
    "hydro": "Wasser", "wasser": "Wasser",
    "geo": "Geothermie", "geothermal": "Geothermie", "geothermie": "Geothermie",
    "storage": "Speicher", "speicher": "Speicher", "stromspeicher": "Speicher",
    "grubengas": "Grubengas", "mine_gas": "Grubengas",
    "klaerschlamm": "Klaerschlamm", "sewage_sludge": "Klaerschlamm",
    "solarthermie": "Solarthermie", "solar_thermal": "Solarthermie",
    "druckentspannung_gas": "DruckAusGasleitungen", "pressure_relief_gas": "DruckAusGasleitungen",
    "druckentspannung_wasser": "DruckAusWasserleitungen", "pressure_relief_water": "DruckAusWasserleitungen",
    # Konventionelle
    "erdgas": "Erdgas", "natural_gas": "Erdgas",
    "steinkohle": "Steinkohle", "hard_coal": "Steinkohle",
    "braunkohle": "Braunkohle", "lignite": "Braunkohle",
    "mineraloelprodukte": "Mineraloelprodukte", "mineraloel": "Mineraloelprodukte", "mineral_oil": "Mineraloelprodukte",
    "andere_gase": "AndereGase", "other_gases": "AndereGase",
    "abfall": "NichtBiogenerAbfall", "waste": "NichtBiogenerAbfall",
    "waerme": "Waerme", "heat": "Waerme",
    "wasserstoff": "Wasserstoff", "hydrogen": "Wasserstoff",
    "kernenergie": "Kernenergie", "kernkraft": "Kernenergie", "nuclear": "Kernenergie",
}

# ─── SOAP technology dispatching for get_unit ────────────────────────────────

# Maps technology keywords → (GetEinheit* method, GetAnlageEeg* method or None).
# Keys are checked via exact match first, then longest-substring-first fallback
# (so "wasserstoff" matches before "wasser", "gasspeicher" before "speicher").

_GEO_EINHEIT = "GetEinheitGeothermieGrubengasDruckentspannung"
_GEO_EEG = "GetAnlageEegGeothermieGrubengasDruckentspannung"

TECH_SOAP_DISPATCH: dict[str, tuple[str, Optional[str]]] = {
    # Erneuerbare (with EEG endpoints)
    "wind": ("GetEinheitWind", "GetAnlageEegWind"),
    "solar": ("GetEinheitSolar", "GetAnlageEegSolar"),
    "pv": ("GetEinheitSolar", "GetAnlageEegSolar"),
    "biomass": ("GetEinheitBiomasse", "GetAnlageEegBiomasse"),
    "biomasse": ("GetEinheitBiomasse", "GetAnlageEegBiomasse"),
    "hydro": ("GetEinheitWasser", "GetAnlageEegWasser"),
    "wasser": ("GetEinheitWasser", "GetAnlageEegWasser"),
    "geo": (_GEO_EINHEIT, _GEO_EEG),
    "geothermie": (_GEO_EINHEIT, _GEO_EEG),
    "grubengas": (_GEO_EINHEIT, _GEO_EEG), "mine_gas": (_GEO_EINHEIT, _GEO_EEG),
    "klaerschlamm": (_GEO_EINHEIT, _GEO_EEG), "sewage_sludge": (_GEO_EINHEIT, _GEO_EEG),
    "solarthermie": (_GEO_EINHEIT, _GEO_EEG), "solar_thermal": (_GEO_EINHEIT, _GEO_EEG),
    "druckentspannung": (_GEO_EINHEIT, _GEO_EEG), "pressure_relief": (_GEO_EINHEIT, _GEO_EEG),
    "storage": ("GetEinheitStromSpeicher", "GetAnlageEegSpeicher"),
    "speicher": ("GetEinheitStromSpeicher", "GetAnlageEegSpeicher"),
    "stromspeicher": ("GetEinheitStromSpeicher", "GetAnlageEegSpeicher"),
    # Konventionelle Stromerzeugung (no EEG)
    "verbrennung": ("GetEinheitVerbrennung", None), "combustion": ("GetEinheitVerbrennung", None),
    "erdgas": ("GetEinheitVerbrennung", None), "natural_gas": ("GetEinheitVerbrennung", None),
    "braunkohle": ("GetEinheitVerbrennung", None), "lignite": ("GetEinheitVerbrennung", None),
    "steinkohle": ("GetEinheitVerbrennung", None), "hard_coal": ("GetEinheitVerbrennung", None),
    "kohle": ("GetEinheitVerbrennung", None), "coal": ("GetEinheitVerbrennung", None),
    "mineraloelprodukte": ("GetEinheitVerbrennung", None), "mineral_oil": ("GetEinheitVerbrennung", None),
    "mineraloel": ("GetEinheitVerbrennung", None),
    "abfall": ("GetEinheitVerbrennung", None), "waste": ("GetEinheitVerbrennung", None),
    "waerme": ("GetEinheitVerbrennung", None), "heat": ("GetEinheitVerbrennung", None),
    "wasserstoff": ("GetEinheitVerbrennung", None), "hydrogen": ("GetEinheitVerbrennung", None),
    "andere_gase": ("GetEinheitVerbrennung", None), "other_gases": ("GetEinheitVerbrennung", None),
    # Kernkraft (no EEG)
    "kernkraft": ("GetEinheitKernkraft", None),
    "kernenergie": ("GetEinheitKernkraft", None),
    "nuclear": ("GetEinheitKernkraft", None),
    # Gas-Einheiten (no EEG, separate SOAP endpoints)
    "gasspeicher": ("GetEinheitGasSpeicher", None), "gas_storage": ("GetEinheitGasSpeicher", None),
    "gaserzeugung": ("GetEinheitGasErzeuger", None), "gas_production": ("GetEinheitGasErzeuger", None),
    "gasverbrauch": ("GetEinheitGasVerbraucher", None), "gas_consumption": ("GetEinheitGasVerbraucher", None),
    # Strom-Verbrauch (no EEG)
    "stromverbrauch": ("GetEinheitStromVerbraucher", None), "power_consumption": ("GetEinheitStromVerbraucher", None),
}

# Pre-sorted keys: longest first to avoid partial matches.
_TECH_DISPATCH_KEYS_BY_LEN = sorted(TECH_SOAP_DISPATCH, key=len, reverse=True)


def resolve_tech_dispatch(technology: str) -> tuple[str, Optional[str]]:
    """Resolve a technology hint to (GetEinheit* method, GetAnlageEeg* method).

    Tries exact dict match first, then longest-substring-first fallback to
    handle auto-detected technology strings like 'WindAnLand' or 'Verbrennung'.
    """
    tech_lower = technology.lower()
    if tech_lower in TECH_SOAP_DISPATCH:
        return TECH_SOAP_DISPATCH[tech_lower]
    for key in _TECH_DISPATCH_KEYS_BY_LEN:
        if key in tech_lower:
            return TECH_SOAP_DISPATCH[key]
    raise ValueError(
        f"Unknown technology: {technology!r}. "
        f"Valid hints: {', '.join(sorted(set(TECH_SOAP_DISPATCH)))}"
    )
