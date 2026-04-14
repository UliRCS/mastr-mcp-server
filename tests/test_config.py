"""Tests for config module: technology dispatch, SOAP mapping."""

from __future__ import annotations

import pytest

from mastr_mcp.config import (
    ENERGY_CARRIER_IDS,
    SOAP_TECHNOLOGY_MAP,
    TECH_SOAP_DISPATCH,
    resolve_tech_dispatch,
)


# ─── resolve_tech_dispatch ──────────────────────────────────────────────────


class TestResolveTechDispatch:
    """Technology hint → (GetEinheit*, GetAnlageEeg*) resolution."""

    @pytest.mark.parametrize("tech,expected_einheit", [
        ("wind", "GetEinheitWind"),
        ("solar", "GetEinheitSolar"),
        ("pv", "GetEinheitSolar"),
        ("biomass", "GetEinheitBiomasse"),
        ("hydro", "GetEinheitWasser"),
        ("storage", "GetEinheitStromSpeicher"),
        ("geo", "GetEinheitGeothermieGrubengasDruckentspannung"),
        ("nuclear", "GetEinheitKernkraft"),
        ("natural_gas", "GetEinheitVerbrennung"),
        ("hydrogen", "GetEinheitVerbrennung"),
    ])
    def test_exact_match(self, tech, expected_einheit):
        einheit, _ = resolve_tech_dispatch(tech)
        assert einheit == expected_einheit

    def test_case_insensitive(self):
        einheit, _ = resolve_tech_dispatch("Wind")
        assert einheit == "GetEinheitWind"

    def test_substring_fallback_windanland(self):
        """Auto-detected strings like 'WindAnLand' match via substring."""
        einheit, eeg = resolve_tech_dispatch("WindAnLand")
        assert einheit == "GetEinheitWind"
        assert eeg == "GetAnlageEegWind"

    def test_substring_wasserstoff_before_wasser(self):
        """'wasserstoff' must match Verbrennung, not Wasser (longest match)."""
        einheit, eeg = resolve_tech_dispatch("Wasserstoff")
        assert einheit == "GetEinheitVerbrennung"
        assert eeg is None

    def test_substring_gasspeicher_before_speicher(self):
        """'gasspeicher' must match GasSpeicher, not StromSpeicher."""
        einheit, _ = resolve_tech_dispatch("Gasspeicher")
        assert einheit == "GetEinheitGasSpeicher"

    def test_unknown_technology_raises(self):
        with pytest.raises(ValueError, match="Unknown technology"):
            resolve_tech_dispatch("unobtanium")

    def test_renewables_have_eeg(self):
        """Wind, solar, biomass, hydro, storage should all have EEG methods."""
        for tech in ["wind", "solar", "biomass", "hydro", "storage"]:
            _, eeg = resolve_tech_dispatch(tech)
            assert eeg is not None, f"{tech} should have an EEG method"

    def test_conventional_no_eeg(self):
        """Conventional fuels should have no EEG method."""
        for tech in ["natural_gas", "hard_coal", "lignite", "nuclear", "hydrogen"]:
            _, eeg = resolve_tech_dispatch(tech)
            assert eeg is None, f"{tech} should not have an EEG method"


# ─── SOAP_TECHNOLOGY_MAP ────────────────────────────────────────────────────


class TestSoapTechnologyMap:
    """All 20 energy carriers have SOAP technology values."""

    def test_all_20_unique_soap_values(self):
        unique_values = set(SOAP_TECHNOLOGY_MAP.values())
        assert len(unique_values) == 20

    def test_wind_value(self):
        assert SOAP_TECHNOLOGY_MAP["wind"] == "Wind"

    def test_solar_value(self):
        assert SOAP_TECHNOLOGY_MAP["solar"] == "SolareStrahlungsenergie"

    def test_aliases_resolve_same(self):
        assert SOAP_TECHNOLOGY_MAP["solar"] == SOAP_TECHNOLOGY_MAP["pv"]
        assert SOAP_TECHNOLOGY_MAP["erdgas"] == SOAP_TECHNOLOGY_MAP["natural_gas"]
        assert SOAP_TECHNOLOGY_MAP["kernkraft"] == SOAP_TECHNOLOGY_MAP["nuclear"]


# ─── Cross-consistency ──────────────────────────────────────────────────────


class TestCrossConsistency:
    """All three mapping dicts share the same set of primary English keys."""

    ENGLISH_PRIMARIES = {
        "wind", "solar", "pv", "biomass", "hydro", "storage", "geo",
        "mine_gas", "sewage_sludge", "solar_thermal",
        "pressure_relief_gas", "pressure_relief_water",
        "natural_gas", "hard_coal", "lignite", "mineral_oil",
        "other_gases", "waste", "heat", "hydrogen", "nuclear",
    }

    def test_energy_carrier_ids_cover_primaries(self):
        missing = self.ENGLISH_PRIMARIES - set(ENERGY_CARRIER_IDS)
        assert missing == set(), f"Missing in ENERGY_CARRIER_IDS: {missing}"

    def test_soap_technology_map_cover_primaries(self):
        missing = self.ENGLISH_PRIMARIES - set(SOAP_TECHNOLOGY_MAP)
        assert missing == set(), f"Missing in SOAP_TECHNOLOGY_MAP: {missing}"
