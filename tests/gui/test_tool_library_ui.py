"""Tool Library button labels and bundled icons."""

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from app.tools.discovery_rules import default_settings
from app.tools.setup import refresh_setup
from app.ui.dialogs.tool_library_dialog import ToolLibraryDialog
from app.ui.generated.editors.tool_library import Ui_ToolLibraryDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_tool_library_buttons_have_short_labels_tooltips_and_icons(qt_app):
    dialog = QDialog()
    ui = Ui_ToolLibraryDialog()
    ui.setupUi(dialog)

    for prefix in ("milling", "turning"):
        for suffix, label in (
            ("EditProgram", "Edit Geometry"),
            ("Assign", "Assign from Library"),
            ("Save", "Save to Library"),
            ("AddLibrary", "Add"),
            ("EditLibrary", "Edit"),
            ("DuplicateLibrary", "Duplicate"),
            ("ExportLibrary", "Export"),
            ("RemoveLibrary", "Remove"),
        ):
            button = getattr(ui, f"{prefix}{suffix}Button")
            assert button.text() == label
            assert button.toolTip() == label
            assert button.iconSize().width() == 16
            assert not button.icon().isNull()
        preview = getattr(ui, f"{prefix}PreviewPane")
        for action in ("Import", "Export"):
            button = getattr(ui, f"{prefix}{action}ProgramButton")
            assert button.text() == action
            assert button.toolTip() == f"{action} current program tools (JSON)"
            assert button.iconSize().width() == 16
            assert not button.icon().isNull()
        for name, label in (
            ("zoomOutButton", "Zoom out"),
            ("fitButton", "Fit preview"),
            ("zoomInButton", "Zoom in"),
        ):
            button = getattr(preview.ui, name)
            assert button.text() == ""
            assert button.toolTip() == label
            assert button.iconSize().width() == 16
            assert not button.icon().isNull()
    assert qt_app is not None


def test_library_discovery_uses_the_document_recognition_rules():
    rules = default_settings()
    rules["dimensions"]["milling_diameter"] = "SIZE"
    source = "T1 M6 (BALL MILL SIZE8)\nG0 X0 Y0\nM30"
    tools = {}
    inference = refresh_setup(source, tools, {}, turning=False, rules=rules)
    parent = SimpleNamespace(
        latheMode=False,
        program_tool_inference={"millingTools": inference},
        defaultUnits="mm",
        toolDiscovery=rules,
        ui=SimpleNamespace(editor=SimpleNamespace(text=lambda: source)),
    )
    dialog = SimpleNamespace(
        parent=lambda: parent,
        _editable_program_tools=lambda _kind: tools,
        library_tools=lambda _kind: {},
        _program_inference={},
    )
    ToolLibraryDialog._discover_program_tools(dialog)  # pylint: disable=protected-access
    assert tools["T1"]["diameter"] == 8


def test_library_export_reports_io_failure(qt_app, monkeypatch, tmp_path):
    dialog = ToolLibraryDialog()
    warnings = []
    monkeypatch.setattr("app.ui.dialogs.tool_library_dialog.QMessageBox.warning", lambda *args: warnings.append(args))
    dialog.export_library_tool("milling", str(tmp_path / "missing" / "tools.json"))
    assert len(warnings) == 1
    assert "tools.json" in warnings[0][2]
    assert dialog.result() == 0
    dialog.deleteLater()
