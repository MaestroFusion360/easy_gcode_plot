"""Four-stage isolated GUI sandbox; EASY_GCODE_SMOKE_DEMO=1 enables visual pacing.

File pickers receive fixture paths. Dialogs/actions remain real; assertions
inspect model and scene state rather than pixels. Outputs stay in tmp_path.
"""

from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from app import settings as app_settings
from app.gcode.export import EXPANDED_EXECUTION_MODE
from app.gcode.kernel import execute
from app.main_window import MainWindow
from app.ui.windows import main_window_file_ops

# pylint: disable=protected-access
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
DEMO = os.environ.get("EASY_GCODE_SMOKE_DEMO") == "1"
DELAY_MS = max(0, int(os.environ.get("EASY_GCODE_SMOKE_DELAY_MS", "1000")))
IMPELLER_TOOL = {
    "type": "taper_ball_mill",
    "diameter": 4.0,
    "cornerRadius": 0.0,
    "fluteLength": 25.0,
    "bodyLength": 25.0,
    "length": 50.0,
    "taperAngle": 6.0,
    "description": "TAPER BALL MILL D4",
}


def _settle(app, label, factor=1):
    app.processEvents()
    print(f"[sandbox] {label}", flush=True)
    if DEMO:
        QTest.qWait(DELAY_MS * factor)


def _wait(app, condition, label, timeout=60):
    deadline = monotonic() + timeout
    while not condition():
        app.processEvents()
        assert monotonic() < deadline, f"Timed out: {label}"


def _record(results, stage, errors):
    assert not errors, f"{stage}: {errors}"
    results.append((stage, "PASS"))


def _dispose(window):
    window.ui.editor.setModified(False)
    window.autoUpdateTimer.stop()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _summary(window, results, error=None):
    text = "\n".join(f"{name}: {status}" for name, status in results)
    text += "\n\n" + (f"Sandbox FAILED: {error}" if error else "Sandbox completed successfully")
    print(text, flush=True)
    if DEMO:
        box = QMessageBox(window)
        box.setObjectName("sandboxResult")
        box.setWindowTitle("Easy G-Code Plot Sandbox")
        box.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
        box.setText(text)
        QTimer.singleShot(max(3000, DELAY_MS * 4), box.accept)
        box.exec()


def _install_dialogs(monkeypatch, paths, exported):
    html_report = exported.with_suffix(".html")
    errors = []

    def open_file(_parent, caption, *_args, **_kwargs):
        assert caption in paths, f"Unexpected file picker: {caption}"
        return str(paths[caption]), ""

    def save_file(_parent, caption, *_args, **_kwargs):
        assert caption in {"Export", "Export HTML"}, f"Unexpected save picker: {caption}"
        if caption == "Export HTML":
            return str(html_report), "HTML (*.html)"
        return str(exported), main_window_file_ops.NC_PROGRAM_FILTER

    def unexpected(*args, **_kwargs):
        errors.append(str(args))
        return QMessageBox.StandardButton.Cancel

    def information(parent, title, text, *_args, **_kwargs):
        target = html_report if title == "Export HTML" else exported
        if title not in {"Export", "Export HTML"} or str(target) not in text or not target.exists():
            return unexpected(parent, title, text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(main_window_file_ops.QFileDialog, "getOpenFileName", open_file)
    monkeypatch.setattr(main_window_file_ops.QFileDialog, "getSaveFileName", save_file)
    monkeypatch.setattr(QMessageBox, "information", information)
    monkeypatch.setattr(QMessageBox, "warning", unexpected)
    monkeypatch.setattr(QMessageBox, "critical", unexpected)
    monkeypatch.setattr(main_window_file_ops, "_show_export_error", unexpected)
    return errors


def _new_program(window, app, *, turning=False, profile=None, home=(0, 100)):
    window.ui.editor.setModified(False)
    window.ui.actionNew.trigger()
    window.autoUpdateTimer.stop()
    assert not window.curFile and not window.ui.editor.text()
    assert not window.render_points and not window._stl_entries
    assert window._toolpath_item is None
    assert getattr(window, "_stock_item", None) not in window.ui.graphicsView.items
    _settle(app, "New: workspace cleared", 0)
    window.ui.actionLatheMode.setChecked(turning)
    if not turning:
        window.ui.action3D.trigger()
        assert window._view_mode == "3d"
        _settle(app, "ISO view", 0)
    if profile:
        _options(window, app, profile=profile)
    window.ui.actionWCS.trigger()
    dialog = window.wcsDlg
    assert dialog.isVisible()
    for code in range(54, 60):
        for axis in ("X", "Y", "Z"):
            getattr(dialog.ui, f"g{code}{axis}").setValue(0)
    dialog.ui.homeX.setValue(home[0])
    dialog.ui.homeY.setValue(0)
    dialog.ui.homeZ.setValue(home[1])
    dialog.ui.homeConfiguredCheck.setChecked(True)
    _settle(app, f"WCS: Home X={home[0]} Z={home[1]}", 2)
    dialog.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).click()
    assert window.homeConfigured
    assert window.xPosMach == home[0] / (2 if turning else 1)
    assert window.zPosMach == home[1]


def _open_fixture(window, app, paths, path):
    assert path.is_file(), path
    paths["Open"] = path
    previous = window.execution_result
    window.ui.actionOpen.trigger()
    window.autoUpdateTimer.stop()
    window.ui.actionRefresh.trigger()
    _wait(app, lambda: window.execution_result is not previous and not window._kernel_execution_active, str(path))
    assert Path(window.curFile) == path
    _settle(app, path.name, 2)
    return window.execution_result


def _playback(window, app, *, full=False, step_percent=25):
    if not window.ui.actionPlay.isEnabled():
        assert not window.execution_result.motions
        _settle(app, "Playback unavailable: kernel rejected the program", 2)
        return
    window.ui.horizontalSlider.setValue(0)
    if full or step_percent == 10:
        window.ui.playbackSpeedSlider.setValue(5)
    window.ui.actionPlay.trigger()
    assert window.ui.actionPlay.isChecked() and window.timer.isActive()
    if full:
        _complete_playback(window, app)
        _settle(app, "Full playback complete", 2)
        return
    _wait(app, lambda: window.ui.horizontalSlider.value() > 0, "playback advances")
    _settle(app, "Play: motion playback", 2)
    window.ui.actionPlay.setChecked(False)
    maximum = window.ui.horizontalSlider.maximum()
    for percent in range(step_percent, 100, step_percent):
        value = maximum * percent // 100
        window.ui.horizontalSlider.setValue(value)
        _settle(app, f"Playback {percent}% ({value}/{maximum})")
    window.ui.horizontalSlider.setValue(maximum - 1)
    window.ui.actionPlay.trigger()
    _wait(app, lambda: not window.ui.actionPlay.isChecked(), "playback finishes")
    assert window.ui.horizontalSlider.value() == maximum
    _settle(app, "Playback complete", 2)


def _complete_playback(window, app):
    """Visit every logical motion via timer events, without seeking the slider."""
    maximum = window.ui.horizontalSlider.maximum()
    window.timer.start(2 if DEMO else 0, Qt.TimerType.PreciseTimer, window)
    deadline = monotonic() + max(60, maximum * 0.03 + 30)
    while window.ui.actionPlay.isChecked():
        QTest.qWait(5 if DEMO else 1)
        assert monotonic() < deadline, "Timed out: full playback"
    app.processEvents()
    assert window.ui.horizontalSlider.value() == maximum
    assert not window.timer.isActive()


def _assert_execution(window, *, allowed=()):
    result = window.execution_result
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert result.motions and window.render_points
    assert {d.code for d in result.diagnostics} <= set(allowed), result.diagnostics
    assert window._toolpath_item in window.ui.graphicsView.items
    assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)
    return result


def _options(window, app, *, profile=None, appearance=False, stl_edges=None):
    window.ui.actionOptions.trigger()
    dialog = window.optionsDlg
    assert dialog.isVisible()
    _settle(app, "Options", 2)
    ui = dialog.ui
    original_width = window.plotLineWidth
    if appearance:
        ui.tabs.setCurrentWidget(ui.generalTab)
        ui.fileTypeCombo.setCurrentIndex(1)
        _settle(app, "Default syntax: ISO G-Code", 2)
        ui.themeCombo.setCurrentIndex(1)
        ui.tabs.setCurrentWidget(ui.plotTab)
        ui.gridCheck.setChecked(True)
        ui.gridStepSpin.setValue(20)
        _settle(app, "Plot settings")
        ui.tabs.setCurrentWidget(ui.colorsTab)
        ui.linearColorEdit.setText("#36d9ff")
        ui.arcColorEdit.setText("#ffb347")
        _settle(app, "Toolpath colors")
    if profile:
        ui.tabs.setCurrentWidget(ui.plotTab)
        index = ui.rotaryKinematicsCombo.findData(profile)
        assert index >= 0, profile
        ui.rotaryKinematicsCombo.setCurrentIndex(index)
        _settle(app, profile)
    if stl_edges is not None:
        ui.tabs.setCurrentWidget(ui.plotTab)
        ui.stlWireframeCheck.setChecked(stl_edges)
        _settle(app, "STL edges only")
    ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).click()
    _settle(app, "Options applied")
    if profile:
        assert window.rotaryKinematics == profile
    if stl_edges is not None:
        assert window.stlWireframe == stl_edges
    if appearance:
        assert window.defaultFileType == window.ui.fileTypeCombo.currentIndex() == 1
        assert window.ui.editor.lexer() is window.lexer
        assert window.uiTheme == "dark"
        assert window.plotLineWidth == window._toolpath_item.width == original_width
        assert window.plotLineColor == "#36d9ff" and window.plotArcColor == "#ffb347"
        assert window.plotGrid and window.plotGridStep == 20
        window.settings.sync()
        restored = MainWindow()
        try:
            assert restored.defaultFileType == 1 and restored.ui.editor.lexer() is restored.lexer
            assert restored.uiTheme == "dark" and restored.plotLineWidth == original_width
            assert restored.plotLineColor == "#36d9ff" and restored.plotGridStep == 20
        finally:
            _dispose(restored)


def _export(window, app, exported):
    source_count = len(window.execution_result.motions)
    window.ui.actionExportData.trigger()
    dialog = window.exportDlg
    assert dialog.isVisible()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.targetCncCombo.setCurrentIndex(0)
    _settle(app, "Export expanded FANUC", 2)
    dialog.accept()
    _wait(app, exported.exists, "export output")
    result = execute(
        exported.read_text(encoding="utf-8"),
        "fanuc_mill",
        home_x=window.xPosMach,
        home_y=window.yPosMach,
        home_z=window.zPosMach,
    )
    assert result.ok and result.complete, result.diagnostics
    assert not result.diagnostics, result.diagnostics
    assert len(result.motions) == source_count


def _statistics(window, app, report):
    window.ui.actionStatistics.trigger()
    dialog = window.statisticsDlg
    assert dialog.isVisible()
    all_tools = dialog.reportText.toPlainText()
    assert all_tools.strip() and dialog.toolSelect.count() > 1
    assert dialog.exportHtmlButton.isEnabled()
    _settle(app, "Statistics: all tools", 2)
    dialog.toolSelect.setCurrentIndex(1)
    assert dialog.toolSelect.currentData() is not None
    assert dialog.reportText.toPlainText() != all_tools
    _settle(app, "Statistics: selected tool", 2)
    dialog.toolSelect.setCurrentIndex(0)
    dialog.exportHtmlButton.click()
    assert report.is_file()
    html = report.read_text(encoding="utf-8")
    assert "<svg" in html and "<select" in html
    assert Path(window.curFile).name in html
    _settle(app, "Statistics: HTML exported")
    dialog.close()


def _stock(window, app):
    window.ui.actionStock.trigger()
    dialog = window.stockDlg
    assert dialog.isVisible()
    dialog.enabled.setChecked(True)
    dialog.outer.setValue(130)
    dialog.inner.setValue(0)
    dialog.length.setValue(55)
    dialog.front_z.setValue(1)
    dialog.accuracy.setValue(dialog.accuracy.maximum())
    _settle(app, "Stock configuration", 2)
    dialog.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).click()
    assert window.stockEnabled
    assert window.turnStockDiameter == 130
    assert window.turnStockInnerDiameter == 0
    assert window.turnStockLength == 55
    assert window.turnStockFrontZ == 1
    assert window.turnStockResolution == 0.1
    window.ui.playbackSpeedSlider.setValue(5)
    window.ui.actionPlay.setChecked(True)
    _wait(app, lambda: window._stock_animation_active, "stock playback")
    _wait(app, lambda: window.ui.horizontalSlider.value() > 0, "stock playback advances")
    _settle(app, "Play: complete Stock Removal", 2)
    timeline = window._stock_timeline
    assert timeline is not None
    initial = list(timeline.initial_material_intervals)
    maximum = window.ui.horizontalSlider.maximum()
    _complete_playback(window, app)
    assert timeline.material_intervals != initial
    assert window._stock_item in window.ui.graphicsView.items
    assert window._stock_item.last_stock_face_count > 0
    final = list(timeline.material_intervals)
    first_thread = next(index for index, motion in enumerate(timeline.motions) if motion.threading)
    timeline.set_motion_count(first_thread)
    before_thread_outer = list(timeline.outer)
    before_thread_inner = list(timeline.inner)
    timeline.set_motion_count(len(timeline.motions))
    assert timeline.outer == before_thread_outer, "Internal threading damaged the outside stock contour"
    assert all(after >= before for after, before in zip(timeline.inner, before_thread_inner))
    assert any(after > before for after, before in zip(timeline.inner, before_thread_inner))
    assert timeline.material_intervals == final
    window.ui.horizontalSlider.setValue(0)
    window.ui.horizontalSlider.setValue(maximum)
    assert timeline.material_intervals == final
    _settle(app, "Stock Removal complete", 2)
    window.ui.actionStop.trigger()


def _stl(window, app, paths, name):
    window.ui.actionClearSTL.trigger()
    paths["Import STL"] = ROOT / "stl" / name
    window.ui.actionImportSTL.trigger()
    _wait(app, lambda: len(window._stl_entries) == 1, "STL import")
    window._stl_panel_toggle_action.setChecked(True)
    panel = window.stlObjectsDock
    assert panel.isVisible()
    panel.objectList.setCurrentRow(0)
    assert not window.stlWireframe
    _settle(app, f"STL Objects: {name}", 2)
    if name == "test6.stl":
        _position_test6(window, panel, app)
    else:
        _section_test7(window, panel, app)
        _options(window, app, stl_edges=True)
    assert window._stl_entries[0].overlay.item in window.ui.graphicsView.items
    window.fitToView()
    window._stl_panel_toggle_action.setChecked(False)
    _settle(app, "STL and toolpath", 2)


def _position_test6(window, panel, app):
    panel.operationCombo.setCurrentIndex(0)
    panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("origin"))
    panel.pivotApplyButton.click()
    _settle(app, "Base Point: Origin")
    assert window._stl_entries[0].obj.pivot_mode == "origin"
    panel.operationCombo.setCurrentIndex(1)
    panel.positionX.setValue(0)
    panel.positionY.setValue(0)
    panel.positionZ.setValue(-100)
    _settle(app, "Position Z=-100")
    panel.moveButton.click()
    _settle(app, "Move Here")
    assert window._stl_entries[0].obj.world_pivot() == pytest.approx((0, 0, -100))
    assert window._stl_entries[0].overlay.bounds[2] == pytest.approx((-100, 0))


def _use_impeller_library_tool(window, app):
    """Verify that the unchanged opened source resolves the saved T60 snapshot."""
    opened_lines = window.ui.editor.text().splitlines()
    fixture_lines = (FIXTURES / "milling/sinumerik/impeller.mpf").read_text(encoding="utf-8").splitlines()
    unchanged = opened_lines == fixture_lines
    assert unchanged, "Sandbox must use the opened fixture without rewriting its source"
    assert window.millingTools["T60"] == IMPELLER_TOOL
    assert {motion.tool for motion in window.execution_result.motions if motion.tool} == {"T60"}
    _settle(app, "Impeller: saved T60 taper ball mill, D1")


def _section_test7(window, panel, app):
    original_triangles = window._stl_entries[0].obj.world_triangles().copy()
    original_pivot = tuple(window._stl_entries[0].obj.world_pivot())
    panel.operationCombo.setCurrentIndex(2)
    panel.rotateAxis.setCurrentText("Z")
    panel.rotateAngle.setValue(90)
    _settle(app, "Transform: rotate Z +90 degrees")
    panel.rotateButton.click()
    rotated = window._stl_entries[0].obj
    expected = original_triangles.copy()
    expected[..., 0] = original_pivot[0] - (original_triangles[..., 1] - original_pivot[1])
    expected[..., 1] = original_pivot[1] + (original_triangles[..., 0] - original_pivot[0])
    assert not np.allclose(rotated.world_triangles(), original_triangles)
    np.testing.assert_allclose(rotated.world_triangles(), expected, atol=1e-5)
    assert window._stl_entries[0].overlay.object is rotated
    _settle(app, "Rotate applied", 2)
    panel.operationCombo.setCurrentIndex(5)
    panel.sectionAxis.setCurrentText("Y")
    panel.sectionOffset.setValue(0)
    panel.sectionKeepSide.setCurrentIndex(0)
    _settle(app, "Section Y=0")
    panel.sectionButton.click()
    _settle(app, "Section Apply")
    assert window._stl_section_spec == (0, "Y", 0, True)
    assert window._stl_entries[0].section_overlay is not None
    assert panel.undoButton.isEnabled()
    panel.undoButton.click()
    _settle(app, "Section Undo")
    assert window._stl_section_spec is None
    assert window._stl_entries[0].section_overlay is None
    assert window._stl_entries[0].obj.world_pivot() == pytest.approx(original_pivot)
    assert window._stl_entries[0].obj == rotated
    np.testing.assert_allclose(window._stl_entries[0].obj.world_triangles(), expected, atol=1e-5)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_daily_gui_workflow_stays_inside_sandbox(qt_app, monkeypatch, tmp_path):
    """Exercise four programs, including complete native impeller playback."""
    if DEMO:
        assert qt_app.platformName() not in {"offscreen", "minimal"}, "Demo needs a visible Qt platform"
    paths = {}
    exported = tmp_path / "flange_expanded.nc"
    errors = _install_dialogs(monkeypatch, paths, exported)
    # Seed only the isolated test library, never the user's configured SQLite.
    saved_boring_tool = {
        "type": "diamond_80",
        "applications": ["id"],
        "tipOrientation": 2,
        "noseRadius": 0.4,
        "insertLength": 12.0,
        "description": "PROFILE ROUGHING2",
    }
    saved_tools = {
        "T0101": {
            "type": "diamond_80",
            "applications": ["od"],
            "tipOrientation": 3,
            "noseRadius": 0.4,
            "insertLength": 12.0,
            "description": "FACE1",
        },
        "T0202": {
            "type": "drill",
            "diameter": 15.0,
            "length": 100.0,
            "tipAngle": 118.0,
            "description": "DRILL1",
        },
        "T0303": saved_boring_tool,
        "T0404": {
            "type": "groove",
            "grooveCuttingPlane": "radial",
            "applications": ["od"],
            "tipOrientation": 3,
            "width": 3.0,
            "noseRadius": 0.2,
            "description": "GROOVE1",
        },
        "T0505": {
            "type": "groove",
            "grooveCuttingPlane": "radial",
            "applications": ["id"],
            "tipOrientation": 2,
            "width": 2.5,
            "noseRadius": 0.2,
            "description": "GROOVE3",
        },
        "T0606": {
            "type": "thread",
            "applications": ["id"],
            "tipOrientation": 6,
            "insertLength": 12.0,
            "threadAngle": 60.0,
            "threadTipWidth": 0.8,
            "threadCornerRadius": 0.1,
            "description": "THREAD1",
        },
    }
    library = app_settings.get_tool_library()
    for key, spec in saved_tools.items():
        library.save_tool("turning", key, spec)
    library.save_tool("milling", "T60", IMPELLER_TOOL)
    window = MainWindow()
    window.autoUpdateEnabled = False
    results = []
    stage = "FANUC Mill"
    guard = QTimer(window)

    def guard_modal():
        modal = qt_app.activeModalWidget()
        if isinstance(modal, QMessageBox) and modal.objectName() != "sandboxResult":
            errors.append(f"Unexpected modal: {modal.windowTitle()}: {modal.text()}")
            modal.reject()

    guard.timeout.connect(guard_modal)
    guard.start(100)
    try:
        window.resize(1280, 800)
        window.show()
        qt_app.processEvents()
        screen = window.screen().availableGeometry()
        frame = window.frameGeometry()
        frame.moveCenter(screen.center())
        window.move(frame.topLeft())
        _new_program(window, qt_app)
        _open_fixture(window, qt_app, paths, FIXTURES / "milling/fanuc/flange_plate_benchmark.nc")
        _assert_execution(window)
        assert window.millingTools["T2"]["type"] == "mill_flat" and window.millingTools["T2"]["diameter"] == 10
        assert window.millingTools["T4"]["type"] == "drill"
        assert not window._stl_entries
        _record(results, stage, errors)
        stage = "Options / Dark Theme / Plot Settings"
        _options(window, qt_app, appearance=True)
        _record(results, stage, errors)
        stage = "Statistics / HTML report"
        _statistics(window, qt_app, exported.with_suffix(".html"))
        _record(results, stage, errors)
        stage = "Export"
        _export(window, qt_app, exported)
        _playback(window, qt_app, full=True)
        _record(results, stage, errors)
        stage = "FANUC Turn"
        _new_program(window, qt_app, turning=True, home=(150, 10))
        _open_fixture(window, qt_app, paths, FIXTURES / "turning/lathe_cycles_example.nc")
        assert window.ui.editor.lexer() is window.lexer
        result = _assert_execution(window, allowed=("UNVERIFIED_TOOL_NOSE_COMPENSATION",))
        assert window.tools["T0303"] == saved_boring_tool
        assert window.tools == saved_tools
        assert library.get_tool("turning", "T0303").spec == saved_boring_tool
        assert any(m.cycle_generated and m.source_raw.startswith("G71") for m in result.motions)
        assert any(m.cycle_generated and m.source_raw.startswith("G76") for m in result.motions)
        _record(results, stage, errors)
        stage = "Stock Removal"
        _stock(window, qt_app)
        _record(results, stage, errors)
        stage = "SINUMERIK 3+2 + test6.stl"
        _new_program(window, qt_app, profile="5ax_table_ac_angled", home=(0, 100))
        _open_fixture(window, qt_app, paths, FIXTURES / "milling/sinumerik/5ax_test.mpf")
        assert window.ui.editor.lexer() is window.lexer
        result = _assert_execution(window, allowed=("UNVERIFIED_CUTTER_COMPENSATION",))
        assert result.kinematics_profile == "5ax_table_ac_angled"
        assert any(m.tool_orientation is not None for m in result.motions)
        assert len({m.tool_orientation for m in result.motions}) > 1
        _stl(window, qt_app, paths, "test6.stl")
        _playback(window, qt_app)
        _record(results, stage, errors)
        stage = "SINUMERIK Impeller + test7.stl"
        _new_program(window, qt_app, profile="5ax_table_bc_angled", home=(0, 300))
        _open_fixture(window, qt_app, paths, FIXTURES / "milling/sinumerik/impeller.mpf")
        _use_impeller_library_tool(window, qt_app)
        result = _assert_execution(window, allowed=("UNMODELED_SINUMERIK_NATIVE",))
        assert result.kinematics_profile == "5ax_table_bc_angled"
        _stl(window, qt_app, paths, "test7.stl")
        _playback(window, qt_app, step_percent=10)
        for diagnostic in result.diagnostics:
            print(f"[sandbox] {diagnostic.code}: {diagnostic.message}", flush=True)
        _record(results, stage, errors)
        results.append(("STL Objects / Origin / Position / Section / Undo", "PASS"))
        assert not errors, errors
        _summary(window, results)
    except Exception as exc:
        results.append((stage, "FAIL"))
        _summary(window, results, error=f"{stage}: {exc}")
        raise
    finally:
        guard.stop()
        _dispose(window)
