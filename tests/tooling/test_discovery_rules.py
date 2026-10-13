"""Configurable comment recognition preserves source facts and assignment priority."""

import json
from dataclasses import replace

import pytest

from app.gcode.execution.program import execute_program
from app.settings import get_settings
from app.tools import discovery
from app.tools.definitions import MILLING_TOOL_TYPES, TURNING_TOOL_TYPES
from app.tools.discovery import _scan_source_python, discover_tools
from app.tools.discovery_patterns import type_hint
from app.tools.discovery_rules import (
    SETTINGS_KEY,
    default_profile,
    default_settings,
    load_settings,
    validate_profile,
    validate_settings,
)
from app.tools.setup import refresh_setup


def custom_profile(kind="mill_ball"):
    profile = default_profile()
    for entry in profile["types"]:
        if entry[1] == kind:
            entry[0] = r"\bSPECIAL\b"
    profile["dimensions"]["milling_diameter"] = "SIZE"
    return profile


@pytest.mark.parametrize("turning,types", [(False, MILLING_TOOL_TYPES), (True, TURNING_TOOL_TYPES)])
def test_all_existing_types_can_be_configured(turning, types):
    for kind in types:
        rules = custom_profile(kind)
        source = "T0101 (SPECIAL)\nG1 X20 F100" if turning else "T1 M6 (SPECIAL SIZE=8)\nG1 X2 F100"
        tools = discover_tools(source, turning=turning, rules=rules)
        spec = tools["T0101" if turning else "T1"]
        assert spec["type"] == kind
        if not turning:
            assert spec["diameter"] == 8


@pytest.mark.parametrize("native", [False, True])
def test_custom_nearby_comment_and_cycle_priority(monkeypatch, native):
    if not native:
        monkeypatch.setattr(discovery, "_native_scan_source", None)
    rules = custom_profile()
    source = "G21\nT1 M6\nM8 (SPECIAL SIZE8)\nT2 M6\nG81 Z-2 R1 F100"
    tools = discover_tools(source, turning=False, rules=rules)
    assert tools["T2"]["type"] == "drill"
    assert tools["T2"]["diameter"] == 8
    assert tools["T1"]["type"] == "mill_flat"


def test_native_custom_scan_matches_python():
    native = pytest.importorskip("app.tools._native_discovery")
    if native.COMMENT_HINTS_VERSION < 3:
        pytest.skip("Native discovery must be rebuilt for custom comment predicates")

    def predicate(text):
        return "SPECIAL" in text

    source = "G21\nM8 (SPECIAL SIZE8)\nT0101\nG1 X20 F100"
    assert native.scan_source(source, True, 1.0, None, predicate) == _scan_source_python(
        source, True, 1.0, None, predicate
    )


@pytest.mark.parametrize("description", ["SPECIAL SIZE=-2", "SPECIAL SIZE=oops", "UNKNOWN SIZE8", "BALL TAP SIZE8"])
def test_invalid_incomplete_and_ambiguous_comments(description):
    spec = discover_tools(f"T1 M6 ({description})", turning=False, rules=custom_profile())["T1"]
    assert spec["diameter"] == (8 if "SIZE8" in description else 10)
    assert spec["type"] == ("tap" if "TAP" in description else "mill_ball" if "SPECIAL" in description else "mill_flat")


def test_library_and_manual_geometry_keep_priority():
    source = "T1 M6 (SPECIAL SIZE8)\nG1 X2 F100"
    current = {}
    library = {"T1": {"type": "mill_flat", "diameter": 12, "length": 50}}
    inferred = refresh_setup(source, current, {}, turning=False, library_tools=library, rules=custom_profile())
    assert current["T1"]["diameter"] == 12
    current["T1"]["diameter"] = 6
    refresh_setup(source, current, inferred, turning=False, library_tools=library, rules=default_profile())
    assert current["T1"]["diameter"] == 6
    assert library["T1"]["diameter"] == 12


@pytest.mark.parametrize("pattern", ["[", ".*", "", "(SIZE)", 5, None])
def test_invalid_dimension_rules_are_rejected(pattern):
    profile = default_profile()
    profile["dimensions"]["milling_diameter"] = pattern
    with pytest.raises(ValueError):
        validate_profile(profile)


def test_missing_duplicate_unknown_rules_and_invalid_documents_are_rejected():
    profile = default_profile()
    for replacement in ([], profile["types"][:-1], profile["types"][:-1] + [profile["types"][0]], [["x", "unknown"]]):
        with pytest.raises(ValueError):
            validate_profile({**profile, "types": replacement})
    for document in (None, {}, {"active": "Missing", "profiles": {"Default": default_profile()}}):
        with pytest.raises(ValueError):
            validate_settings(document)


@pytest.mark.parametrize(
    "turning,dialect,source",
    [
        (False, "fanuc", "G21 G90 G17\nT1 M6 (BALL MILL D8)\nS1000 M3\nG1 X10 F100\nM30"),
        (True, "fanuc", "G21 G18\nT0101 (OD R0.8)\nS1000 M3\nG0 X20 Z2\nG1 Z-10 F100\nM30"),
        (False, "sinumerik", 'G710 G90\nT="DRILL"\nM6\nG0 Z5\nF100\nMCALL CYCLE81(5,0,1,-2,)\nX0 Y0\nMCALL\nM30'),
    ],
)
def test_reusing_program_preserves_entire_execution_result(monkeypatch, turning, dialect, source):
    options = {"language": "fanuc_turn" if turning else "fanuc_mill", "source_dialect": dialect}
    original, tools, inferred = execute_program(source, **options)
    assert original.ok, original.diagnostics

    def unexpected_parse(*_args):
        pytest.fail("Cached Program must not be parsed again")

    for module in (
        "app.gcode.kernel.api.execution_request",
        "app.gcode.kernel.milling.executor",
        "app.tools.discovery",
    ):
        monkeypatch.setattr(f"{module}.parse_program", unexpected_parse)
    monkeypatch.setattr("app.gcode.kernel.milling.executor.parse_sinumerik_program", unexpected_parse)
    repeated, repeated_tools, repeated_inferred = execute_program(source, parsed_program=original.program, **options)
    assert replace(repeated, program=None) == replace(original, program=None)
    assert repeated.program is original.program
    assert (repeated_tools, repeated_inferred) == (tools, inferred)


def test_profile_validation_does_not_alias_input_and_corrupt_storage_falls_back(caplog):
    original = default_settings()
    validated = validate_settings(original)
    validated["types"][0][0] = "CHANGED"
    assert original == default_settings()
    settings = get_settings()
    settings.setValue(SETTINGS_KEY, "{broken")
    assert load_settings(settings) == default_settings()
    assert "Invalid saved tool discovery rules" in caplog.text


def test_legacy_presets_are_removed_from_saved_settings():
    original = default_profile()
    original["dimensions"]["milling_diameter"] = "SIZE"
    document = {
        "active": "NX",
        "profiles": {"Default": original, "NX": default_profile(), "Fusion 360": default_profile()},
    }
    with pytest.raises(ValueError):
        validate_settings(document)
    settings = get_settings()
    settings.setValue(SETTINGS_KEY, json.dumps(document))
    migrated = load_settings(settings)
    assert set(migrated) == {"types", "dimensions"}
    assert migrated["dimensions"]["milling_diameter"] == "SIZE"
    assert json.loads(settings.value(SETTINGS_KEY)) == migrated


def test_cyrillic_name_aliases_are_removed_from_saved_settings():
    document = default_settings()
    suffix = r"|\b" + "\u041a\u041e\u041d\u0426\u0415\u0412\u0410\u042f" + r"\b"
    for entry in document["types"]:
        if entry[1] == "mill_flat":
            entry[0] += suffix
    settings = get_settings()
    settings.setValue(SETTINGS_KEY, json.dumps(document, ensure_ascii=False))
    assert load_settings(settings) == default_settings()
    assert json.loads(settings.value(SETTINGS_KEY)) == default_settings()
    assert all(pattern.isascii() for pattern, _kind in default_profile()["types"])


def test_cyrillic_tool_names_are_not_recognized():
    names = [
        "\u0421\u0412\u0415\u0420\u041b\u041e",
        "\u041c\u0415\u0422\u0427\u0418\u041a",
        "\u041a\u041e\u041d\u0426\u0415\u0412\u0410\u042f",
    ]
    for name in names:
        assert type_hint(name) is None
    rules = default_profile()
    rules["types"][0][0] = names[0]
    with pytest.raises(ValueError, match="Cyrillic"):
        validate_profile(rules)
