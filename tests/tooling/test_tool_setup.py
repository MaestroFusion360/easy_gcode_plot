"""Program-local setup, explicit library transfers, and unique tool numbers."""

# pylint: disable=protected-access

import json
from copy import deepcopy

import pytest
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox

from app import settings
from app.gcode.program_execution import execute_program
from app.main_window import MainWindow
from app.tools.definitions import DEFAULT_MILLING_TOOL, DEFAULT_TURNING_TOOL
from app.tools.setup import refresh_setup
from app.ui.dialogs import tool_dialogs, tool_library_dialog


@pytest.fixture
def window(qt_app):
    application = qt_app
    widget = MainWindow()
    widget.autoUpdateEnabled = False
    yield widget
    widget.autoUpdateTimer.stop()
    widget.ui.editor.setModified(False)
    widget.close()
    widget.deleteLater()
    application.processEvents()


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_same_t_number_in_different_files_uses_each_program_geometry(window, tmp_path):
    library = settings.get_tool_library()
    before = library.list_tools()
    first = tmp_path / "first.nc"
    second = tmp_path / "second.nc"
    first.write_text("T1 M6 (FLAT MILL D6)\nG1 X10 F100\nM30")
    second.write_text("T1 M6 (FLAT MILL D10)\nG1 X10 F100\nM30")
    window.loadFile(str(first))
    window.analyzeEditorSource()
    assert window.millingTools["T1"]["diameter"] == 6
    window.millingTools["T1"]["diameter"] = 7
    window.analyzeEditorSource()
    assert window.millingTools["T1"]["diameter"] == 7

    window.loadFile(str(second))
    window.analyzeEditorSource()
    assert window.millingTools["T1"]["diameter"] == 10
    assert library.list_tools() == before
    window.newFile()
    assert window.tools == window.millingTools == {}
    assert library.list_tools() == before


def test_setup_refresh_updates_inferred_tools_but_preserves_manual_geometry():
    current = {}
    previous = refresh_setup("T1 M6 (FLAT MILL D6)\nT2 M6", current, {}, turning=False)
    current["T2"]["diameter"] = 12
    previous = refresh_setup("T1 M6 (FLAT MILL D10)\nT2 M6", current, previous, turning=False)
    assert current["T1"]["diameter"] == 10
    assert current["T2"]["diameter"] == 12
    refresh_setup("T2 M6", current, previous, turning=False)
    assert "T1" not in current
    assert current["T2"]["diameter"] == 12


def test_shared_execution_preserves_gui_tool_override(monkeypatch):
    source = "T1 M6 (FLAT MILL D6)\nM30\n"
    current = {}
    previous = refresh_setup(source, current, {}, turning=False)
    current["T1"]["diameter"] = 7
    observed = {}

    def fake_execute(_source, **options):
        observed.update(options)
        return object()

    monkeypatch.setattr("app.gcode.program_execution.execute", fake_execute)
    _result, updated, inferred = execute_program(
        source,
        language="fanuc_mill",
        current_tools=current,
        previous_inference=previous,
    )

    assert updated["T1"]["diameter"] == 7
    assert inferred["T1"]["diameter"] == 6
    assert observed["milling_tools"]["T1"]["diameter"] == 7


def test_setup_refresh_removes_manual_assignment_when_t_slot_disappears():
    current = {}
    previous = refresh_setup("T1 M6\nT2 M6", current, {}, turning=False)
    current["T1"]["diameter"] = 6

    refresh_setup("T2 M6", current, previous, turning=False)

    assert "T1" not in current
    assert set(current) == {"T2"}


@pytest.mark.parametrize(
    ("editor_type", "key", "alias", "different", "spec"),
    [
        (tool_dialogs._MillingToolEditor, "T1", "T01", "T2", DEFAULT_MILLING_TOOL),
        (tool_dialogs._TurningToolEditor, "T0101", "T101", "T0102", DEFAULT_TURNING_TOOL),
    ],
)
def test_tool_editor_rejects_duplicate_library_number(window, monkeypatch, editor_type, key, alias, different, spec):
    warnings = []
    monkeypatch.setattr(tool_dialogs.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    editor = editor_type(window.toolLibraryDlg)
    editor.reservedCodes = {key, different}
    editor.toolCode.setText(alias)
    editor.validateAndAccept()
    assert editor.result() != QDialog.DialogCode.Accepted
    assert warnings and key in warnings[-1]

    renamed = editor_type(window.toolLibraryDlg, different, spec)
    renamed.reservedCodes = {key}
    renamed.toolCode.setText(key)
    renamed.validateAndAccept()
    assert renamed.result() != QDialog.DialogCode.Accepted
    renamed.toolCode.setText(different)
    renamed.validateAndAccept()
    assert renamed.result() == QDialog.DialogCode.Accepted


def test_turning_setup_keeps_distinct_offsets_for_same_tool():
    current = {}
    refresh_setup("T0101 (OD R0.4)\nT0102 (ID R0.8)\nT0101", current, {}, turning=True)
    assert set(current) == {"T0101", "T0102"}
    assert current["T0101"]["noseRadius"] == 0.4
    assert current["T0102"]["noseRadius"] == 0.8


def test_library_assignment_copies_geometry_into_selected_program_number(window, monkeypatch):
    window.millingTools = {"T7": deepcopy(DEFAULT_MILLING_TOOL)}
    dialog = window.toolLibraryDlg
    library_geometry = window.millingToolLibrary["T1"]
    original = deepcopy(library_geometry)
    monkeypatch.setattr(window, "updateData", lambda: True)
    dialog.refresh("milling", selected_program="T7", selected_library="T1")
    dialog.assign_from_library("milling")
    assert set(window.millingTools) == {"T7"}
    assert window.millingTools["T7"] == original
    window.millingTools["T7"]["diameter"] = 22
    assert library_geometry == original
    assert settings.get_tool_library().get_tool("milling", "T7") is None


def test_library_edit_never_changes_setup_and_preserves_unknown_entries(window):
    library = settings.get_tool_library()
    library.save_tool("milling", "T99", {"type": "future_type"})
    window.millingTools = {"T1": {**DEFAULT_MILLING_TOOL, "diameter": 6}}
    dialog = window.toolLibraryDlg
    edited = {**window.millingToolLibrary["T1"], "diameter": 20}
    dialog.begin_session()
    assert dialog._persist_library_change("milling", "T1", edited, previous_key="T1")
    assert window.millingTools["T1"]["diameter"] == 6
    assert library.get_tool("milling", "T1").spec["diameter"] != 20
    dialog.accept()
    assert library.get_tool("milling", "T1").spec["diameter"] == 20
    assert library.get_tool("milling", "T99").spec == {"type": "future_type"}


def test_closing_tool_library_never_persists_current_program_tools(window):
    window.millingTools = {"T42": {**DEFAULT_MILLING_TOOL, "diameter": 6}}
    dialog = window.toolLibraryDlg
    dialog.refresh("milling", selected_program="T42")
    dialog.reject()
    assert window.millingTools["T42"]["diameter"] == 6
    assert settings.get_tool_library().get_tool("milling", "T42") is None


def test_save_to_library_is_an_explicit_copy(window, monkeypatch):
    window.millingTools = {"T7": {**DEFAULT_MILLING_TOOL, "diameter": 6}}
    dialog = window.toolLibraryDlg
    dialog.begin_session()
    dialog.refresh("milling", selected_program="T7")

    def accept_editor(editor):
        editor.toolCode.setText("T8")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(tool_library_dialog._MillingToolEditor, "exec", accept_editor)
    dialog.save_program_to_library("milling")
    assert settings.get_tool_library().get_tool("milling", "T8") is None
    assert dialog.library_tools("milling")["T8"]["diameter"] == 6
    assert set(window.millingTools) == {"T7"}
    dialog.accept()
    assert settings.get_tool_library().get_tool("milling", "T8").spec["diameter"] == 6
    window.millingToolLibrary["T8"]["diameter"] = 12
    assert window.millingTools["T7"]["diameter"] == 6


def test_library_save_failure_keeps_setup_and_library_unchanged(window, monkeypatch):
    dialog = window.toolLibraryDlg
    original = deepcopy(window.millingToolLibrary["T1"])
    edited = {**original, "diameter": 6}
    warnings = []
    dialog.begin_session()
    monkeypatch.setattr(tool_library_dialog, "save_library_changes", lambda *args: False)
    monkeypatch.setattr(
        tool_library_dialog.QMessageBox,
        "warning",
        lambda *args: warnings.append(args[-1]),
    )
    assert dialog._persist_library_change("milling", "T1", edited, previous_key="T1")
    dialog.accept()
    assert window.millingToolLibrary["T1"] == original
    assert warnings == ["Could not save the tool library. Please retry."]


def test_tool_library_load_failure_is_visible_and_disables_editing(qt_app, monkeypatch):
    class _BrokenLibrary:
        def tools_by_kind(self, _kind):
            raise OSError("read failed")

    messages = []
    monkeypatch.setattr(settings, "get_tool_library", lambda: _BrokenLibrary())
    monkeypatch.setattr("app.main_window.QMessageBox.critical", lambda *args: messages.append(args[-1]))

    widget = MainWindow()
    qt_app.processEvents()

    assert not widget.ui.actionToolLibrary.isEnabled()
    assert messages and "disabled to protect the existing database" in messages[-1]
    widget.autoUpdateTimer.stop()
    widget.ui.editor.setModified(False)
    widget.close()
    widget.deleteLater()


def test_tool_library_ok_commits_staged_saved_library(window):
    dialog = window.toolLibraryDlg
    database = settings.get_tool_library()
    original = deepcopy(window.millingToolLibrary["T1"])
    edited = {**original, "diameter": 7.0}
    dialog.begin_session()

    dialog._persist_library_change("milling", "T1", edited, previous_key="T1")

    assert window.millingToolLibrary["T1"] == original
    assert database.get_tool("milling", "T1").spec == original
    dialog.accept()
    assert window.millingToolLibrary["T1"] == edited
    assert database.get_tool("milling", "T1").spec == edited


def test_tool_library_cancel_rolls_back_add_edit_delete_and_duplicate(window, monkeypatch):
    dialog = window.toolLibraryDlg
    database = settings.get_tool_library()
    original = deepcopy(window.millingToolLibrary)
    original_database = database.tools_by_kind("milling")
    added = {**DEFAULT_MILLING_TOOL, "diameter": 6.0}
    edited = {**original["T1"], "diameter": 12.0}
    dialog.begin_session()

    class _AcceptedEditor:
        values = [("T2", added), ("T1", edited)]

        def __init__(self, *_args, **_kwargs):
            self.reservedCodes = set()

        def exec(self):
            return QDialog.DialogCode.Accepted

        def value(self):
            return self.values.pop(0)

    monkeypatch.setattr(tool_library_dialog, "_MillingToolEditor", _AcceptedEditor)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

    dialog.add_library_tool("milling")
    dialog.refresh("milling", selected_library="T1")
    dialog.edit_library_tool("milling")
    dialog.refresh("milling", selected_library="T1")
    dialog.duplicate_library_tool("milling")
    dialog.refresh("milling", selected_library="T2")
    dialog.remove_library_tool("milling")
    assert dialog.library_tools("milling") != original

    dialog.reject()

    assert window.millingToolLibrary == original
    assert database.tools_by_kind("milling") == original_database


def test_current_program_preview_tracks_selection_tabs_edits_and_empty_selection(window, monkeypatch):
    dialog = window.toolLibraryDlg
    milling_first = {**DEFAULT_MILLING_TOOL, "diameter": 3.0}
    milling_second = {**DEFAULT_MILLING_TOOL, "diameter": 8.0}
    turning = {**DEFAULT_TURNING_TOOL, "noseRadius": 1.2}
    window.millingTools = {"T2": milling_first, "T7": milling_second}
    window.tools = {"T0101": turning}
    monkeypatch.setattr(window, "updateData", lambda: True)

    dialog.refresh("milling")
    dialog.pages["milling"]["program"].selectRow(1)
    assert dialog.pages["milling"]["preview"].spec == milling_second

    dialog.refresh("turning", selected_program="T0101")
    dialog.ui.tabs.setCurrentWidget(dialog.ui.turningTab)
    assert dialog.pages["turning"]["preview"].spec == turning

    edited = {**turning, "noseRadius": 0.2}

    def accept_editor(editor):
        editor.noseRadius.setValue(0.2)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(tool_library_dialog._TurningToolEditor, "exec", accept_editor)
    dialog.edit_program_tool("turning")
    assert dialog.pages["turning"]["preview"].spec == edited

    dialog.pages["turning"]["program"].clearSelection()
    assert dialog.pages["turning"]["preview"].spec == {}


def test_tool_library_has_only_standard_ok_cancel_and_no_explanatory_labels(window, qt_app):
    dialog = window.toolLibraryDlg
    texts = {label.text() for label in dialog.findChildren(QLabel)}
    buttons = dialog.ui.buttonBox.standardButtons()

    assert not any("T-slots discovered" in text or "T slots discovered" in text for text in texts)
    assert not any("Reusable tool geometry stored in tools.db" in text for text in texts)
    assert not any("Current Program tools are temporary" in text for text in texts)
    assert buttons == QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    assert not buttons & QDialogButtonBox.StandardButton.Close
    assert dialog.minimumWidth() == 0
    assert dialog.minimumHeight() == 0
    assert dialog.width() <= 940
    assert dialog.height() <= 620
    assert dialog.styleSheet() == ""
    assert all(
        getattr(dialog.ui, f"{kind}{section}Group").isFlat()
        for kind in ("milling", "turning")
        for section in ("Program", "Library")
    )
    assert all(page["previewPane"].scrollArea.styleSheet() == "" for page in dialog.pages.values())
    assert all(
        page["previewPane"].scrollArea.viewport().backgroundRole() == QPalette.ColorRole.Window
        and page["previewPane"].preview.backgroundRole() == QPalette.ColorRole.Window
        for page in dialog.pages.values()
    )
    assert all(
        page["previewPane"].scrollArea.viewport().palette().color(QPalette.ColorRole.Window)
        == page["previewPane"].preview.palette().color(QPalette.ColorRole.Window)
        for page in dialog.pages.values()
    )
    assert all(page[source].minimumHeight() == 0 for page in dialog.pages.values() for source in ("program", "library"))

    dialog.show()
    qt_app.processEvents()
    assert dialog.size().width() <= 940
    assert dialog.size().height() <= 620
    dialog.resize(760, 500)
    qt_app.processEvents()
    assert (dialog.width(), dialog.height()) == (760, 500)


def test_tool_library_export_uses_complete_saved_kind_not_current_selection(window, tmp_path):
    dialog = window.toolLibraryDlg
    window.millingToolLibrary = {
        "T1": {**DEFAULT_MILLING_TOOL, "diameter": 10.0},
        "T7": {**DEFAULT_MILLING_TOOL, "diameter": 6.0},
    }
    window.millingTools = {"T99": {**DEFAULT_MILLING_TOOL, "diameter": 3.0}}
    dialog.begin_session()
    dialog.refresh("milling", selected_library="T1")
    output = tmp_path / "saved_milling.json"

    dialog.export_library_tool("milling", str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [record["tool"] for record in payload["tools"]] == ["T1", "T7"]
    assert "T99" not in {record["tool"] for record in payload["tools"]}
