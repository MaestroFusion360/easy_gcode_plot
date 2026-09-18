from __future__ import annotations

import json
import sqlite3

import pytest

from app import settings as app_settings
from app.tools.definitions import AUTO_TIP_ORIENTATIONS, DEFAULT_MILLING_TOOL, default_turning_library
from app.tools.library import KIND_MILLING, KIND_TURNING, ToolLibrary
from app.ui.dialogs.tool_dialogs import _export_tool_library
from scripts import generate_turning_tools as generator_script
from scripts.generate_turning_tools import generate_turning_tools

TURNING_T1 = {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}
TURNING_T1_CHANGED = {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.8, "tipOrientation": 3}
MILLING_T1 = {"type": "mill_flat", "diameter": 10.0, "cornerRadius": 0.0, "length": 50.0}


@pytest.mark.parametrize("spec", [{"type": "future_type", "future_field": 123}, {"type": "diamond_80"}])
def test_loading_turning_tools_never_rewrites_database(tmp_path, monkeypatch, spec):
    with ToolLibrary(str(tmp_path / "tools.db")) as library:
        library.save_tool(KIND_TURNING, "T0001", TURNING_T1)
        library.save_tool(KIND_TURNING, "T0002", spec)
        before = library.tools_by_kind(KIND_TURNING)
        monkeypatch.setattr(app_settings, "get_tool_library", lambda: library)

        app_settings.load_turning_tools()
        app_settings.load_turning_tools()

        assert library.tools_by_kind(KIND_TURNING) == before


def test_tool_library_save_load_and_sync(tmp_path):
    with ToolLibrary(str(tmp_path / "tools.db")) as library:
        library.save_tool(KIND_TURNING, "T0001", TURNING_T1)
        library.save_tool(KIND_TURNING, "T0002", TURNING_T1)

        assert library.get_tool(KIND_TURNING, "T0001").spec == TURNING_T1

        library.sync_kind(KIND_TURNING, {"T0001": TURNING_T1_CHANGED})

        assert library.tools_by_kind(KIND_TURNING) == {"T0001": TURNING_T1_CHANGED}
        assert library.get_tool(KIND_TURNING, "T0002") is None


def test_multi_kind_edits_are_one_transaction(tmp_path):
    with ToolLibrary(str(tmp_path / "tools.db")) as library:
        library.save_tool(KIND_MILLING, "T1", MILLING_T1)
        library.save_tool(KIND_TURNING, "T0001", TURNING_T1)
        original = {
            KIND_MILLING: {"T1": MILLING_T1},
            KIND_TURNING: {"T0001": TURNING_T1},
        }
        changes = {
            KIND_MILLING: (original[KIND_MILLING], {"T1": {**MILLING_T1, "diameter": 6.0}}),
            KIND_TURNING: (original[KIND_TURNING], {"T0001": None}),
        }

        with pytest.raises(ValueError, match="mapping"):
            library.apply_edits_by_kind(changes)

        assert library.tools_by_kind(KIND_MILLING) == original[KIND_MILLING]
        assert library.tools_by_kind(KIND_TURNING) == original[KIND_TURNING]


def test_duplicate_tool_never_overwrites_existing_key(tmp_path):
    with ToolLibrary(str(tmp_path / "tools.db")) as library:
        library.save_tool(KIND_TURNING, "T0001", TURNING_T1)
        library.save_tool(KIND_TURNING, "T0002", TURNING_T1_CHANGED)

        try:
            library.duplicate_tool(KIND_TURNING, "T0001", "T0002")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("duplicate_tool must reject an existing destination key")

        assert library.get_tool(KIND_TURNING, "T0002").spec == TURNING_T1_CHANGED


def test_settings_creates_current_database_without_importing_qsettings_tools():
    settings = app_settings.get_settings()
    settings.setValue("CNC/TOOLS_JSON", json.dumps({"T1": TURNING_T1}))
    settings.setValue("CNC/MILLING_TOOLS_JSON", json.dumps({"T1": MILLING_T1}))
    settings.sync()

    turning = app_settings.load_turning_tools()
    assert len(turning) == 28
    assert "T0001" not in turning
    assert app_settings.load_milling_tools() == {"T1": DEFAULT_MILLING_TOOL}
    assert settings.contains("CNC/TOOLS_JSON") is True
    assert settings.contains("CNC/MILLING_TOOLS_JSON") is True

    assert app_settings.save_turning_tools({}) is True
    assert app_settings.load_turning_tools() == {}


def test_failed_sqlite_save_does_not_create_second_qsettings_source(monkeypatch):
    class _BrokenLibrary:
        def sync_kind(self, _kind, _tools):
            raise sqlite3.OperationalError("write failed")

    settings = app_settings.get_settings()
    settings.remove("CNC/TOOLS_JSON")
    monkeypatch.setattr(app_settings, "get_tool_library", lambda: _BrokenLibrary())

    assert app_settings.save_turning_tools({"T0001": TURNING_T1}) is False
    assert settings.contains("CNC/TOOLS_JSON") is False


def test_combined_tool_library_load_reports_failure(monkeypatch):
    class _BrokenLibrary:
        def tools_by_kind(self, _kind):
            raise sqlite3.DatabaseError("database is corrupt")

    monkeypatch.setattr(app_settings, "get_tool_library", lambda: _BrokenLibrary())
    monkeypatch.setattr(app_settings, "tool_library_path", lambda: "broken-tools.db")

    with pytest.raises(app_settings.ToolLibraryLoadError, match="broken-tools.db"):
        app_settings.load_tool_libraries()


def test_saved_library_export_supports_json_and_csv(tmp_path):
    json_path = tmp_path / "milling_tools.json"
    csv_path = tmp_path / "milling_tools.csv"
    tools = {
        "T1": MILLING_T1,
        "T2": {**MILLING_T1, "diameter": 6.0, "description": "Finisher"},
    }

    _export_tool_library(str(json_path), "milling", tools)
    _export_tool_library(str(csv_path), "milling", tools)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["library"] == "milling"
    assert [record["tool"] for record in payload["tools"]] == ["T1", "T2"]
    assert payload["tools"][1]["diameter"] == 6.0

    csv_lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(csv_lines) == 3
    assert csv_lines[0].startswith("tool,type,description")
    assert csv_lines[1].startswith("T1,")
    assert csv_lines[2].startswith("T2,")


def test_empty_library_is_seeded_once_with_all_deterministic_tool_positions(tmp_path):
    presets = default_turning_library()
    assert len(presets) == 28
    for tool_type, orientations in AUTO_TIP_ORIENTATIONS.items():
        assert {spec["tipOrientation"] for spec in presets.values() if spec["type"] == tool_type} == set(orientations)

    with ToolLibrary(str(tmp_path / "tools.db")) as library:
        library.save_tool(KIND_TURNING, "T0101", TURNING_T1_CHANGED)
        assert library.seed_defaults_once(presets, {"T1": DEFAULT_MILLING_TOOL})
        assert len(library.tools_by_kind(KIND_TURNING)) == 29
        assert library.get_tool(KIND_TURNING, "T0101").spec == TURNING_T1_CHANGED
        assert library.tools_by_kind(KIND_MILLING) == {"T1": DEFAULT_MILLING_TOOL}
        library.sync_kind(KIND_TURNING, {})

        assert not library.seed_defaults_once(presets, {"T1": DEFAULT_MILLING_TOOL})
        assert library.tools_by_kind(KIND_TURNING) == {}


def test_generator_writes_auto_tools_and_preserves_milling(tmp_path):
    database = tmp_path / "tools.db"
    with ToolLibrary(str(database)) as library:
        library.save_tool(KIND_MILLING, "T1", MILLING_T1)

    assert generate_turning_tools(database) == 28
    with ToolLibrary(str(database)) as library:
        assert library.tools_by_kind(KIND_TURNING) == default_turning_library()
        assert library.tools_by_kind(KIND_MILLING) == {"T1": MILLING_T1}

    with pytest.raises(RuntimeError, match="--force"):
        generate_turning_tools(database)


def test_generator_cli_defaults_to_the_database_used_by_the_application(tmp_path, monkeypatch, capsys):
    database = tmp_path / "active-application-tools.db"
    monkeypatch.setattr(generator_script, "tool_library_path", lambda: str(database))

    assert generator_script.main([]) == 0

    with ToolLibrary(str(database)) as library:
        assert library.tools_by_kind(KIND_TURNING) == default_turning_library()
    assert str(database) in capsys.readouterr().out
