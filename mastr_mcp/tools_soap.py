"""SOAP-based MCP tools (require MASTR_USER + MASTR_TOKEN)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from pydantic import Field

from mastr_mcp.client import (
    client_actor,
    client_general,
    client_nap,
    client_plant,
    require_credentials,
    retry_soap,
)
from mastr_mcp.config import (
    MASTR_TOKEN,
    MASTR_USER,
    SOAP_TECHNOLOGY_MAP,
    TECH_SOAP_DISPATCH,
    resolve_tech_dispatch,
)
from mastr_mcp.serialization import serialize_soap
from mastr_mcp.server import mcp


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO date string to datetime, or return None."""
    return datetime.fromisoformat(value) if value else None


@mcp.tool()
def get_unit(
    unit_id: Annotated[
        str,
        Field(description="MaStR number of the unit, e.g. 'SEE966095906064'."),
    ],
    technology: Annotated[
        Optional[str],
        Field(
            description=(
                "Technology hint — any key from TECH_SOAP_DISPATCH, e.g.: "
                "'wind', 'solar', 'biomass', 'hydro', 'geo', 'storage', "
                "'natural_gas', 'hard_coal', 'lignite', 'nuclear', "
                "'hydrogen', 'combustion', 'mine_gas', 'sewage_sludge', "
                "'gas_storage', 'gas_production', 'gas_consumption', 'power_consumption'. "
                "German aliases also work (erdgas, steinkohle, braunkohle, etc.). "
                "If omitted, auto-detection via GetListeAlleEinheiten is attempted."
            ),
        ),
    ] = None,
) -> dict:
    """Get **full details** of a single unit by its MaStR number (SEE...).

    Use this when you already know a unit's MaStR number and need its complete
    master data. Returns capacity (kW), commissioning date, location, operator,
    EEG data, CHP data, permit data, and storage grouping — all in one call.

    Covers all unit types: wind, solar, biomass, hydro, storage, geothermal,
    gas, combustion (coal/gas/oil/waste/hydrogen), nuclear, and consumption units.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    # Auto-detect technology if not supplied
    if not technology:
        try:
            raw = retry_soap(
                client_plant().GetListeAlleEinheiten,
                {
                    "apiKey": MASTR_TOKEN,
                    "marktakteurMastrNummer": MASTR_USER,
                    "limit": 1,
                    "einheitMastrNummern": [unit_id],
                },
                max_attempts=3,
                label="GetListeAlleEinheiten",
            )
            if isinstance(raw, dict) and "error" not in raw:
                candidates = raw.get("Einheiten") or []
                if candidates:
                    einheit_typ = (
                        candidates[0].get("Einheittyp")
                        or candidates[0].get("Einheitart")
                    )
                    if einheit_typ:
                        technology = str(einheit_typ)
        except Exception:
            pass

    if not technology:
        return {
            "error": (
                "technology could not be auto-detected; please pass one of: "
                + ", ".join(sorted(set(TECH_SOAP_DISPATCH)))
            )
        }

    try:
        einheit_method, eeg_method = resolve_tech_dispatch(technology)
    except ValueError as exc:
        return {"error": str(exc)}

    client = client_plant()
    common = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "einheitMastrNummer": unit_id,
    }

    unit_dict = retry_soap(
        getattr(client, einheit_method),
        common,
        max_attempts=5,
        label=einheit_method,
    )
    if not isinstance(unit_dict, dict) or "error" in unit_dict:
        return unit_dict

    auth = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
    }

    # ── Load EEG data if available ──
    eeg_nr = unit_dict.get("EegMastrNummer")
    if eeg_nr and eeg_method:
        eeg_dict = retry_soap(
            getattr(client, eeg_method),
            {**auth, "eegMastrNummer": eeg_nr},
            max_attempts=5,
            label=eeg_method,
        )
        if isinstance(eeg_dict, dict) and "error" not in eeg_dict:
            eeg_dict.pop("VerknuepfteEinheit", None)
        unit_dict["eeg"] = eeg_dict

    # ── Load KWK (CHP) data if available ──
    kwk_nr = unit_dict.get("KwkMastrNummer")
    if kwk_nr:
        kwk_dict = retry_soap(
            client.GetAnlageKwk,
            {**auth, "kwkMastrNummer": kwk_nr},
            max_attempts=3,
            label="GetAnlageKwk",
        )
        if isinstance(kwk_dict, dict) and "error" not in kwk_dict:
            kwk_dict.pop("VerknuepfteEinheiten", None)
        unit_dict["kwk"] = kwk_dict

    # ── Load permit (Genehmigung) data if available ──
    gen_nr = unit_dict.get("GenMastrNummer")
    if gen_nr:
        gen_dict = retry_soap(
            client.GetEinheitGenehmigung,
            {**auth, "genMastrNummer": gen_nr},
            max_attempts=3,
            label="GetEinheitGenehmigung",
        )
        if isinstance(gen_dict, dict) and "error" not in gen_dict:
            gen_dict.pop("VerknuepfteEinheiten", None)
        unit_dict["genehmigung"] = gen_dict

    # ── Load storage grouping data if available ──
    spe_nr = unit_dict.get("SpeMastrNummer")
    if spe_nr:
        # Determine the right endpoint based on unit type prefix
        spe_method = "GetGasSpeicher" if spe_nr.startswith("G") else "GetStromSpeicher"
        spe_dict = retry_soap(
            getattr(client, spe_method),
            {**auth, "speMastrNummer": spe_nr},
            max_attempts=3,
            label=spe_method,
        )
        if isinstance(spe_dict, dict) and "error" not in spe_dict:
            spe_dict.pop("VerknuepfteEinheit", None)
        unit_dict["speicher"] = spe_dict

    return unit_dict


@mcp.tool()
def search_power_generation_soap(
    technology: Annotated[
        Optional[str],
        Field(
            description=(
                "Technology / energy carrier. Any key from SOAP_TECHNOLOGY_MAP: "
                "'wind', 'solar', 'biomass', 'hydro', 'geo', 'storage', "
                "'natural_gas', 'hard_coal', 'lignite', 'mineral_oil', "
                "'nuclear', 'hydrogen', 'heat', 'waste', 'other_gases', "
                "'mine_gas', 'sewage_sludge', 'solar_thermal', "
                "'pressure_relief_gas', 'pressure_relief_water'. "
                "German aliases also work (erdgas, steinkohle, braunkohle, etc.)."
            ),
        ),
    ] = None,
    postcode: Annotated[
        Optional[str], Field(description="Postal code.")
    ] = None,
    plant_name: Annotated[
        Optional[str], Field(description="Plant display name.")
    ] = None,
    min_capacity: Annotated[
        Optional[float],
        Field(description="Minimum brutto capacity in kW."),
    ] = None,
    max_capacity: Annotated[
        Optional[float],
        Field(description="Maximum brutto capacity in kW."),
    ] = None,
    min_commission_date: Annotated[
        Optional[str],
        Field(description="Earliest commissioning date (YYYY-MM-DD)."),
    ] = None,
    max_commission_date: Annotated[
        Optional[str],
        Field(description="Latest commissioning date (YYYY-MM-DD)."),
    ] = None,
    operator_id: Annotated[
        Optional[str],
        Field(description="Operator MaStR number (AnlagenbetreiberMastrNummer)."),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results (API cap is 2000).")
    ] = 2000,
) -> dict:
    """Search **power generation units** (Stromerzeugung) via SOAP with structured filters.

    Use this for filtered searches by technology, postcode, capacity range,
    commissioning date range, or operator. Returns MaStR numbers, names,
    and capacity for matching units. Supports all 20 energy carriers.

    Prefer search_power_generation_public (no auth needed) for simple searches.
    Use this SOAP variant when you need operator_id filtering or date ranges.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    tech_german: Optional[str] = None
    if technology:
        tech_german = SOAP_TECHNOLOGY_MAP.get(technology.lower())
        if tech_german is None:
            return {
                "error": (
                    f"Unknown technology '{technology}'. "
                    f"Valid: {sorted(set(SOAP_TECHNOLOGY_MAP.keys()))}"
                )
            }

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "limit": min(max(limit, 1), 2000),
        "energietraeger": tech_german,
        "name": plant_name,
        "postleitzahl": postcode,
        "bruttoleistungGroesser": min_capacity,
        "bruttoleistungKleiner": max_capacity,
        "inbetriebnahmedatumGroesser": _parse_date(min_commission_date),
        "inbetriebnahmedatumKleiner": _parse_date(max_commission_date),
        "AnlagenbetreiberMastrNummer": operator_id,
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    data = retry_soap(
        client_plant().GetGefilterteListeStromErzeuger,
        kwargs,
        max_attempts=5,
        label="GetGefilterteListeStromErzeuger",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    units = data.get("Einheiten") or []
    return {
        "count": len(units),
        "results": units,
        "meta": {k: v for k, v in data.items() if k != "Einheiten"},
    }


@mcp.tool()
def get_actor(
    actor_id: Annotated[
        str,
        Field(description="MaStR number of the market actor, e.g. 'SOM930870688704'."),
    ],
) -> dict:
    """Get **full details** of a single market actor by MaStR number (SOM..., ABR...).

    Returns name, address, contact data, market function, roles, registration
    date, and more. Use this when you know the actor's MaStR number.

    For searching actors by name/function/location, use search_actors_soap
    or search_actors_public instead.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    data = retry_soap(
        client_actor().GetMarktakteur,
        {
            "apiKey": MASTR_TOKEN,
            "marktakteurMastrNummer": MASTR_USER,
            "mastrNummer": actor_id,
        },
        max_attempts=3,
        label="GetMarktakteur",
    )
    if not isinstance(data, dict):
        return {"raw": data}
    return data


@mcp.tool()
def get_api_quota() -> dict:
    """Check how many SOAP API calls have been used today vs. the daily limit.

    Daily limit is 100,000 calls for regular users. Returns ``used`` and
    ``limit`` counts. Use this to monitor API quota before bulk operations.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()
    data = retry_soap(
        client_general().GetAktuellerStandTageskontingent,
        {
            "apiKey": MASTR_TOKEN,
            "marktakteurMastrNummer": MASTR_USER,
        },
        max_attempts=3,
        label="GetAktuellerStandTageskontingent",
    )
    if not isinstance(data, dict) or "error" in data:
        return data
    return {
        "used": data.get("AktuellerStandTageskontingent"),
        "limit": data.get("AktuellesLimitTageskontingent"),
    }


@mcp.tool()
def get_recent_changes(
    date_from: Annotated[
        str,
        Field(description="ISO date (YYYY-MM-DD) — only changes after this date."),
    ],
    object_type: Annotated[
        str,
        Field(
            description=(
                "Type of linked object to check for changes. One of: "
                "'EEG', 'KWK', 'Genehmigung', 'Lokation', 'Speicher', "
                "'Anlagenbetreiber', 'Netzbetreiberpruefungsprozess'."
            ),
        ),
    ],
    unit_type: Annotated[
        Optional[str],
        Field(
            description=(
                "Unit type filter (EinheitArtEnum), e.g. "
                "'Stromerzeugungseinheit', 'Stromverbrauchseinheit', "
                "'Gaserzeugungseinheit', 'Gasverbrauchseinheit'."
            ),
        ),
    ] = None,
    unit_ids: Annotated[
        Optional[list[str]],
        Field(description="Restrict to specific unit MaStR numbers."),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results (API cap is 2000).")
    ] = 2000,
) -> dict:
    """Find units whose linked objects were updated after a given date (delta sync).

    Returns units where EEG, KWK, permit, location, or storage data changed
    since ``date_from``. Use this for incremental data synchronization — e.g.
    "which EEG records changed since 2026-04-01?"

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "limit": min(max(limit, 1), 2000),
        "VerknuepftesObjektArt": object_type,
        "VerknuepftesObjektDatumAb": datetime.fromisoformat(date_from),
    }
    if unit_type:
        kwargs["Einheitart"] = unit_type
    if unit_ids:
        kwargs["EinheitMastrNummern"] = unit_ids

    data = retry_soap(
        client_plant().GetListeLetzteAktualisierung,
        kwargs,
        max_attempts=3,
        label="GetListeLetzteAktualisierung",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    units = data.get("Einheiten") or []
    return {
        "count": len(units),
        "results": units,
        "meta": {k: v for k, v in data.items() if k != "Einheiten"},
    }


@mcp.tool()
def search_power_consumption_soap(
    postcode: Annotated[
        Optional[str], Field(description="Postal code.")
    ] = None,
    name: Annotated[
        Optional[str], Field(description="Unit display name.")
    ] = None,
    city: Annotated[
        Optional[str], Field(description="City / Ort.")
    ] = None,
    district: Annotated[
        Optional[str], Field(description="Landkreis.")
    ] = None,
    municipality: Annotated[
        Optional[str], Field(description="Gemeinde.")
    ] = None,
    municipality_key: Annotated[
        Optional[str], Field(description="Gemeindeschlüssel.")
    ] = None,
    bundesland: Annotated[
        Optional[str],
        Field(description="Federal state (BundeslaenderEinheitenEnum), e.g. 'Bayern'."),
    ] = None,
    status: Annotated[
        Optional[str],
        Field(description="Operating status, e.g. 'InBetrieb'."),
    ] = None,
    min_large_consumers: Annotated[
        Optional[int],
        Field(description="Min number of connected consumers > 50 MW."),
    ] = None,
    max_large_consumers: Annotated[
        Optional[int],
        Field(description="Max number of connected consumers > 50 MW."),
    ] = None,
    min_commission_date: Annotated[
        Optional[str],
        Field(description="Earliest commissioning date (YYYY-MM-DD)."),
    ] = None,
    max_commission_date: Annotated[
        Optional[str],
        Field(description="Latest commissioning date (YYYY-MM-DD)."),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results (API cap is 2000).")
    ] = 2000,
) -> dict:
    """Search **power consumption units** (Stromverbrauch) via SOAP.

    Use this to find electricity consumers by postcode, city, federal state,
    status, or commissioning date. Returns MaStR numbers of matching units.

    Prefer search_power_consumption_public (no auth needed, 29 filter keys)
    for most searches. Use this SOAP variant for municipality_key or
    large_consumers filtering.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "limit": min(max(limit, 1), 2000),
        "einheitBetriebsstatus": status,
        "name": name,
        "postleitzahl": postcode,
        "ort": city,
        "Landkreis": district,
        "Gemeinde": municipality,
        "Gemeindeschluessel": municipality_key,
        "einheitBundesland": bundesland,
        "anzahlStromverbraucherGroesser50MwGroesser": min_large_consumers,
        "anzahlStromverbraucherGroesser50MwKleiner": max_large_consumers,
        "inbetriebnahmedatumGroesser": _parse_date(min_commission_date),
        "inbetriebnahmedatumKleiner": _parse_date(max_commission_date),
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    data = retry_soap(
        client_plant().GetGefilterteListeStromVerbraucher,
        kwargs,
        max_attempts=5,
        label="GetGefilterteListeStromVerbraucher",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    units = data.get("Einheiten") or []
    return {
        "count": len(units),
        "results": units,
        "meta": {k: v for k, v in data.items() if k != "Einheiten"},
    }


@mcp.tool()
def search_gas_production_soap(
    postcode: Annotated[
        Optional[str], Field(description="Postal code.")
    ] = None,
    name: Annotated[
        Optional[str], Field(description="Unit display name.")
    ] = None,
    city: Annotated[
        Optional[str], Field(description="City / Ort.")
    ] = None,
    district: Annotated[
        Optional[str], Field(description="Landkreis.")
    ] = None,
    municipality: Annotated[
        Optional[str], Field(description="Gemeinde.")
    ] = None,
    municipality_key: Annotated[
        Optional[str], Field(description="Gemeindeschlüssel.")
    ] = None,
    bundesland: Annotated[
        Optional[str],
        Field(description="Federal state (BundeslaenderEinheitenEnum), e.g. 'Bayern'."),
    ] = None,
    status: Annotated[
        Optional[str],
        Field(description="Operating status, e.g. 'InBetrieb'."),
    ] = None,
    min_capacity: Annotated[
        Optional[float],
        Field(description="Min gas production capacity (Erzeugungsleistung)."),
    ] = None,
    max_capacity: Annotated[
        Optional[float],
        Field(description="Max gas production capacity (Erzeugungsleistung)."),
    ] = None,
    min_commission_date: Annotated[
        Optional[str],
        Field(description="Earliest commissioning date (YYYY-MM-DD)."),
    ] = None,
    max_commission_date: Annotated[
        Optional[str],
        Field(description="Latest commissioning date (YYYY-MM-DD)."),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results (API cap is 2000).")
    ] = 2000,
) -> dict:
    """Search **gas production units** (Gaserzeugung) via SOAP.

    Use this to find gas producers (biogas, Power-to-Gas, LNG, fossil gas)
    by postcode, city, federal state, capacity, or commissioning date.

    Prefer search_gas_production_public (no auth needed, 30 filter keys)
    for most searches. Use this SOAP variant for capacity range filtering.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "limit": min(max(limit, 1), 2000),
        "einheitBetriebsstatus": status,
        "name": name,
        "postleitzahl": postcode,
        "ort": city,
        "Landkreis": district,
        "Gemeinde": municipality,
        "Gemeindeschluessel": municipality_key,
        "einheitBundesland": bundesland,
        "erzeugungsleistungGroesser": min_capacity,
        "erzeugungsleistungKleiner": max_capacity,
        "inbetriebnahmedatumGroesser": _parse_date(min_commission_date),
        "inbetriebnahmedatumKleiner": _parse_date(max_commission_date),
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    data = retry_soap(
        client_plant().GetGefilterteListeGasErzeuger,
        kwargs,
        max_attempts=5,
        label="GetGefilterteListeGasErzeuger",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    units = data.get("Einheiten") or []
    return {
        "count": len(units),
        "results": units,
        "meta": {k: v for k, v in data.items() if k != "Einheiten"},
    }


@mcp.tool()
def search_gas_consumption_soap(
    postcode: Annotated[
        Optional[str], Field(description="Postal code.")
    ] = None,
    name: Annotated[
        Optional[str], Field(description="Unit display name.")
    ] = None,
    city: Annotated[
        Optional[str], Field(description="City / Ort.")
    ] = None,
    district: Annotated[
        Optional[str], Field(description="Landkreis.")
    ] = None,
    municipality: Annotated[
        Optional[str], Field(description="Gemeinde.")
    ] = None,
    municipality_key: Annotated[
        Optional[str], Field(description="Gemeindeschlüssel.")
    ] = None,
    bundesland: Annotated[
        Optional[str],
        Field(description="Federal state (BundeslaenderEinheitenEnum), e.g. 'Bayern'."),
    ] = None,
    status: Annotated[
        Optional[str],
        Field(description="Operating status, e.g. 'InBetrieb'."),
    ] = None,
    min_capacity: Annotated[
        Optional[float],
        Field(description="Min gas consumption capacity (Bezugsleistung)."),
    ] = None,
    max_capacity: Annotated[
        Optional[float],
        Field(description="Max gas consumption capacity (Bezugsleistung)."),
    ] = None,
    min_commission_date: Annotated[
        Optional[str],
        Field(description="Earliest commissioning date (YYYY-MM-DD)."),
    ] = None,
    max_commission_date: Annotated[
        Optional[str],
        Field(description="Latest commissioning date (YYYY-MM-DD)."),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results (API cap is 2000).")
    ] = 2000,
) -> dict:
    """Search **gas consumption units** (Gasverbrauch) via SOAP.

    Use this to find gas consumers by postcode, city, federal state, capacity
    (Bezugsleistung), or commissioning date.

    Prefer search_gas_consumption_public (no auth needed, 30 filter keys)
    for most searches. Use this SOAP variant for capacity range filtering.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "limit": min(max(limit, 1), 2000),
        "einheitBetriebsstatus": status,
        "name": name,
        "postleitzahl": postcode,
        "ort": city,
        "Landkreis": district,
        "Gemeinde": municipality,
        "Gemeindeschluessel": municipality_key,
        "einheitBundesland": bundesland,
        "bezugsleistungGroesser": min_capacity,
        "bezugsleistungKleiner": max_capacity,
        "inbetriebnahmedatumGroesser": _parse_date(min_commission_date),
        "inbetriebnahmedatumKleiner": _parse_date(max_commission_date),
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    data = retry_soap(
        client_plant().GetGefilterteListeGasVerbraucher,
        kwargs,
        max_attempts=5,
        label="GetGefilterteListeGasVerbraucher",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    units = data.get("Einheiten") or []
    return {
        "count": len(units),
        "results": units,
        "meta": {k: v for k, v in data.items() if k != "Einheiten"},
    }


@mcp.tool()
def search_actors_soap(
    name: Annotated[
        Optional[str], Field(description="Actor name (company or person).")
    ] = None,
    postcode: Annotated[
        Optional[str], Field(description="Postal code.")
    ] = None,
    city: Annotated[
        Optional[str], Field(description="City / Ort.")
    ] = None,
    bundesland: Annotated[
        Optional[str],
        Field(description="Federal state, e.g. 'Bayern'."),
    ] = None,
    market_function: Annotated[
        Optional[str],
        Field(
            description=(
                "Market function (MarktfunktionEnum), e.g. "
                "'Stromnetzbetreiber', 'Gasnetzbetreiber', "
                "'Anlagenbetreiber', 'Stromlieferant', etc."
            ),
        ),
    ] = None,
    market_roles: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Market roles (MarktrollenEnum), e.g. "
                "['NetzbetreiberAnschlussnetzbetreiberStrom']."
            ),
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results (API cap is 2000).")
    ] = 2000,
) -> dict:
    """Search **market actors** (Marktakteure) via SOAP.

    Use this to find energy market participants — DSOs, generators, suppliers,
    traders — by name, postcode, city, federal state, market function, or
    market roles.  Returns more fields than search_actors_public, including
    non-public actor data.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "marktakteurMastrNummer": MASTR_USER,
        "limit": min(max(limit, 1), 2000),
        "name": name,
        "postleitzahl": postcode,
        "ort": city,
        "bundesland": bundesland,
        "marktfunktion": market_function,
    }
    if market_roles:
        kwargs["Marktrollen"] = market_roles
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    data = retry_soap(
        client_actor().GetGefilterteListeMarktakteure,
        kwargs,
        max_attempts=5,
        label="GetGefilterteListeMarktakteure",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    actors = data.get("Marktakteure") or []
    return {
        "count": len(actors),
        "results": actors,
        "meta": {k: v for k, v in data.items() if k != "Marktakteure"},
    }


@mcp.tool()
def get_location(
    location_id: Annotated[
        str,
        Field(
            description=(
                "MaStR number of the location, e.g. 'SEL978745131498' (power) "
                "or 'GEL...' (gas).  The type (StromErzeuger/StromVerbraucher/"
                "GasErzeuger/GasVerbraucher) is auto-detected from the prefix."
            ),
        ),
    ],
    location_type: Annotated[
        Optional[str],
        Field(
            description=(
                "Location type override. One of: 'power_generation', "
                "'power_consumption', 'gas_production', 'gas_consumption'. "
                "Usually not needed — auto-detected from the location MaStR number."
            ),
        ),
    ] = None,
) -> dict:
    """Get **location details** by MaStR location number (SEL.../GEL...).

    Returns the location name, all linked units at that location, and grid
    connection point data (voltage level, balancing area, control area,
    connection capacity). Auto-detects power vs. gas from the prefix.

    Use this when you have a location MaStR number and want to see what
    units are installed there and how they connect to the grid.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    _TYPE_MAP = {
        "power_generation": "GetLokationStromErzeuger",
        "power_consumption": "GetLokationStromVerbraucher",
        "gas_production": "GetLokationGasErzeuger",
        "gas_consumption": "GetLokationGasVerbraucher",
    }

    method: Optional[str] = None
    if location_type:
        method = _TYPE_MAP.get(location_type)
        if not method:
            return {
                "error": (
                    f"Unknown location_type '{location_type}'. "
                    f"Valid: {sorted(_TYPE_MAP.keys())}"
                )
            }
    else:
        # Auto-detect: SEL = Strom, GEL = Gas.  Default to power generation.
        if location_id.startswith("GEL"):
            method = "GetLokationGasErzeuger"
        else:
            method = "GetLokationStromErzeuger"

    data = retry_soap(
        getattr(client_plant(), method),
        {
            "apiKey": MASTR_TOKEN,
            "marktakteurMastrNummer": MASTR_USER,
            "lokationMastrNummer": location_id,
        },
        max_attempts=3,
        label=method,
    )
    if not isinstance(data, dict) or "error" in data:
        return data
    return data


@mcp.tool()
def get_catalog_values(
    category_id: Annotated[
        int,
        Field(
            description=(
                "Catalog category ID.  Use get_catalog_categories first to "
                "discover available categories and their IDs."
            ),
        ),
    ],
    limit: Annotated[
        int, Field(description="Maximum results.")
    ] = 2000,
) -> dict:
    """Look up valid enum/catalog values for a MaStR category (e.g. Rechtsform, Hersteller).

    Use ``get_catalog_categories`` first to discover available categories
    and their IDs, then call this with the category ID to get all valid values.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    data = retry_soap(
        client_general().GetKatalogwerte,
        {
            "apiKey": MASTR_TOKEN,
            "id": category_id,
            "limit": min(max(limit, 1), 2000),
        },
        max_attempts=3,
        label="GetKatalogwerte",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    values = data.get("Katalogwerte") or []
    return {
        "count": len(values),
        "results": values,
        "meta": {k: v for k, v in data.items() if k != "Katalogwerte"},
    }


@mcp.tool()
def get_catalog_categories(
    limit: Annotated[
        int, Field(description="Maximum results.")
    ] = 2000,
) -> dict:
    """List all available MaStR catalog categories with their IDs.

    Returns category names (e.g. Rechtsform, Energieträger, Betriebsstatus)
    and IDs. Use the IDs with ``get_catalog_values`` to get valid values.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    data = retry_soap(
        client_general().GetListeKatalogkategorien,
        {
            "apiKey": MASTR_TOKEN,
            "limit": min(max(limit, 1), 2000),
        },
        max_attempts=3,
        label="GetListeKatalogkategorien",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    categories = data.get("Katalogkategorien") or []
    return {
        "count": len(categories),
        "results": categories,
        "meta": {k: v for k, v in data.items() if k != "Katalogkategorien"},
    }


@mcp.tool()
def get_balancing_areas(
    dso_id: Annotated[
        Optional[str],
        Field(description="DSO MaStR number to filter by (optional)."),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum results.")
    ] = 2000,
) -> dict:
    """Get grid balancing areas (Bilanzierungsgebiete) with Y-EIC codes.

    Returns balancing area names, Y-EIC codes, and control areas
    (50Hertz, TenneT, Amprion, TransnetBW). Optionally filter by DSO.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    kwargs: dict[str, Any] = {
        "apiKey": MASTR_TOKEN,
        "limit": min(max(limit, 1), 2000),
    }
    if dso_id:
        kwargs["NetzbetreiberMastrNummer"] = dso_id

    data = retry_soap(
        client_general().GetBilanzierungsgebiete,
        kwargs,
        max_attempts=3,
        label="GetBilanzierungsgebiete",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    areas = data.get("Bilanzierungsgebiete") or []
    return {
        "count": len(areas),
        "results": areas,
        "meta": {k: v for k, v in data.items() if k != "Bilanzierungsgebiete"},
    }


# ─── Tool: get_grid_connection (Netzanschlusspunkte per Einheit) ──────────


@mcp.tool()
def get_grid_connection(
    unit_id: Annotated[
        str,
        Field(
            description=(
                "MaStR number of a unit (e.g. 'SEE966095906064'). "
                "Returns all grid connection points (Netzanschlusspunkte) "
                "linked to that unit, including location, voltage level, "
                "metering location, and co-located units."
            ),
        ),
    ],
) -> dict:
    """Get **grid connection points** (Netzanschlusspunkte) for a specific unit.

    Given a unit's MaStR number, returns all grid connection points linked
    to it: location name, voltage level, gas quality, metering location IDs,
    and all co-located units with their addresses.

    Use search_grid_connections_public to search grid connections by area
    (postcode, voltage level, etc.) without needing a specific unit ID.

    Requires SOAP credentials (MASTR_USER + MASTR_TOKEN).
    """
    require_credentials()

    data = retry_soap(
        client_nap().GetListeAlleNetzanschlusspunkte,
        {
            "apiKey": MASTR_TOKEN,
            "marktakteurMastrNummer": MASTR_USER,
            "einheitMastrNummer": unit_id,
        },
        max_attempts=3,
        label=f"GetListeAlleNetzanschlusspunkte({unit_id})",
    )
    if not isinstance(data, dict) or "error" in data:
        return data

    naps = data.get("ListeNetzanschlusspunkte") or []
    return {
        "unit_id": unit_id,
        "count": len(naps),
        "results": naps,
        "meta": {k: v for k, v in data.items() if k != "ListeNetzanschlusspunkte"},
    }
