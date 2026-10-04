"""End-to-end smoke test for a deterministic daily desktop editing workflow.

Scope and limitations:

- Only widget, action and model state is asserted; rendered pixels and OpenGL
  image quality are never verified, especially on the default ``offscreen``
  platform.
- File dialogs and message boxes are stubbed, so native dialog behavior and
  real file-system prompts are not exercised.
- Modal dialogs (the Tool Library editor) block their caller, so the test
  drives them with ``QTimer.singleShot`` rather than waiting for a human.
- The SINUMERIK export uses the resolved (Expanded Execution) conversion;
  Full Program dialect conversion of this fixture is rejected because it would
  change machine signals.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from app.gcode.export import EXPANDED_EXECUTION_MODE
from app.gcode.kernel import execute
from app.main_window import MainWindow
from app.ui.windows import main_window_file_ops

PROGRAM_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "milling" / "plate_setup_complete.nc"
STL_FIXTURE = Path(__file__).resolve().parents[2] / "stl" / "test2.stl"

# The smoke scenario verifies GUI state behind the dialogs' and dock's public controls.
# pylint: disable=protected-access

SINUMERIK_ISO_TARGET = 2


def _is_interactive() -> bool:
    """A visible Qt platform means a human is watching this run."""
    return os.environ.get("QT_QPA_PLATFORM", "offscreen").strip().lower() not in {"offscreen", "minimal", ""}


def _step_delay_ms() -> int:
    """Read the visual pause, falling back to the default on invalid input."""
    try:
        return max(0, int(os.environ.get("EASY_GCODE_SMOKE_DELAY_MS", "600")))
    except ValueError:
        return 600


INTERACTIVE = _is_interactive()
STEP_DELAY_MS = _step_delay_ms()


def _settle(app, label=""):
    """Drain pending Qt events; pause between steps only on a visible platform."""
    app.processEvents()
    if INTERACTIVE:
        if label:
            print(f"[smoke] {label}", flush=True)
        QTest.qWait(STEP_DELAY_MS)


def _dispose_window(window):
    window.autoUpdateTimer.stop()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _install_dialog_stubs(monkeypatch, *, open_paths, save_paths):
    """Answer file dialogs from a path map and record the message boxes used."""
    information = []
    warnings = []
    criticals = []
    export_errors = []

    def fake_open_file_name(_parent, caption, *_args, **_kwargs):
        if caption not in open_paths:
            pytest.fail(f"Unexpected open-file dialog: {caption}")
        return str(open_paths[caption]), ""

    def fake_save_file_name(_parent, caption, *_args, **_kwargs):
        if caption not in save_paths:
            pytest.fail(f"Unexpected save-file dialog: {caption}")
        return str(save_paths[caption]), main_window_file_ops.NC_PROGRAM_FILTER

    monkeypatch.setattr(main_window_file_ops.QFileDialog, "getOpenFileName", fake_open_file_name)
    monkeypatch.setattr(main_window_file_ops.QFileDialog, "getSaveFileName", fake_save_file_name)
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **_kwargs: information.append(args) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **_kwargs: warnings.append(args) or QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **_kwargs: criticals.append(args) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        main_window_file_ops,
        "_show_export_error",
        lambda *args, **_kwargs: export_errors.append(args),
    )
    return information, warnings, criticals, export_errors


def _open_setup_program(window, app):
    """Open the plate-setup program and require a complete execution."""
    window.ui.actionOpen.trigger()
    _settle(app, "open plate setup program")
    window.autoUpdateTimer.stop()
    assert Path(window.curFile) == PROGRAM_FIXTURE
    window.ui.actionRefresh.trigger()
    _settle(app, "refresh execution")
    assert window.execution_result is not None
    assert window.execution_result.ok
    assert window.execution_result.complete
    assert window.execution_result.motions
    return len(window.execution_result.motions)


def _import_part_model(window, app):
    """Import the matching STL model and reveal the object dock."""
    window.ui.actionImportSTL.trigger()
    _settle(app, "import STL model")
    assert len(window._stl_entries) == 1
    window._stl_panel_toggle_action.setChecked(True)
    _settle(app, "show STL dock")
    return window.stlObjectsDock


def _save_working_copy(window, app, saved):
    """Save As writes a separate working copy and switches the document to it."""
    window.ui.actionSaveAs.trigger()
    _settle(app, "save working copy")
    assert saved.exists()
    assert Path(window.curFile) == saved


def _export_sinumerik_iso(window, app, exported, source_motions):
    """Export the setup as SINUMERIK 840D ISO-M and re-execute it."""
    window.ui.actionExportData.trigger()
    _settle(app, "open export dialog")
    dialog = window.exportDlg
    assert dialog.isVisible()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.targetCncCombo.setCurrentIndex(SINUMERIK_ISO_TARGET)
    assert dialog.targetCncCombo.currentIndex() == SINUMERIK_ISO_TARGET
    dialog.accept()
    _settle(app, "export SINUMERIK ISO-M")

    assert exported.exists()
    assert exported.stat().st_size > 0
    text = exported.read_text(encoding="utf-8")
    assert text.splitlines()[0].strip() == "G291"
    assert "T10" in text
    converted = execute(text, language="fanuc_mill", source_dialect="sinumerik")
    assert converted.ok
    assert converted.complete
    assert len(converted.motions) == source_motions


def _move_stl_to(window, panel, target, app):
    """Place the STL base point at an explicit world position."""
    panel.operationCombo.setCurrentIndex(1)
    panel.positionX.setValue(target[0])
    panel.positionY.setValue(target[1])
    panel.positionZ.setValue(target[2])
    panel.moveButton.click()
    _settle(app, "move STL to X100")
    assert window._stl_entries[0].obj.world_pivot() == pytest.approx(target)


def _shift_g54_x(window, app, value):
    """Set the G54 X offset through the real WCS dialog."""
    window.ui.actionWCS.trigger()
    _settle(app, "open WCS")
    dialog = window.wcsDlg
    assert dialog.isVisible()
    dialog.ui.g54X.setValue(value)
    dialog.accept()
    _settle(app, "apply G54 X100")
    assert window.wcsOffsets[54][0] == pytest.approx(value)


def _section_stl_along_y(window, panel, app):
    """Cut the placed model with a Y section plane through its middle."""
    bounds = window._stl_entries[0].overlay.bounds
    panel.operationCombo.setCurrentIndex(5)
    panel.sectionAxis.setCurrentText("Y")
    panel.sectionOffset.setValue((bounds[1][0] + bounds[1][1]) / 2.0)
    panel.sectionButton.click()
    _settle(app, "section STL along Y")
    assert window._stl_section_spec is not None
    assert window._stl_section_spec[1] == "Y"


def _change_program_tool(window, app):
    """Edit the first program tool through the Tool Library's modal editor."""
    window.ui.actionToolLibrary.trigger()
    _settle(app, "open tool library")
    dialog = window.toolLibraryDlg
    assert dialog.isVisible()
    table = dialog.pages["milling"]["program"]
    assert table.rowCount() >= 1
    table.selectRow(0)
    key = table.item(0, 0).text()
    before = float(window.millingTools[key]["diameter"])
    target = before + 1.0
    opened = []

    def edit_open_editor():
        editors = [
            child
            for child in dialog.findChildren(QDialog)
            if child.isVisible() and hasattr(child, "diameter") and hasattr(child, "validateAndAccept")
        ]
        assert editors, "milling tool editor did not open"
        opened.append(editors[0])
        editors[0].diameter.setValue(target)
        editors[0].validateAndAccept()

    QTimer.singleShot(0, edit_open_editor)
    dialog.edit_program_tool("milling")
    _settle(app, "edit program tool")
    assert opened
    assert float(window.millingTools[key]["diameter"]) == pytest.approx(target, abs=1e-6)
    dialog.close()
    _settle(app, "close tool library")


def _export_statistics_html(window, app, report_path):
    """Open Statistics and write its portable HTML report."""
    window.ui.actionStatistics.trigger()
    _settle(app, "open statistics")
    dialog = window.statisticsDlg
    assert dialog.isVisible()
    assert dialog.reportText.toPlainText().strip()
    assert dialog.exportHtmlButton.isEnabled()
    dialog.exportHtmlButton.click()
    _settle(app, "export statistics HTML")
    assert report_path.exists()
    assert report_path.stat().st_size > 0
    assert "<html" in report_path.read_text(encoding="utf-8").lower()
    dialog.close()
    _settle(app, "close statistics")


def _exercise_options_dialog(window, app):
    """Toggle a broad set of persistent options and confirm they were applied."""
    window.ui.actionOptions.trigger()
    _settle(app, "open options")
    dialog = window.optionsDlg
    assert dialog.isVisible()
    ui = dialog.ui
    ui.showRapidCheck.setChecked(False)
    ui.stlWireframeCheck.setChecked(True)
    ui.axesCheck.setChecked(False)
    ui.whitespaceCheck.setChecked(True)
    ui.eolCheck.setChecked(True)
    ui.lineWidthSpin.setValue(2.5)
    ui.playbackSpeedSlider.setValue(5)
    _settle(app, "edit options")
    dialog.accept()
    _settle(app, "apply options")

    assert window.plotShowRapid is False
    assert window.stlWireframe is True
    assert window.plotAxes is False
    assert window.spaceVisible is True
    assert window.eolVisible is True
    assert window.plotLineWidth == pytest.approx(2.5)
    assert window.playbackSpeed == 5


def _visit_tool_dialogs(window, app):
    """Open the assistant dialogs a user reaches from the CNC functions menu."""
    for action_name, attribute in (
        ("actionHoleCalculator", "holeCalculatorDlg"),
        ("actionPocketCalculator", "pocketCalculatorDlg"),
        ("actionTokens", "tokensDlg"),
        ("actionSnippets", "snippetsDlg"),
    ):
        getattr(window.ui, action_name).trigger()
        _settle(app, action_name)
        dialog = getattr(window, attribute)
        assert dialog.isVisible(), action_name
        dialog.close()
        _settle(app, f"{action_name} closed")

    window.holeCalculatorDlg.show()
    window.holeCalculatorDlg.ui.patternTabs.setCurrentIndex(1)
    _settle(app, "hole calculator grid pattern")
    window.holeCalculatorDlg.close()

    window.pocketCalculatorDlg.show()
    window.pocketCalculatorDlg.ui.rectangularRadio.setChecked(True)
    _settle(app, "pocket calculator rectangular pattern")
    window.pocketCalculatorDlg.close()

    assert window.tokensDlg.model.rowCount() >= 1

    # Stock is only offered in turning mode.
    window.ui.actionLatheMode.setChecked(True)
    _settle(app, "toggle lathe mode")
    window.ui.actionStock.trigger()
    _settle(app, "open stock")
    assert window.stockDlg.isVisible()
    window.stockDlg.close()
    _settle(app, "close stock")
    window.ui.actionLatheMode.setChecked(False)
    _settle(app, "toggle mill mode")


def _run_interactive_extras(window, app):
    """Slower scenarios that only make sense while a human watches the window."""
    print("[smoke] --- interactive extras ---", flush=True)
    _exercise_options_dialog(window, app)
    _visit_tool_dialogs(window, app)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_daily_gui_workflow_stays_inside_sandbox(qt_app, monkeypatch, tmp_path):
    """Walk one deterministic setup-to-report workflow through the real GUI surface."""
    saved = tmp_path / "plate_setup_complete_copy.nc"
    exported = tmp_path / "plate_setup_sinumerik.mpf"
    html_report = tmp_path / "plate_setup_statistics.html"

    information, warnings, criticals, export_errors = _install_dialog_stubs(
        monkeypatch,
        open_paths={"Open": PROGRAM_FIXTURE, "Import STL": STL_FIXTURE},
        save_paths={"Save As": saved, "Export": exported, "Export HTML": html_report},
    )

    window = MainWindow()
    try:
        window.show()
        _settle(qt_app, "show main window")

        # 1. Open the milling setup program and import its matching stock model.
        source_motions = _open_setup_program(window, qt_app)
        panel = _import_part_model(window, qt_app)

        # 2. Save a working copy, then export a SINUMERIK ISO-M program for it.
        _save_working_copy(window, qt_app, saved)
        _export_sinumerik_iso(window, qt_app, exported, source_motions)
        assert any(str(exported) in str(part) for message in information for part in message)

        # 3. Place the stock at X100 and shift the G54 origin to match.
        _move_stl_to(window, panel, (100.0, 0.0, 0.0), qt_app)
        _shift_g54_x(window, qt_app, 100.0)

        # 4. Inspect a Y section of the placed model, then hide the STL dock.
        _section_stl_along_y(window, panel, qt_app)
        window._stl_panel_toggle_action.setChecked(False)
        _settle(qt_app, "hide STL objects")
        assert not panel.isVisible()
        assert not window._stl_panel_toggle_action.isChecked()

        # 5. Change a program tool and export the statistics HTML report.
        _change_program_tool(window, qt_app)
        _export_statistics_html(window, qt_app, html_report)

        # 6. Change a persistent option and a custom hotkey through the real Options dialog.
        previous_grid = window.plotGrid
        window.ui.actionOptions.trigger()
        _settle(qt_app, "open options")
        assert window.optionsDlg.isVisible()
        window.optionsDlg.ui.gridCheck.setChecked(not previous_grid)
        assert window.optionsDlg.hotkeyEditor.assign("actionToolLibrary", "Ctrl+Alt+L")
        window.optionsDlg.accept()
        _settle(qt_app, "apply options")
        assert window.plotGrid == (not previous_grid)
        assert window.ui.actionToolLibrary.shortcut() == QKeySequence("Ctrl+Alt+L")

        # 7. Send the new shortcut through Qt's key event path rather than triggering QAction directly.
        window.toolLibraryDlg.hide()
        window.activateWindow()
        window.ui.editor.setFocus()
        _settle(qt_app, "focus editor")
        QTest.keyClick(
            window.ui.editor,
            Qt.Key.Key_L,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
        )
        _settle(qt_app, "send shortcut")
        assert window.toolLibraryDlg.isVisible()
        window.toolLibraryDlg.close()
        _settle(qt_app, "close tool library")

        # 8. Options.accept() persists both values; verify that a fresh MainWindow restores them.
        window.settings.sync()
        restored = MainWindow()
        try:
            assert restored.plotGrid == (not previous_grid)
            assert restored.ui.actionToolLibrary.shortcut() == QKeySequence("Ctrl+Alt+L")
        finally:
            _dispose_window(restored)

        assert not warnings
        assert not criticals
        assert not export_errors

        # 9. A visible run keeps the same window open longer and walks extra dialogs.
        if INTERACTIVE:
            _run_interactive_extras(window, qt_app)
    finally:
        # A failed assertion must not leave a save prompt blocking the suite.
        window.ui.editor.setModified(False)
        _dispose_window(window)
