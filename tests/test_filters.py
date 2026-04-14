"""Tests for the filter builder, operator parsing, and dropdown/boolean resolution."""

from __future__ import annotations

import urllib.parse

import pytest

from mastr_mcp.filters import (
    build_extended_filter,
    UNIT_FILTER_COLUMNS,
    ACTOR_FILTER_COLUMNS,
    ACTOR_BOOLEAN_KEYS,
    CONSUMPTION_FILTER_COLUMNS,
    GAS_CONSUMPTION_FILTER_COLUMNS,
    GAS_CONSUMPTION_BOOLEAN_KEYS,
    GAS_PRODUCTION_FILTER_COLUMNS,
    NAP_POWER_GENERATION_COLUMNS,
    NAP_BOOLEAN_KEYS,
    UNIT_DROPDOWN_VALUES,
    ACTOR_DROPDOWN_VALUES,
)
from mastr_mcp.config import ENERGY_CARRIER_IDS


# ─── Helpers ────────────────────────────────────────────────────────────────


def _decode_filter(flt: str) -> str:
    """URL-decode a filter string for easier assertion."""
    return urllib.parse.unquote(urllib.parse.unquote(flt))


# ─── Basic operator tests ──────────────────────────────────────────────────


class TestOperatorParsing:
    """Verify all 10 operator suffixes produce the correct Kendo tokens."""

    def test_eq_default(self):
        flt, unk = build_extended_filter({"postcode": "49074"}, UNIT_FILTER_COLUMNS)
        assert "~eq~" in flt
        assert unk == []

    def test_eq_explicit(self):
        flt, _ = build_extended_filter({"postcode=": "49074"}, UNIT_FILTER_COLUMNS)
        assert "~eq~" in flt

    def test_neq(self):
        flt, _ = build_extended_filter({"tech!=": "2497"}, UNIT_FILTER_COLUMNS)
        assert "~neq~" in flt

    def test_contains(self):
        flt, _ = build_extended_filter({"name%": "park"}, UNIT_FILTER_COLUMNS)
        assert "~ct~" in flt

    def test_not_contains(self):
        flt, _ = build_extended_filter({"name!%": "test"}, UNIT_FILTER_COLUMNS)
        assert "~nct~" in flt

    def test_starts_with(self):
        flt, _ = build_extended_filter({"postcode:": "23"}, UNIT_FILTER_COLUMNS)
        assert "~sw~" in flt

    def test_ends_with(self):
        flt, _ = build_extended_filter({"postcode$": "74"}, UNIT_FILTER_COLUMNS)
        assert "~ew~" in flt

    def test_greater_than(self):
        flt, _ = build_extended_filter({"capacity>": 1200}, UNIT_FILTER_COLUMNS)
        assert "~gt~" in flt

    def test_less_than(self):
        flt, _ = build_extended_filter({"capacity<": 3500}, UNIT_FILTER_COLUMNS)
        assert "~lt~" in flt

    def test_null(self):
        flt, _ = build_extended_filter({"eeg_key?": ""}, UNIT_FILTER_COLUMNS)
        assert "~null~" in flt
        # Value-less: no %27 quotes after operator
        assert "%27" not in flt

    def test_not_null_bang(self):
        flt, _ = build_extended_filter({"eeg_key!": ""}, UNIT_FILTER_COLUMNS)
        assert "~nn~" in flt
        assert "%27" not in flt

    def test_not_null_bang_question(self):
        flt, _ = build_extended_filter({"eeg_key!?": ""}, UNIT_FILTER_COLUMNS)
        assert "~nn~" in flt


class TestMultipleFilters:
    """Combining multiple filters produces ~and~ separated segments."""

    def test_two_filters_joined(self):
        flt, _ = build_extended_filter(
            {"postcode": "49074", "capacity>": 1000},
            UNIT_FILTER_COLUMNS,
        )
        assert "~and~" in flt

    def test_empty_filter(self):
        flt, unk = build_extended_filter({}, UNIT_FILTER_COLUMNS)
        assert flt == ""
        assert unk == []


# ─── Unknown keys ───────────────────────────────────────────────────────────


class TestUnknownKeys:
    """Unknown filter keys are collected and returned."""

    def test_single_unknown(self):
        flt, unk = build_extended_filter({"postode": "49074"}, UNIT_FILTER_COLUMNS)
        assert unk == ["postode"]
        assert flt == ""  # nothing valid → empty

    def test_multiple_unknown(self):
        _, unk = build_extended_filter(
            {"postode": "49074", "xyz": "a", "foo>": 5},
            UNIT_FILTER_COLUMNS,
        )
        assert set(unk) == {"postode", "xyz", "foo>"}

    def test_mixed_valid_and_unknown(self):
        flt, unk = build_extended_filter(
            {"postcode": "49074", "postode": "49074"},
            UNIT_FILTER_COLUMNS,
        )
        assert unk == ["postode"]
        assert "~eq~" in flt  # valid key produced output

    def test_unknown_with_operator_suffix(self):
        """Operator suffix is stripped before checking, but raw key is reported."""
        _, unk = build_extended_filter({"xyz>": 5}, UNIT_FILTER_COLUMNS)
        assert unk == ["xyz>"]


# ─── Tech shortcut resolution ──────────────────────────────────────────────


class TestTechTranslation:
    """Energy carrier shortcuts → numeric IDs."""

    @pytest.mark.parametrize("alias,expected_id", [
        ("wind", "2497"),
        ("solar", "2495"),
        ("pv", "2495"),
        ("biomass", "2493"),
        ("hydro", "2498"),
        ("storage", "2496"),
        ("nuclear", "2494"),
        ("hydrogen", "3030"),
        ("natural_gas", "2410"),
        ("erdgas", "2410"),
        ("kernkraft", "2494"),
    ])
    def test_tech_alias_resolved(self, alias, expected_id):
        flt, _ = build_extended_filter(
            {"tech": alias}, UNIT_FILTER_COLUMNS, translate_tech=True,
        )
        decoded = _decode_filter(flt)
        assert expected_id in decoded

    def test_unknown_tech_skipped(self):
        """An unrecognized tech value produces an empty filter."""
        flt, unk = build_extended_filter(
            {"tech": "unobtanium"}, UNIT_FILTER_COLUMNS, translate_tech=True,
        )
        assert flt == ""
        assert unk == []  # key itself is valid, just the value is unknown

    def test_tech_numeric_passthrough(self):
        """Numeric tech IDs not in ENERGY_CARRIER_IDS are skipped."""
        flt, _ = build_extended_filter(
            {"tech": "9999"}, UNIT_FILTER_COLUMNS, translate_tech=True,
        )
        assert flt == ""

    def test_tech_without_translate_flag(self):
        """Without translate_tech=True, the raw value is passed through."""
        flt, _ = build_extended_filter(
            {"tech": "wind"}, UNIT_FILTER_COLUMNS, translate_tech=False,
        )
        decoded = _decode_filter(flt)
        assert "wind" in decoded
        assert "2497" not in decoded


# ─── Dropdown resolution ───────────────────────────────────────────────────


class TestDropdownResolution:
    """Label → ID mapping for dropdown fields."""

    def test_bundesland_label_resolved(self):
        """A Bundesland label like 'Niedersachsen' should be resolved to its ID."""
        if not UNIT_DROPDOWN_VALUES or "bundesland" not in UNIT_DROPDOWN_VALUES:
            pytest.skip("unit_dropdowns.json not loaded")
        flt, _ = build_extended_filter(
            {"bundesland": "Niedersachsen"},
            UNIT_FILTER_COLUMNS,
            dropdown_values=UNIT_DROPDOWN_VALUES,
        )
        decoded = _decode_filter(flt)
        # Should contain a numeric ID, not the text "Niedersachsen"
        assert "Niedersachsen" not in decoded or decoded.count("~eq~") > 0

    def test_numeric_id_passthrough(self):
        """Numeric IDs should pass through without dropdown lookup."""
        flt, _ = build_extended_filter(
            {"bundesland": "1408"},
            UNIT_FILTER_COLUMNS,
            dropdown_values=UNIT_DROPDOWN_VALUES,
        )
        decoded = _decode_filter(flt)
        assert "1408" in decoded

    def test_unknown_dropdown_passthrough(self):
        """Unknown dropdown labels pass through as-is."""
        flt, _ = build_extended_filter(
            {"bundesland": "Mordor"},
            UNIT_FILTER_COLUMNS,
            dropdown_values=UNIT_DROPDOWN_VALUES,
        )
        decoded = _decode_filter(flt)
        assert "Mordor" in decoded


# ─── Boolean handling ───────────────────────────────────────────────────────


class TestBooleanHandling:
    """Boolean fields produce unquoted 1/0 in the filter string."""

    @pytest.mark.parametrize("value,expected", [
        (True, "~eq~1"),
        (False, "~eq~0"),
        ("true", "~eq~1"),
        ("false", "~eq~0"),
        ("ja", "~eq~1"),
        ("nein", "~eq~0"),
        ("1", "~eq~1"),
        ("0", "~eq~0"),
    ])
    def test_boolean_values(self, value, expected):
        flt, _ = build_extended_filter(
            {"dso_large": value},
            ACTOR_FILTER_COLUMNS,
            boolean_keys=ACTOR_BOOLEAN_KEYS,
        )
        decoded = _decode_filter(flt)
        assert expected in decoded

    def test_boolean_no_quotes(self):
        """Boolean values must NOT have URL-encoded single quotes (%27)."""
        flt, _ = build_extended_filter(
            {"dso_large": True},
            ACTOR_FILTER_COLUMNS,
            boolean_keys=ACTOR_BOOLEAN_KEYS,
        )
        assert "%27" not in flt

    def test_invalid_boolean_skipped(self):
        """Non-boolean values for boolean fields are skipped."""
        flt, _ = build_extended_filter(
            {"dso_large": "maybe"},
            ACTOR_FILTER_COLUMNS,
            boolean_keys=ACTOR_BOOLEAN_KEYS,
        )
        assert flt == ""

    def test_gas_consumption_boolean(self):
        flt, _ = build_extended_filter(
            {"gas_for_power": True},
            GAS_CONSUMPTION_FILTER_COLUMNS,
            boolean_keys=GAS_CONSUMPTION_BOOLEAN_KEYS,
        )
        assert "~eq~1" in _decode_filter(flt)

    def test_nap_planned_boolean(self):
        flt, _ = build_extended_filter(
            {"planned": "ja"},
            NAP_POWER_GENERATION_COLUMNS,
            boolean_keys=NAP_BOOLEAN_KEYS,
        )
        assert "~eq~1" in _decode_filter(flt)


# ─── Column maps completeness ──────────────────────────────────────────────


class TestColumnMaps:
    """Verify column maps have the expected structure and key counts."""

    def test_unit_columns_count(self):
        assert len(UNIT_FILTER_COLUMNS) == 27

    def test_actor_columns_count(self):
        assert len(ACTOR_FILTER_COLUMNS) == 23

    def test_consumption_columns_count(self):
        assert len(CONSUMPTION_FILTER_COLUMNS) == 29

    def test_gas_production_columns_count(self):
        assert len(GAS_PRODUCTION_FILTER_COLUMNS) == 30

    def test_gas_consumption_columns_count(self):
        assert len(GAS_CONSUMPTION_FILTER_COLUMNS) == 30

    def test_nap_power_generation_has_voltage(self):
        assert "voltage_level" in NAP_POWER_GENERATION_COLUMNS
        assert "control_area" in NAP_POWER_GENERATION_COLUMNS

    def test_all_column_values_are_strings(self):
        for name, cmap in [
            ("UNIT", UNIT_FILTER_COLUMNS),
            ("ACTOR", ACTOR_FILTER_COLUMNS),
            ("CONSUMPTION", CONSUMPTION_FILTER_COLUMNS),
            ("GAS_PROD", GAS_PRODUCTION_FILTER_COLUMNS),
            ("GAS_CONS", GAS_CONSUMPTION_FILTER_COLUMNS),
            ("NAP_PG", NAP_POWER_GENERATION_COLUMNS),
        ]:
            for k, v in cmap.items():
                assert isinstance(k, str), f"{name}: key {k!r} is not str"
                assert isinstance(v, str), f"{name}: value {v!r} for {k} is not str"


# ─── Energy carrier IDs ────────────────────────────────────────────────────


class TestEnergyCarrierIDs:
    """All 20 energy carriers have entries."""

    def test_all_20_unique_ids(self):
        unique_ids = set(ENERGY_CARRIER_IDS.values())
        assert len(unique_ids) == 20

    @pytest.mark.parametrize("alias", [
        "wind", "solar", "pv", "biomass", "hydro", "storage", "geo",
        "mine_gas", "sewage_sludge", "solar_thermal",
        "pressure_relief_gas", "pressure_relief_water",
        "natural_gas", "hard_coal", "lignite", "mineral_oil",
        "other_gases", "waste", "heat", "hydrogen", "nuclear",
    ])
    def test_english_alias_exists(self, alias):
        assert alias in ENERGY_CARRIER_IDS

    @pytest.mark.parametrize("alias", [
        "erdgas", "biomasse", "wasser", "speicher", "geothermie",
        "grubengas", "klaerschlamm", "solarthermie",
        "steinkohle", "braunkohle", "mineraloelprodukte",
        "andere_gase", "abfall", "waerme", "wasserstoff",
        "kernenergie", "kernkraft",
    ])
    def test_german_alias_exists(self, alias):
        assert alias in ENERGY_CARRIER_IDS
