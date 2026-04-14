"""Filter builder, column mappings, and dropdown resolution for public MaStR API."""

from __future__ import annotations

import json as _json
import logging
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from mastr_mcp.config import ENERGY_CARRIER_IDS

logger = logging.getLogger("mastr-mcp")

# ─── Filter operators ────────────────────────────────────────────────────────
#
# Operator suffixes appended to filter keys by the caller:
#   Single-char:  '='  '%'  '>'  '<'  ':'  '$'  '?'  '!'
#   Two-char:     '!=' '!%' '!?'
#
# Two-char suffixes are checked first so '!=' is not confused with '!'.

FILTER_OPS_2CHAR: dict[str, str] = {
    "!=": "~neq~",   # not equal
    "!%": "~nct~",   # not contains
    "!?": "~nn~",    # is not null (value-less)
}

FILTER_OPS_1CHAR: dict[str, str] = {
    "=": "~eq~",     # equal (default)
    "%": "~ct~",     # contains
    ">": "~gt~",     # greater than
    "<": "~lt~",     # less than
    ":": "~sw~",     # starts with
    "$": "~ew~",     # ends with
    "?": "~null~",   # is null (value-less)
    "!": "~nn~",     # is not null (value-less) — single-char alias
}

# Operators where MaStR expects no value (just ColumnName~op~).
VALUE_LESS_OPS: set[str] = {"~null~", "~nn~"}


# ─── Boolean normalization ───────────────────────────────────────────────────

_BOOLEAN_TRUE = {"1", "true", "yes", "ja", "wahr"}
_BOOLEAN_FALSE = {"0", "false", "no", "nein", "falsch"}


# ─── Filter column maps ─────────────────────────────────────────────────────
# Labels must match byte-for-byte what MaStR's GetFilterColumns* returns.

UNIT_FILTER_COLUMNS: dict[str, str] = {
    # Core identification
    "tech": "Energieträger",
    "name": "Anzeige-Name der Einheit",
    "eeg_key": "EEG-Anlagenschlüssel",
    "mastr_number": "MaStR-Nr. der Einheit",
    "mastr_operator": "MaStR-Nr. des Anlagenbetreibers",
    # Capacity
    "capacity": "Bruttoleistung der Einheit",
    "capacity_netto": "Nettonennleistung der Einheit",
    # Location
    "postcode": "Postleitzahl",
    "city": "Ort",
    "landkreis": "Landkreis",
    "street": "Straße",
    "bundesland": "Bundesland",
    "longitude": "Koordinate: Längengrad (WGS84)",
    "latitude": "Koordinate: Breitengrad (WGS84)",
    # Dates / status
    "status": "Betriebs-Status",
    "commission_date": "Inbetriebnahmedatum der Einheit",
    "eeg_commission_date": "Inbetriebnahmedatum der EEG-Anlage",
    # Operator
    "operator_name": "Name des Anlagenbetreibers (nur Org.)",
    # Wind
    "wind_park": "Name des Windparks",
    "wind_manufacturer": "Hersteller der Windenergieanlage",
    "hub_height": "Nabenhöhe der Windenergieanlage",
    "rotor_diameter": "Rotordurchmesser der Windenergieanlage",
    # Solar
    "solar_park": "Name des Solarparks",
    # Storage
    "storage_capacity": "Nutzbare Speicherkapazität in kWh",
    "storage_mastr_number": "MaStR-Nr. der Speichereinheit",
    "storage_technology": "Speichertechnologie",
    "battery_technology": "Batterietechnologie",
}

ACTOR_FILTER_COLUMNS: dict[str, str] = {
    # Identification
    "name": "Name des Marktakteurs",
    "mastr_number": "MaStR-Nr.",
    "bnetza_number": "BNetzA-Betriebsnummer",
    "acer_code": "ACER-Code",
    "vat_id": "Umsatzsteueridentifikationsnummer",
    "register_court": "Registergericht",
    "register_number": "Registernummer",
    # Function / role
    "function": "Marktfunktion",
    "roles": "Marktrollen",
    "industry_group": "Hauptwirtschaftszweig: Gruppe",
    # Location
    "postcode": "Postleitzahl",
    "city": "Ort",
    "street": "Straße",
    "bundesland": "Bundesland",
    "nuts_region": "NUTS-II-Region",
    # Status / dates
    "status": "Tätigkeitsstatus",
    "registration_date": "Registrierungsdatum",
    "last_update": "Datum der letzten Aktualisierung",
    "activity_start": "Tätigkeitsbeginn",
    "activity_end": "Tätigkeitsende",
    # DSO / company flags (booleans)
    "dso_large": "Netz: Mehr als 100.000 Kunden?",
    "dso_closed": "Netz: Geschlossenes  Verteilernetz?",
    "sme_flag": "Kleinst-, Klein- oder mittleres Unternehmen?",
}

ACTOR_BOOLEAN_KEYS: set[str] = {"dso_large", "dso_closed", "sme_flag"}

# ─── Stromverbrauch (power consumption) ─────────────────────────────────────

CONSUMPTION_FILTER_COLUMNS: dict[str, str] = {
    "name": "Anzeige-Name der Einheit",
    "mastr_number": "MaStR-Nr. der Einheit",
    "mastr_operator": "MaStR-Nr. des Anlagenbetreibers",
    "location_mastr": "MaStR-Nr. der Lokation",
    "dso_mastr": "MaStR-Nr. des Anschluss-Netzbetreibers",
    "operator_name": "Name des Anlagenbetreibers (nur Org.)",
    "dso_name": "Name des Anschluss-Netzbetreibers",
    # Location
    "postcode": "Postleitzahl",
    "city": "Ort",
    "landkreis": "Landkreis",
    "street": "Straße",
    "bundesland": "Bundesland",
    "municipality": "Gemeinde",
    "municipality_key": "Gemeindeschlüssel",
    "landmark": "Gemarkung",
    "parcel": "Flurstück",
    "country": "Land",
    "longitude": "Koordinate: Längengrad (WGS84)",
    "latitude": "Koordinate: Breitengrad (WGS84)",
    # Dates / status
    "status": "Betriebs-Status",
    "commission_date": "Inbetriebnahmedatum der Einheit",
    "current_location_date": "Inbetriebnahmedatum der Einheit am aktuellen Standort",
    "shutdown_date": "Datum der endgültigen Stilllegung",
    "planned_date": "Datum der geplanten Inbetriebnahme",
    "registration_date": "Registrierungsdatum der Einheit",
    "last_update": "Letzte Aktualisierung",
    # Specifics
    "large_consumers": "Anzahl angeschlossener Stromverbrauchseinheiten größer 50 MW",
    "voltage_level": "Spannungsebene des Netzanschlusses",
    "dso_check": "Netzbetreiberprüfung",
}

# ─── Gaserzeugung (gas production) ──────────────────────────────────────────

GAS_PRODUCTION_FILTER_COLUMNS: dict[str, str] = {
    "name": "Anzeige-Name der Einheit",
    "mastr_number": "MaStR-Nr. der Einheit",
    "mastr_operator": "MaStR-Nr. des Anlagenbetreibers",
    "location_mastr": "MaStR-Nr. der Lokation",
    "dso_mastr": "MaStR-Nr. des Anschluss-Netzbetreibers",
    "operator_name": "Name des Anlagenbetreibers (nur Org.)",
    "dso_name": "Name des Anschluss-Netzbetreibers",
    # Location
    "postcode": "Postleitzahl",
    "city": "Ort",
    "landkreis": "Landkreis",
    "street": "Straße",
    "bundesland": "Bundesland",
    "municipality": "Gemeinde",
    "municipality_key": "Gemeindeschlüssel",
    "landmark": "Gemarkung",
    "parcel": "Flurstück",
    "country": "Land",
    "longitude": "Koordinate: Längengrad (WGS84)",
    "latitude": "Koordinate: Breitengrad (WGS84)",
    # Dates / status
    "status": "Betriebs-Status",
    "commission_date": "Inbetriebnahmedatum der Einheit",
    "current_location_date": "Inbetriebnahmedatum der Einheit am aktuellen Standort",
    "shutdown_date": "Datum der endgültigen Stilllegung",
    "planned_date": "Datum der geplanten Inbetriebnahme",
    "registration_date": "Registrierungsdatum der Einheit",
    "last_update": "Letzte Aktualisierung",
    # Specifics
    "gas_production_capacity": "Gaserzeugungsleistung",
    "gas_technology": "Technologie",
    "unit_type": "Typ der Einheit",
    "dso_check": "Netzbetreiberprüfung",
}

# ─── Gasverbrauch (gas consumption) ─────────────────────────────────────────

GAS_CONSUMPTION_FILTER_COLUMNS: dict[str, str] = {
    "name": "Anzeige-Name der Einheit",
    "mastr_number": "MaStR-Nr. der Einheit",
    "mastr_operator": "MaStR-Nr. des Anlagenbetreibers",
    "location_mastr": "MaStR-Nr. der Lokation",
    "dso_mastr": "MaStR-Nr. des Anschluss-Netzbetreibers",
    "operator_name": "Name des Anlagenbetreibers (nur Org.)",
    "dso_name": "Name des Anschluss-Netzbetreibers",
    # Location
    "postcode": "Postleitzahl",
    "city": "Ort",
    "landkreis": "Landkreis",
    "street": "Straße",
    "bundesland": "Bundesland",
    "municipality": "Gemeinde",
    "municipality_key": "Gemeindeschlüssel",
    "landmark": "Gemarkung",
    "parcel": "Flurstück",
    "country": "Land",
    "longitude": "Koordinate: Längengrad (WGS84)",
    "latitude": "Koordinate: Breitengrad (WGS84)",
    # Dates / status
    "status": "Betriebs-Status",
    "commission_date": "Inbetriebnahmedatum der Einheit",
    "current_location_date": "Inbetriebnahmedatum der Einheit am aktuellen Standort",
    "shutdown_date": "Datum der endgültigen Stilllegung",
    "planned_date": "Datum der geplanten Inbetriebnahme",
    "registration_date": "Registrierungsdatum der Einheit",
    "last_update": "Letzte Aktualisierung",
    # Specifics
    "max_gas_capacity": "Maximale Gasbezugsleistung",
    "gas_quality": "Gasqualität des Netzes",
    "gas_for_power": "Gasverbrauch dient der Stromerzeugung",
    "dso_check": "Netzbetreiberprüfung",
}

GAS_CONSUMPTION_BOOLEAN_KEYS: set[str] = {"gas_for_power"}

# ─── Netzanschlusspunkte & Lokationen (grid connection points) ─────────────

# Shared base fields across all 4 NAP endpoints.
# These endpoints use the raw API field names as Kendo filter keys (no
# GetFilterColumns endpoint exists).
_NAP_BASE_COLUMNS: dict[str, str] = {
    "location_mastr": "LokationMaStRNummer",
    "location_name": "LokationName",
    "nap_mastr": "NetzanschlusspunktMaStRNummer",
    "nap_name": "NetzanschlusspunktBezeichnung",
    "dso_mastr": "NetzbetreiberMaStRNummer",
    "dso_name": "NetzbetreiberName",
    "unit_mastr": "EinheitenMaStRNummern",
    "postcode": "Postleitzahl",
    "city": "Ort",
    "municipality": "Gemeinde",
    "municipality_key": "Gemeindeschluessel",
    "planned": "IsGeplant",
}

# Strom-Erzeugung specific
NAP_POWER_GENERATION_COLUMNS: dict[str, str] = {
    **_NAP_BASE_COLUMNS,
    "unit_types": "EinheitenTypen",
    "capacity": "Nettoengpassleistung",
    "voltage_level": "Spannungsebene",
    "voltage_level_id": "SpannungsebeneDovId",
    "control_area": "Regelzone",
    "control_area_id": "RegelzoneDovId",
    "balancing_area": "Bilanzierungsgebiet",
    "metering_location": "Messlokation",
}

# Strom-Verbrauch specific
NAP_POWER_CONSUMPTION_COLUMNS: dict[str, str] = {
    **_NAP_BASE_COLUMNS,
    "capacity": "Netzanschlusskapazitaet",
    "voltage_level": "Spannungsebene",
    "voltage_level_id": "SpannungsebeneDovId",
    "control_area": "Regelzone",
    "control_area_id": "RegelzoneDovId",
    "balancing_area": "Bilanzierungsgebiet",
    "metering_location": "Messlokation",
}

# Gas-Erzeugung specific
NAP_GAS_PRODUCTION_COLUMNS: dict[str, str] = {
    **_NAP_BASE_COLUMNS,
    "capacity": "MaximaleEinspeiseleistung",
    "gas_quality": "Gasqualitaet",
    "gas_quality_id": "GasqualitaetDovId",
    "market_area": "Marktgebiet",
    "market_area_id": "MarktgebietDovId",
}

# Gas-Verbrauch specific
NAP_GAS_CONSUMPTION_COLUMNS: dict[str, str] = {
    **_NAP_BASE_COLUMNS,
    "capacity": "MaximaleAusspeiseleistung",
    "gas_quality": "Gasqualitaet",
    "gas_quality_id": "GasqualitaetDovId",
    "market_area": "Marktgebiet",
    "market_area_id": "MarktgebietDovId",
}

# Dispatching: type keyword → (endpoint, column_map)
NAP_TYPE_DISPATCH: dict[str, tuple[str, dict[str, str]]] = {
    "power_generation": (
        "GetOeffentlicheNetzanschlusspunkteUndLokationenStromerzeugung",
        NAP_POWER_GENERATION_COLUMNS,
    ),
    "power_consumption": (
        "GetOeffentlicheNetzanschlusspunkteUndLokationenStromverbrauch",
        NAP_POWER_CONSUMPTION_COLUMNS,
    ),
    "gas_production": (
        "GetOeffentlicheNetzanschlusspunkteUndLokationenGaserzeugung",
        NAP_GAS_PRODUCTION_COLUMNS,
    ),
    "gas_consumption": (
        "GetOeffentlicheNetzanschlusspunkteUndLokationenGasverbrauch",
        NAP_GAS_CONSUMPTION_COLUMNS,
    ),
}

NAP_BOOLEAN_KEYS: set[str] = {"planned"}


# ─── Dropdown loading ────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dropdowns(filename: str, label: str) -> dict[str, dict[str, str]]:
    """Load a bundled dropdown-ID mapping JSON file.

    Keys are lowercased German labels (fullwidth '\\uff06' normalized to '&'),
    values are the numeric MaStR IDs the Kendo filter expects.
    """
    path = _PROJECT_ROOT / filename
    if not path.is_file():
        logger.warning(
            "%s not found — dropdown filters for %s will pass through unchanged.",
            filename,
            label,
        )
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            return _json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load %s: %s", filename, exc)
        return {}


UNIT_DROPDOWN_VALUES = _load_dropdowns("unit_dropdowns.json", "units")
ACTOR_DROPDOWN_VALUES = _load_dropdowns("actor_dropdowns.json", "actors")
CONSUMPTION_DROPDOWN_VALUES = _load_dropdowns("consumption_dropdowns.json", "consumption")
GAS_PRODUCTION_DROPDOWN_VALUES = _load_dropdowns("gas_production_dropdowns.json", "gas production")
GAS_CONSUMPTION_DROPDOWN_VALUES = _load_dropdowns("gas_consumption_dropdowns.json", "gas consumption")


# ─── Filter builder ──────────────────────────────────────────────────────────


def build_extended_filter(
    dic_filter: dict[str, Any],
    column_map: dict[str, str],
    *,
    translate_tech: bool = False,
    dropdown_values: Optional[dict[str, dict[str, str]]] = None,
    boolean_keys: Optional[set[str]] = None,
) -> tuple[str, list[str]]:
    """Build a Kendo-style filter string from a user-friendly filter dict.

    Operator suffixes on keys (two-char checked first):
        '='   → eq (default)     '!='  → neq (not equal)
        '%'   → ct (contains)    '!%'  → nct (not contains)
        '>'   → gt               '!?'  → nn  (is not null)
        '<'   → lt               '?'   → null (is null)
        ':'   → sw (starts with) '!'   → nn  (is not null, alias)
        '$'   → ew (ends with)

    ``null`` and ``nn`` operators produce value-less filter segments.

    ``dropdown_values`` translates human-readable labels → numeric IDs.
    ``boolean_keys`` normalizes truthy/falsy inputs to unquoted 1/0.

    Returns a tuple of (filter_string, unknown_keys).
    """
    parts: list[str] = []
    unknown_keys: list[str] = []
    for raw_key, raw_value in dic_filter.items():
        key = raw_key
        op = "~eq~"

        # Parse operator suffix: check two-char first, then one-char.
        if len(key) >= 2 and key[-2:] in FILTER_OPS_2CHAR:
            op = FILTER_OPS_2CHAR[key[-2:]]
            key = key[:-2]
        elif key and key[-1] in FILTER_OPS_1CHAR:
            op = FILTER_OPS_1CHAR[key[-1]]
            key = key[:-1]

        if key not in column_map:
            unknown_keys.append(raw_key)
            continue

        column_encoded = urllib.parse.quote(column_map[key], safe="")

        # Value-less operators (null / nn): just column~op~, no value.
        if op in VALUE_LESS_OPS:
            parts.append(f"{column_encoded}{op}")
            continue

        value = raw_value

        # Tech shortcut resolution (energy carrier name → numeric ID).
        if translate_tech and key == "tech":
            mapped = ENERGY_CARRIER_IDS.get(str(value).lower())
            if mapped is None:
                continue
            value = mapped

        # Dropdown label → numeric ID resolution.
        if dropdown_values and key in dropdown_values:
            svalue = str(value)
            if not svalue.isdigit():
                mapped = dropdown_values[key].get(svalue.lower())
                if mapped is None:
                    logger.info(
                        "Dropdown value %r not in map for %s — passing through as-is",
                        svalue,
                        key,
                    )
                else:
                    value = mapped

        # Boolean columns: MaStR expects unquoted 1/0 and only makes sense with eq.
        if boolean_keys and key in boolean_keys:
            token = str(value).strip().lower()
            if isinstance(raw_value, bool):
                bool_val = "1" if raw_value else "0"
            elif token in _BOOLEAN_TRUE:
                bool_val = "1"
            elif token in _BOOLEAN_FALSE:
                bool_val = "0"
            else:
                logger.info(
                    "Boolean filter %s got non-boolean value %r — skipping",
                    key,
                    raw_value,
                )
                continue
            parts.append(f"{column_encoded}~eq~{bool_val}")
            continue

        if not isinstance(value, str):
            value = str(value)

        value_encoded = urllib.parse.quote_plus(value)
        # MaStR requires string values wrapped in URL-encoded single quotes (%27).
        parts.append(f"{column_encoded}{op}%27{value_encoded}%27")

    return "~and~".join(parts), unknown_keys
