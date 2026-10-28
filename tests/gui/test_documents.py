"""Exercise real Scintilla buffers and the multi-document window controls."""

# Regression assertions inspect buffer snapshots and document-switch guards.
# pylint: disable=protected-access

from pathlib import Path

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from app import settings
from app.main_window import MainWindow
from app.ui.plot.stl import mesh_from_triangles


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    settings.get_settings().setValue("GENERAL/AUTO_UPDATE", False)
    settings.get_settings().setValue("PLOT/LATHE_MODE", True)
    owner = MainWindow()
    yield owner
    owner.autoUpdateTimer.stop()
    owner.timer.stop()
    owner.deleteLater()
    qt_app.processEvents()


def test_startup_has_only_one_milling_document(window):
    assert len(window._documents) == 1
    assert not window.latheMode
    assert not window.ui.actionLatheMode.isChecked()
    assert window.ui.editor.text() == ""
    assert len(window.documentListMenu.actions()) == 1


def test_plus_switch_preserves_text_cursor_modified_and_undo(window):
    editor = window.ui.editor
    QTest.keyClicks(editor, "G0 X12")
    editor.setCursorPosition(0, 3)
    window.documentNewButton.click()
    assert len(window._documents) == 2
    assert editor.text() == ""
    assert not editor.isModified()
    QTest.keyClicks(editor, "G1 Y5")
    window.documentListMenu.actions()[0].trigger()
    assert editor.text() == "G0 X12"
    assert editor.getCursorPosition() == (0, 3)
    assert editor.isModified()
    assert editor.isUndoAvailable()
    editor.undo()
    assert editor.text() != "G0 X12"
    assert window._activate_document(1)
    assert editor.text() == "G1 Y5"


def test_open_reuses_initial_slot_and_existing_file(window, tmp_path):
    paths = [tmp_path / "first.nc", tmp_path / "second.nc"]
    for index, path in enumerate(paths):
        path.write_text(f"G0 X{index}\n", encoding="utf-8")
        assert window.loadFile(str(path))
        assert len(window._documents) == index + 1
    assert window.loadFile(str(paths[0]))
    assert len(window._documents) == 2
    assert window._active_document_index == 0
    assert Path(window.curFile) == paths[0]


def test_switch_restores_machine_mode_and_tool_assignments(window):
    window.ui.actionLatheMode.setChecked(True)
    window.changeLathe()
    window.tools = {"T1": {"description": "turning"}}
    window.newFile()
    window.tools = {"T2": {"description": "second"}}
    window.ui.actionLatheMode.setChecked(False)
    window.changeLathe()
    assert window._activate_document(0)
    assert window.latheMode
    assert window.ui.actionLatheMode.isChecked()
    assert "T1" in window.tools and "T2" not in window.tools
    assert window._activate_document(1)
    assert not window.latheMode
    assert "T2" in window.tools and "T1" not in window.tools


def test_close_cancel_keeps_both_documents(window, monkeypatch):
    window.newFile()
    QTest.keyClicks(window.ui.editor, "G0 X1")
    monkeypatch.setattr(QMessageBox, "warning", lambda *_a: QMessageBox.StandardButton.Cancel)
    assert not window.closeDocument()
    assert len(window._documents) == 2
    assert window.ui.editor.text() == "G0 X1"


def test_close_all_prompts_for_each_modified_document(window, monkeypatch):
    QTest.keyClicks(window.ui.editor, "G0 X1")
    window.newFile()
    QTest.keyClicks(window.ui.editor, "G0 X2")
    prompts = []

    def discard(*args):
        prompts.append(args)
        return QMessageBox.StandardButton.Discard

    monkeypatch.setattr(QMessageBox, "warning", discard)
    assert window.closeAllDocuments()
    assert len(prompts) == 2
    assert len(window._documents) == 1
    assert window.ui.editor.text() == ""
    assert not window.ui.editor.isModified()
    assert window.curFile == ""


def test_switch_blocked_during_execution(window):
    window.newFile()
    window._kernel_execution_active = True
    assert not window._activate_document(0)
    assert window._active_document_index == 1
    assert not window.closeDocument()
    window._kernel_execution_active = False


def test_controls_render_without_font_glyphs(window):
    for button in (window.documentNewButton, window.documentListButton, window.documentCloseButton):
        assert button.text() == ""
        assert button.accessibleName()
        assert not button.grab().isNull()


def test_switch_restores_cached_trace_and_playback(window):
    window.ui.editor.setText("G21 G90\nG0 X0 Y0 Z5\nG1 X10 F100\nM30\n")
    window.updateData(show_errors=False)
    result = window.execution_result
    assert result is not None and result.motions
    points = window.render_points
    position = window.ui.horizontalSlider.maximum()
    window.ui.horizontalSlider.setValue(position)
    window.newFile()
    assert window.execution_result is None
    assert window._activate_document(0)
    assert window.execution_result is result
    assert window.render_points is points
    assert window.ui.horizontalSlider.value() == position


@pytest.mark.parametrize(
    "name",
    [
        "exportDlg",
        "blockNumDlg",
        "wcsDlg",
        "optionsDlg",
        "stockDlg",
        "toolLibraryDlg",
        "holeCalculatorDlg",
        "pocketCalculatorDlg",
        "snippetsDlg",
    ],
)
def test_pending_dialog_cannot_write_into_another_document(window, name):
    window.newFile()
    dialog = getattr(window, name)
    dialog.show()
    assert dialog.isVisible()
    try:
        assert not window._activate_document(0)
        assert not window.closeDocument()
        window.newFile()
        assert len(window._documents) == 2
        assert window._active_document_index == 1
        assert "dialog" in window.ui.statusbar.toolTip()
    finally:
        dialog.reject()
    assert window._activate_document(0)


def test_close_hotkeys_are_configurable_persisted_and_resettable(window):
    assert window.defaultHotkeys["actionCloseDocument"] == "Ctrl+W"
    assert "actionCloseAllDocuments" in window.defaultHotkeys
    window.optionsDlg.load_values()
    window.optionsDlg.restore_defaults()
    assert window.optionsDlg.hotkeyEditor.values["actionCloseDocument"] == "Ctrl+W"
    shortcuts = dict(window.hotkeys, actionCloseDocument="Ctrl+Shift+W")
    window.setHotkeys(shortcuts)
    window.saveSettings()
    restored = MainWindow()
    try:
        assert restored.actionCloseDocument.shortcut().toString() == "Ctrl+Shift+W"
        assert restored.defaultHotkeys["actionCloseDocument"] == "Ctrl+W"
    finally:
        restored.deleteLater()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("defaultUnits", "inch"),
        ("ignoreBlockSkip", True),
        ("latheGcodeSystem", "B"),
        ("correctionEnabled", False),
        ("sinumerik840dSl", False),
        ("homeConfigured", False),
        ("xPosMach", 99.0),
        ("arcTolerance", 0.02),
        ("minimumChordLength", 0.9),
        ("maxGeneratedMotions", 1000),
        ("rotaryKinematics", "4ax_table_a"),
    ],
)
def test_shared_cnc_changes_invalidate_inactive_trace(window, name, value):
    window.ui.editor.setText("G0 X1\nG1 X2 F100\nM30")
    window.updateData(show_errors=False)
    window.newFile()
    setattr(window, name, value)
    assert window._activate_document(0)
    assert window._plot_source_stale
    assert window._parsed_program_cache is None
    assert window._deferred_execution_result is None
    assert window._deferred_execution_source is None
    assert window.executionStatusLabel.text() == "STALE"


def test_wcs_edits_are_shared_but_invalidate_old_trace(window):
    window.ui.editor.setText("G54 G0 X1\nM30")
    window.updateData(show_errors=False)
    window.newFile()
    window.wcsOffsets[54] = (25.0, 0.0, 0.0)
    assert window._activate_document(0)
    assert window._plot_source_stale
    assert window.wcsDlg.ui.g54X.value() == 25.0


def test_stock_and_stl_history_belong_to_each_document(window):
    window.millingStockManual = True
    window.millingStockXMinus = -75.0
    window.turnStockDiameter = 123.0
    window._stock_manual_override = True
    mesh = mesh_from_triangles(np.array([[[0, 0, 0], [10, 0, 0], [0, 10, 0]]], dtype=np.float32))
    window._add_stl_mesh(mesh, "first.stl")
    window._record_stl_edit()
    first_object = window._stl_entries[0].obj
    window.newFile()
    assert not window._stl_entries
    assert window.stlObjectsDock.objectList.count() == 0
    assert not window._stl_undo and not window._stl_redo
    assert not window.millingStockManual
    assert not window._stock_manual_override
    assert window.turnStockDiameter != 123.0
    window.millingStockXMinus = -25.0
    window._add_stl_mesh(mesh, "second.stl")
    assert window._activate_document(0)
    assert window.millingStockManual
    assert window.millingStockXMinus == -75.0
    assert window.turnStockDiameter == 123.0
    assert window._stl_entries[0].obj is first_object
    assert window.stlObjectsDock.objectList.count() == 1
    assert window._stl_undo
    assert window._activate_document(1)
    assert window.millingStockXMinus == -25.0
    assert window._stl_entries[0].obj.name == "second.stl"


def test_visible_tokens_follow_active_document_and_statistics_hide(window):
    window.ui.editor.setText("#1=11\nG0 X1\nM30")
    window.updateData(show_errors=False)
    window.newFile()
    window.ui.editor.setText("#1=22\nG0 X2\nM30")
    window.updateData(show_errors=False)
    window.tokensDlg.show()
    assert window.tokensDlg.model.item(0, 1).text() == "#1=22"
    window.statistics()
    assert window.statisticsDlg.isVisible()
    assert window._activate_document(0)
    assert not window.statisticsDlg.isVisible()
    assert window.tokensDlg.isVisible()
    assert window.tokensDlg.model.item(0, 1).text() == "#1=11"
    window.tokensDlg.ui.tabWidget.setCurrentWidget(window.tokensDlg.ui.macroVariablesTab)
    assert window._activate_document(1)
    values = {
        window.tokensDlg.variables_model.item(row, 0).text(): window.tokensDlg.variables_model.item(row, 1).text()
        for row in range(window.tokensDlg.variables_model.rowCount())
    }
    assert values["#1"] == "22"
    window.tokensDlg.hide()


def test_new_and_close_last_reset_status_and_document_metadata(window):
    window.ui.editor.setText("G0 X1\nM30")
    window.updateData(show_errors=False)
    window._last_execution_ms = 1234.0
    window.newFile()
    assert window.timeStatusLabel.text() == "Exec: --"
    assert window._document_source_dialect == "fanuc"
    assert window.closeDocument()
    window.ui.editor.setModified(False)
    assert window.closeDocument()
    assert len(window._documents) == 1
    assert window.timeStatusLabel.text() == "Exec: --"
    assert window.ui.editor.text() == ""
    assert not window.latheMode


def test_open_into_explicit_empty_buffer_keeps_selected_turning_mode(window, tmp_path):
    window.ui.editor.setText("G0 X1")
    window.newFile()
    window.ui.actionLatheMode.setChecked(True)
    path = tmp_path / "turn.nc"
    path.write_text("G18 G0 X20 Z0\nG1 Z-10 F100\nM30", encoding="utf-8")
    assert window.loadFile(str(path))
    assert len(window._documents) == 2
    assert window.latheMode
    window.updateData(show_errors=False)
    assert window.execution_result.ok


def test_exit_keeps_active_stock_preferences_in_settings(window):
    window.newFile()
    window.millingStockXMinus = -88.0
    window.turnStockDiameter = 77.0
    assert window.closeAllDocuments(exiting=True)
    assert settings.get_settings().value("STOCK/MILL_X_MINUS", type=float) == -88.0
    assert settings.get_settings().value("STOCK/DIAMETER", type=float) == 77.0


def test_reactivating_file_checks_external_changes(window, tmp_path, monkeypatch):
    path = tmp_path / "watched.nc"
    path.write_text("G0 X1", encoding="utf-8")
    assert window.loadFile(str(path))
    window.newFile()
    path.write_text("G0 X999", encoding="utf-8")
    calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: calls.append(args) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(window, "isVisible", lambda: True)
    assert window._activate_document(0)
    assert window._document_change_timer.isActive()
    window._document_change_timer.stop()
    window._check_document_disk_change()
    assert calls
    assert window.ui.editor.text() == "G0 X999"
    assert len(window._documents) == 2


def test_save_as_cannot_overwrite_another_open_document(window, tmp_path, monkeypatch):
    first = tmp_path / "first.nc"
    first.write_text("G0 X1", encoding="utf-8")
    assert window.loadFile(str(first))
    window.newFile()
    window.ui.editor.setText("G0 X2")
    calls = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: calls.append(args))
    assert not window.saveFile(str(first))
    assert first.read_text(encoding="utf-8") == "G0 X1"
    assert window.ui.editor.text() == "G0 X2"
    assert calls


def test_failed_save_stops_close_all_without_losing_unsaved_text(window, monkeypatch):
    window.newFile()
    QTest.keyClicks(window.ui.editor, "G0 X2")
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(window, "save", lambda: False)
    assert not window.closeAllDocuments()
    assert len(window._documents) == 2
    assert window.ui.editor.text() == "G0 X2"
    assert window.ui.editor.isModified()


def test_switch_restores_selection_and_file_encoding(window, tmp_path):
    path = tmp_path / "legacy.ptp"
    path.write_bytes("G0 X1\nG1 X2 F100\nM30\n".encode("cp1251"))
    assert window.loadFile(str(path))
    window._document_encoding = "cp1251"
    window.ui.editor.setSelection(0, 1, 1, 4)
    selection = window.ui.editor.getSelection()
    window.newFile()
    assert window._document_encoding is None
    assert window._activate_document(0)
    assert window.ui.editor.getSelection() == selection
    assert window._document_encoding == "cp1251"


def test_unchanged_shared_settings_keep_cache_current(window):
    window.ui.editor.setText("G0 X1\nM30")
    window.updateData(show_errors=False)
    cached = window.execution_result
    window.newFile()
    assert window._activate_document(0)
    assert window.execution_result is cached
    assert not window._plot_source_stale


def test_reentrant_switch_and_reload_are_blocked(window, tmp_path):
    path = tmp_path / "first.nc"
    path.write_text("G0 X1", encoding="utf-8")
    window.loadFile(str(path))
    window.newFile()
    window._document_switching = True
    try:
        assert not window._activate_document(0)
        assert not window.loadFile(str(path), reload=True)
        assert len(window._documents) == 2
    finally:
        window._document_switching = False


def test_toolbar_customization_contains_document_close_commands(window):
    assert "actionCloseDocument" in window.toolbarSettings.commands
    assert "actionCloseAllDocuments" in window.toolbarSettings.commands
    assert not window.toolbarSettings.defaults["actionCloseDocument"]
    selection = dict(window.toolbarSettings.selected, actionCloseDocument=True)
    window.toolbarSettings.apply(selection)
    assert window.actionCloseDocument in window.ui.fileToolBar.actions()
    assert not window.actionCloseDocument.icon().isNull()


def test_find_replace_targets_only_selected_document(window):
    window.ui.editor.setText("G0 X11")
    window.newFile()
    window.ui.editor.setText("G0 X22")
    window.findDlg.show()
    window.findDlg.ui.lineEditFind.setText("X11")
    window.findDlg.ui.lineEditReplace.setText("X33")
    assert window._activate_document(0)
    assert window.replaceAll("X11", "X33", False, False) == 1
    assert window.ui.editor.text() == "G0 X33"
    assert window._activate_document(1)
    assert window.ui.editor.text() == "G0 X22"
    window.findDlg.hide()


def test_new_document_inherits_machine_mode_without_manual_stock(window):
    window.ui.actionLatheMode.setChecked(True)
    window._stock_manual_override = True
    window.newFile()
    assert window.latheMode
    assert not window._stock_manual_override


def test_nested_modal_editor_blocks_programmatic_document_switch(window):
    window.newFile()
    dialog = QDialog(window)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.show()
    try:
        assert QApplication.activeModalWidget() is dialog
        assert not window._activate_document(0)
        assert window._active_document_index == 1
    finally:
        dialog.reject()
    assert window._activate_document(0)


def test_external_reload_waits_for_pending_dialog_without_ignoring_version(window, tmp_path, monkeypatch):
    path = tmp_path / "pending.nc"
    path.write_text("G0 X1", encoding="utf-8")
    window.loadFile(str(path))
    path.write_text("G0 X1234", encoding="utf-8")
    calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: calls.append(args) or QMessageBox.StandardButton.Yes)
    window.exportDlg.show()
    window._check_document_disk_change()
    assert not calls
    assert window._ignored_document_signature is None
    window.exportDlg.reject()
    window._check_document_disk_change()
    assert calls
    assert window.ui.editor.text() == "G0 X1234"


def test_hidden_stl_panel_stays_hidden_when_document_is_restored(window):
    mesh = mesh_from_triangles(np.array([[[0, 0, 0], [10, 0, 0], [0, 10, 0]]], dtype=np.float32))
    window._add_stl_mesh(mesh, "part.stl")
    window.stlObjectsDock.hide()
    window.newFile()
    assert window._activate_document(0)
    assert window._stl_entries
    assert window.stlObjectsDock.isHidden()


def test_switch_during_stock_playback_removes_previous_simulation(window):
    window.ui.actionLatheMode.setChecked(True)
    window.stockEnabled = True
    window.stockConfigured = True
    window.ui.editor.setText("G21 G18 G90\nG0 X20 Z1\nG1 Z-5 F100\nM30")
    assert window.updateData(show_errors=False)
    result = window.execution_result
    window.ui.actionStockPlayback.setChecked(True)
    assert window._stock_animation_active
    timeline = window._stock_timeline
    window.ui.horizontalSlider.setValue(1)
    window.newFile()
    assert not window._stock_animation_active
    assert window._stock_timeline is None
    assert not window.ui.actionPlay.isChecked()
    assert not window.ui.actionStockPlayback.isChecked()
    assert window._activate_document(0)
    assert window.execution_result is result
    assert window.ui.horizontalSlider.value() == 1
    assert not window._stock_animation_active
    window.ui.actionStockPlayback.setChecked(True)
    assert window._stock_animation_active
    assert window._stock_timeline is not timeline
    assert window._activate_document(1)
    assert window._stock_timeline is None


@pytest.mark.parametrize("selected", [None, "forward", "backward"])
def test_switch_restores_editor_scroll_and_caret(window, selected):
    window.show()
    QApplication.processEvents()
    editor = window.ui.editor
    editor.setText(("G1 X1 " + "Y2 " * 400 + "\n") * 100)
    if selected == "forward":
        editor.setSelection(40, 80, 42, 120)
    elif selected == "backward":
        editor.setSelection(42, 120, 40, 80)
    else:
        editor.setCursorPosition(42, 120)
    editor.setFirstVisibleLine(35)
    editor.horizontalScrollBar().setValue(180)
    expected = (
        editor.getCursorPosition(),
        editor.getSelection(),
        editor.firstVisibleLine(),
        editor.horizontalScrollBar().value(),
    )
    assert expected[-1] > 0
    window.newFile()
    assert window._active_document_index == 1
    editor.setText("M30")
    assert window._activate_document(0)
    assert (
        editor.getCursorPosition(),
        editor.getSelection(),
        editor.firstVisibleLine(),
        editor.horizontalScrollBar().value(),
    ) == expected


def test_simulation_bundle_survives_reload_and_document_switch(window, tmp_path, monkeypatch):
    import json

    from app.application import _start_cli_simulation
    from app.integration.minicad_bundle import read_bundle

    path = tmp_path / "program.nc"
    path.write_text("G90 G17 G21\nT1 M6\nG0 X0 Y0 Z5\nG1 Z-1 F100\nG1 X20\nM30\n")
    manifest = tmp_path / "simulation.json"
    data = {
        "version": 1,
        "units": "mm",
        "nc": path.name,
        "stock": dict(zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), (-5, 105, -5, 105, -10, 0))),
        "tool": {"number": 1, "diameter": 10, "type": "mill_flat"},
        "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
    }
    manifest.write_text(json.dumps(data))
    monkeypatch.setattr(window, "ensure_simulation_ready", lambda _turning: None)
    _start_cli_simulation(window, path, "fanuc_mill", read_bundle(manifest))
    assert window.millingTools["T1"]["diameter"] == 10
    assert window._simulation_bundle_path == manifest
    assert window.loadFile(str(path), reload=True)
    assert window.millingTools["T1"]["diameter"] == 10
    data["tool"]["diameter"] = 6
    manifest.write_text(json.dumps(data))
    path.write_text(path.read_text().replace("X20", "X30"))
    assert window.loadFile(str(path), reload=True)
    assert window.millingTools["T1"]["diameter"] == 6
    assert "X30" in window.ui.editor.text()
    assert window.updateData()
    assert window.millingTools["T1"]["diameter"] == 6
    other = tmp_path / "other.nc"
    other.write_text("G21\nT2 M6\nM30\n")
    assert window.loadFile(str(other))
    assert window._simulation_bundle_path is None
    assert window._activate_document(0)
    assert window._simulation_bundle_path == manifest
    assert window.millingTools["T1"]["diameter"] == 6


def test_repeated_simulation_refreshes_inactive_document_without_duplicating_tabs(window, tmp_path, monkeypatch):
    import json

    from app.application import _start_cli_simulation
    from app.integration.minicad_bundle import read_bundle

    path = tmp_path / "program.nc"
    path.write_text("G90 G17 G21\nT1 M6\nG0 X0 Y0 Z5\nM30\n")
    manifest = tmp_path / "simulation.json"
    data = {
        "version": 1,
        "units": "mm",
        "nc": path.name,
        "stock": dict(zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), (-5, 105, -5, 105, -10, 0))),
        "tool": {"number": 1, "diameter": 10, "type": "mill_flat"},
        "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
    }
    manifest.write_text(json.dumps(data))
    monkeypatch.setattr(window, "ensure_simulation_ready", lambda _turning: None)
    _start_cli_simulation(window, path, "fanuc_mill", read_bundle(manifest))
    other = tmp_path / "other.nc"
    other.write_text("G21\nT2 M6\nM30\n")
    assert window.loadFile(str(other))
    path.write_text(path.read_text().replace("X0", "X30"))
    data["tool"]["diameter"] = 6
    manifest.write_text(json.dumps(data))
    _start_cli_simulation(window, path, "fanuc_mill", read_bundle(manifest))
    assert len(window._documents) == 2
    assert "X30" in window.ui.editor.text()
    assert window.millingTools["T1"]["diameter"] == 6
    _start_cli_simulation(window, other, "fanuc_mill")
    assert len(window._documents) == 2
    assert window._simulation_bundle_path is None
    assert "T2" in window.ui.editor.text()
