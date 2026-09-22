# pylint: disable=protected-access
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from app import main_window
from app import settings as app_settings
from app.ui.generated.dialogs.wcs import Ui_WcsDlg
from app.ui.windows.window_settings import (
    EDITOR_FONT_FAMILY_KEY,
    EDITOR_FONT_ITALIC_KEY,
    EDITOR_FONT_SIZE_KEY,
    EDITOR_FONT_WEIGHT_KEY,
)


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_wcs_dialog_can_shrink_below_legacy_fixed_height(qt_app):
    dialog = QDialog()
    ui = Ui_WcsDlg()
    ui.setupUi(dialog)

    assert dialog.minimumHeight() == 0
    assert dialog.height() == 330
    compact_height = dialog.minimumSizeHint().height()
    assert compact_height < 430
    dialog.resize(dialog.width(), compact_height)
    assert dialog.height() < 430


@pytest.mark.parametrize(("kind", "key"), [("turning", "T9898"), ("milling", "T98")])
def test_saving_window_preferences_preserves_unrecognized_tool_records(qt_app, kind, key):
    window = main_window.MainWindow()
    library = app_settings.get_tool_library()
    future = {"type": "future_type", "custom": 123}
    library.save_tool(kind, key, future)
    before = library.get_tool(kind, key)
    window.saveSettings()
    assert library.get_tool(kind, key) == before
    window.close()
    assert library.get_tool(kind, key) == before


def test_clean_profile_uses_code_defaults_and_ignores_working_directory_config(qt_app, tmp_path, monkeypatch):
    rogue_dir = tmp_path / "legacy-install"
    rogue_dir.mkdir()
    (rogue_dir / "config.ini").write_text("[EXPORT_OPT]\nSAFETY_LINE=true\nSEQ_NUM=true\n", encoding="utf-8")
    monkeypatch.chdir(rogue_dir)

    window = main_window.MainWindow()

    assert window.safLine is False
    assert window.seqNum is False
    assert not window.settings.contains("EXPORT_OPT/SAFETY_LINE")
    assert not window.settings.contains("EXPORT_OPT/SEQ_NUM")
    window.deleteLater()


def test_tool_settings_normalization_matches_turning_kernel_keys():
    raw = {
        "101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 1},
        "T2": {"type": "drill", "description": "  center   drill "},
        "bad": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 1},
        "T0303": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.0, "tipOrientation": 3},
    }

    assert main_window._normalized_tools(raw) == {
        "T0101": {
            "type": "diamond_80",
            "applications": ["od"],
            "noseRadius": 0.4,
            "tipOrientation": 1,
            "insertLength": 12.0,
        },
        "T0002": {"type": "drill", "description": "center drill"},
    }


def test_turning_tool_geometry_types_are_normalized_for_stock_removal():
    raw = {
        "T0101": {"type": "groove", "applications": ["face"], "width": 4.0},
        "T0202": {"type": "groove", "applications": ["od"], "width": 4.0},
        "T0606": {"type": "groove", "applications": ["id"], "width": 3.0},
        "T0303": {"type": "drill", "diameter": 12.0, "length": 60.0, "tipAngle": 118.0},
        "T0404": {"type": "diamond_80", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2},
        "T0505": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3},
        "T0707": {"type": "diamond_35", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3},
        "T0808": {"type": "diamond_35", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2},
        "T0909": {"type": "thread", "tipOrientation": 3},
    }

    expected = {
        **raw,
        "T0101": {"type": "groove", "applications": ["face"], "width": 4.0, "noseRadius": 0.0, "tipOrientation": 3},
        "T0202": {"type": "groove", "applications": ["od"], "width": 4.0, "noseRadius": 0.0, "tipOrientation": 3},
        "T0606": {"type": "groove", "applications": ["id"], "width": 3.0, "noseRadius": 0.0, "tipOrientation": 2},
        "T0404": {**raw["T0404"], "insertLength": 12.0},
        "T0505": {**raw["T0505"], "insertLength": 12.0},
        "T0707": {**raw["T0707"], "insertLength": 16.0},
        "T0808": {**raw["T0808"], "insertLength": 16.0},
        "T0909": {
            **raw["T0909"],
            "applications": ["od"],
            "insertLength": 12.0,
            "threadAngle": 60.0,
            "threadTipWidth": 0.8,
            "threadCornerRadius": 0.1,
        },
    }
    assert main_window._normalized_tools(raw) == expected


def test_editor_font_persistence_uses_existing_font_keys():
    assert (
        EDITOR_FONT_FAMILY_KEY,
        EDITOR_FONT_SIZE_KEY,
        EDITOR_FONT_WEIGHT_KEY,
        EDITOR_FONT_ITALIC_KEY,
    ) == ("FONT_FAMILY", "FONT_SIZE", "FONT_WEIGHT", "FONT_ITALIC")


def test_milling_tool_settings_normalization_matches_cnceditor_geometry_rules():
    raw = {
        "1": {"type": "mill_flat", "diameter": 10, "cornerRadius": 2, "length": 50},
        "T2": {"type": "mill_bull", "diameter": 12, "cornerRadius": 1.5, "length": 60},
        "T0003": {"type": "mill_ball", "diameter": 8, "cornerRadius": 99, "length": 45},
        "4": {"type": "drill", "diameter": 6, "cornerRadius": 1, "length": 70, "description": "  center   drill "},
        "T100": {"type": "mill_flat", "diameter": 10, "length": 20},
        "bad": {"type": "mill_flat", "diameter": 10, "length": 20},
        "T5": {"type": "unknown", "diameter": 10, "length": 20},
    }

    assert main_window._normalized_milling_tools(raw) == {
        "T1": {
            "type": "mill_flat",
            "diameter": 10.0,
            "cornerRadius": 0.0,
            "length": 50.0,
        },
        "T2": {
            "type": "mill_bull",
            "diameter": 12.0,
            "cornerRadius": 1.5,
            "length": 60.0,
        },
        "T3": {
            "type": "mill_ball",
            "diameter": 8.0,
            "cornerRadius": 4.0,
            "length": 45.0,
        },
        "T4": {
            "type": "drill",
            "diameter": 6.0,
            "cornerRadius": 0.0,
            "length": 70.0,
            "tipAngle": 118.0,
            "description": "center drill",
        },
    }


def test_application_settings_are_isolated_from_user_profile(tmp_path):
    del tmp_path  # The autouse settings fixture owns the per-test directory.
    settings = app_settings.get_settings()

    assert "pytest-" in Path(settings.fileName()).as_posix()


def test_application_logging_toggle_creates_and_closes_project_handler(monkeypatch, tmp_path):
    monkeypatch.setattr(app_settings, "_config_dir", lambda: str(tmp_path))
    app_settings.configure_logging(False)
    app_settings.configure_logging(True)
    root = logging.getLogger()
    original_root_level = root.level
    logging.getLogger("app.test").warning("logging-regression")
    for handler in logging.getLogger("app").handlers:
        handler.flush()
    assert "logging-regression" in (tmp_path / "main.log").read_text(encoding="utf-8")
    assert root.level == original_root_level
    app_settings.configure_logging(False)
    assert not any(getattr(handler, "_easy_gcode_plot_handler", False) for handler in logging.getLogger("app").handlers)


def test_milling_tool_normalization_rejects_impossible_geometry():
    raw = {
        "T1": {"type": "mill_flat", "diameter": 0, "length": 20},
        "T2": {"type": "drill", "diameter": 5, "length": 0},
        "T3": {"type": "mill_bull", "diameter": 10, "cornerRadius": 6, "length": 20},
        "T4": {"type": "mill_bull", "diameter": 10, "cornerRadius": 5, "length": 20},
        "T5": {"type": "mill_flat", "diameter": float("nan"), "length": 20},
    }

    assert main_window._normalized_milling_tools(raw) == {
        "T4": {"type": "mill_bull", "diameter": 10.0, "cornerRadius": 5.0, "length": 20.0}
    }
