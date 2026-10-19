"""Real Qt regressions for state ownership, settings and MDI publication."""

# pylint: disable=protected-access

from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PyQt6.QtGui import QVector3D
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMenu

from app.gcode.kernel.types import TraceMotion
from app.main_window import MainWindow
from app.settings import get_settings
from app.ui.windows.main_window_documents import _DOCUMENT_STATE, _EXECUTION_SETTINGS
from app.ui.windows.main_window_execution import _PlotCompletion


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    application = qt_app
    get_settings().setValue("GENERAL/AUTO_UPDATE", False)
    owner = MainWindow()
    yield owner
    owner.optionsDlg.reject()
    owner.autoUpdateTimer.stop()
    owner.timer.stop()
    owner.deleteLater()
    application.processEvents()


def test_required_snapshot_fields_exist_at_startup(window):
    assert all(hasattr(window, name) for name in (*_DOCUMENT_STATE, *_EXECUTION_SETTINGS))
    assert window._document_encoding is None
    assert window._document_source_dialect == "fanuc"
    assert window._milling_retired_workers == set()


@pytest.mark.parametrize(
    "name",
    sorted(path.name for path in (Path(__file__).resolve().parents[1] / "fixtures/milling/heidenhain").glob("*.h")),
)
def test_every_native_fixture_completes_and_plots(window, name):
    fixture = Path(__file__).resolve().parents[1] / "fixtures/milling/heidenhain" / name
    window.zPosMach = 100
    window.homeConfigured = True
    assert window.loadFile(str(fixture))
    window.autoUpdateTimer.stop()
    if name == "6bas154.h":
        # Explicit reference cutter; APPR R3 is not a tool-radius declaration.
        window.millingTools["T4"] = {"type": "mill_flat", "diameter": 6.0, "length": 50.0}
    assert window.updateData(show_errors=False)
    result = window.execution_result
    assert result.ok and result.complete, result.diagnostics
    assert all(d.severity != "error" for d in result.diagnostics)
    if name == "cycles_itnc530.h":
        assert result.program_end == "M30"
        assert sum(event.drilling is not None for event in result.events) == 8
    assert window.render_points


def test_native_five_axis_cam_program_uses_selected_profile_and_plots(window):
    fixture = Path(__file__).resolve().parents[1] / "fixtures/milling/test_5ax/1001.h"
    window.rotaryKinematics = "5ax_table_ac"
    window.zPosMach = 100
    window.homeConfigured = True
    assert window.loadFile(str(fixture))
    window.autoUpdateTimer.stop()
    assert window.updateData(show_errors=False)
    result = window.execution_result
    assert result.source_dialect == "heidenhain"
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert result.kinematics_profile == "5ax_table_ac"
    assert window.render_points
    assert any(step.tool_axis_control and step.rotary_angles for step in result.execution_steps)


def test_native_rotary_notice_identifies_axes_and_offers_profile_selection(window):
    window.rotaryKinematics = None
    window.ui.editor.setText("TOOL CALL Z\nL A0 C0 FMAX")
    window.ui.fileTypeCombo.setCurrentIndex(2)
    assert not window.updateData(show_errors=False)
    assert window.execution_result.diagnostics[-1].code == "ROTARY_KINEMATICS_REQUIRED"
    assert "A, C" in window.rotaryKinematicsNotice.message.text()
    assert not window.rotaryKinematicsNotice.isHidden()


def test_m140_max_uses_z_from_the_real_wcs_g28_dialog(window):
    window.ui.editor.setText("TOOL CALL Z\nL Z-10 FMAX\nL M140 MB MAX")
    window.ui.fileTypeCombo.setCurrentIndex(2)
    window.wcsDlg.loadValues()
    window.wcsDlg.ui.homeZ.setValue(125)
    window.wcsDlg.ui.homeConfiguredCheck.setChecked(True)
    window.wcsDlg.applyValues()
    assert window.zPosMach == 125
    assert window.execution_result.ok, window.execution_result.diagnostics
    assert window.execution_result.motions[-1].end_z == 125


@pytest.mark.parametrize(
    "page",
    [
        "generalTab",
        "editorTab",
        "plotTab",
        "cncTab",
        "colorsTab",
        "hotkeysTab",
        "rotaryTab",
        "postprocessorsTab",
        "toolDiscoveryTab",
    ],
)
def test_all_options_pages_keep_draft_and_cancel_does_not_save(window, page):
    dialog = window.optionsDlg
    dialog.show()
    saved = {key: window.settings.value(key) for key in window.settings.allKeys()}
    dialog.ui.fontSizeSpin.setValue(window.sizeTxt + 1)
    dialog.ui.tabs.setCurrentWidget(getattr(dialog.ui, page))
    QApplication.processEvents()
    assert dialog.ui.tabs.currentWidget().objectName() == page
    assert dialog.ui.fontSizeSpin.value() == window.sizeTxt + 1
    dialog.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert {key: window.settings.value(key) for key in window.settings.allKeys()} == saved
    dialog.show()
    assert dialog.ui.fontSizeSpin.value() == window.sizeTxt


def test_options_ok_reopen_and_restart_load_saved_values(window):
    dialog = window.optionsDlg
    dialog.show()
    dialog.ui.fontSizeSpin.setValue(17)
    dialog.ui.latheGcodeSystemCombo.setCurrentIndex(1)
    dialog.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).click()
    assert window.sizeTxt == 17
    assert window.latheGcodeSystem == "B"
    dialog.show()
    assert dialog.ui.fontSizeSpin.value() == 17
    dialog.reject()
    restored = MainWindow()
    try:
        assert restored.sizeTxt == 17
        assert restored.latheGcodeSystem == "B"
        restored.optionsDlg.show()
        restored.optionsDlg.ui.buttonBox.button(QDialogButtonBox.StandardButton.RestoreDefaults).click()
        assert restored.optionsDlg.ui.latheGcodeSystemCombo.currentIndex() == 0
        restored.optionsDlg.reject()
        assert restored.latheGcodeSystem == "B"
    finally:
        restored.autoUpdateTimer.stop()
        restored.timer.stop()
        restored.deleteLater()
        QApplication.processEvents()


def test_options_dependent_rapid_control_preserves_draft(window):
    dialog = window.optionsDlg
    dialog.show()
    dialog.ui.dashedRapidCheck.setChecked(True)
    dialog.ui.showRapidCheck.click()
    assert not dialog.ui.dashedRapidCheck.isEnabled()
    assert dialog.ui.dashedRapidCheck.isChecked()
    dialog.ui.showRapidCheck.click()
    assert dialog.ui.dashedRapidCheck.isEnabled()


def test_document_camera_survives_round_trip(window):
    view = window.ui.graphicsView
    view.opts["center"] = QVector3D(12, 34, 56)
    view.setCameraPosition(distance=73, elevation=21, azimuth=42)
    view.setOrthographicProjection(123, 0.01, 1000)
    window.newFile()
    view.opts["center"] = QVector3D(-1, -2, -3)
    view.setCameraPosition(distance=24, elevation=65, azimuth=18)
    view.setOrthographicProjection(456, 0.01, 1000)
    assert window._activate_document(0)
    assert view.opts["center"] == QVector3D(12, 34, 56)
    assert view.opts["distance"] == pytest.approx(73)
    assert view.orthographicWidth() == pytest.approx(123)
    assert view.opts["azimuth"] == pytest.approx(42)
    assert window._activate_document(1)
    assert view.opts["center"] == QVector3D(-1, -2, -3)
    assert view.opts["distance"] == pytest.approx(24)
    assert view.orthographicWidth() == pytest.approx(456)


@pytest.mark.parametrize("attribute", ["tools", "millingTools", "program_tool_inference", "exportToolNumbers"])
def test_program_containers_do_not_alias_saved_document(window, attribute):
    setattr(window, attribute, {"item": {"value": 1}})
    window._capture_active_document()
    getattr(window, attribute)["item"]["value"] = 2
    assert window._documents[0].state[attribute]["item"]["value"] == 1
    window.newFile()
    assert window._activate_document(0)
    getattr(window, attribute)["item"]["value"] = 3
    assert window._documents[0].state[attribute]["item"]["value"] == 2


def test_late_completion_cannot_publish_into_identical_other_document(window):
    window.ui.editor.setText("G0 X1")
    completion = _PlotCompletion(window)
    window.newFile()
    window.ui.editor.setText("G0 X1")
    completion.calculation((None, [], {"T99": {}}, {}, 0, False), lambda: False)
    assert completion.cancelled
    assert "T99" not in window.millingTools
    assert window.execution_result is None


def test_clear_plot_clears_visual_playback_and_unit_metadata(window):
    window._motion_unit_scales = [25.4]
    window._playback_visual_samples = (object(),)
    window._playback_visual_sample_index = 1
    window.clearPlot()
    assert window._motion_unit_scales == []
    assert window._playback_visual_samples == ()
    assert window._playback_visual_sample_index == 0


@pytest.mark.parametrize("lathe,physical_x", [(False, 40), (True, 20)])
def test_playback_start_cursor_uses_plot_coordinates_while_readout_keeps_programmed_x(
    window, monkeypatch, lathe, physical_x
):
    motion = TraceMotion(move=1, start_x=40, start_y=0, start_z=5, end_x=30, end_z=-10)
    window.execution_result = SimpleNamespace(motions=[motion])
    window.latheMode = lathe
    window._stock_animation_active = False
    window._motion_unit_scales = [1.0]
    window._toolpath_item = object()
    captured = []
    monkeypatch.setattr(window, "_cursor_item", SimpleNamespace(setData=lambda **kwargs: captured.append(kwargs)))
    monkeypatch.setattr(window, "_highlight_playback_motion", lambda _index: None)
    window.valueHandler(0, sync_editor=False)
    assert captured[0]["pos"] == [(physical_x, 0, 5)]
    assert window.ui.lineEditX.text() == "40.0"


@pytest.mark.parametrize("sampled", [False, True])
def test_hide_tool_controls_plot_endpoints_and_intermediate_samples(window, monkeypatch, sampled):
    motion = TraceMotion(move=1, start_x=0, start_z=0, end_x=20, end_z=-2, tool="T1")
    window.execution_result = SimpleNamespace(motions=[motion])
    window._playback_movements = [SimpleNamespace(motion_end=1)]
    window._motion_unit_scales = [1.0]
    window._motion_render_end = [1]
    window.render_points = [SimpleNamespace(x=20, y=0, z=-2)]
    window._stock_animation_active = False
    window._toolpath_item = object()
    window.millingTools = {"T1": {"type": "mill_flat", "diameter": 6, "length": 30}}
    calls = []
    monkeypatch.setattr(window, "_cursor_item", SimpleNamespace(setData=lambda **_kwargs: None))
    monkeypatch.setattr(window, "_highlight_playback_motion", lambda _index: None)
    monkeypatch.setattr(
        window,
        "_milling_tool_item",
        SimpleNamespace(
            show_tool=lambda *args: calls.append(("show", args)),
            hide_tool=lambda: calls.append(("hide", ())),
        ),
        raising=False,
    )
    for hidden in (True, False):
        window.plotHideTool = hidden
        if sampled:
            window._show_playback_visual_sample(0, SimpleNamespace(x=10, y=0, z=-1))
        else:
            window.valueHandler(1, sync_editor=False)
        assert calls[-1][0] == ("hide" if hidden else "show")
    expected_position = (10, 0, -1) if sampled else (20, 0, -2)
    assert calls[-1][1] == (window.millingTools["T1"], expected_position, None)


def test_hide_tool_does_not_hide_stock_removal_simulation_tool(window, monkeypatch):
    motion = TraceMotion(move=1, start_x=4, start_z=5, end_x=20, end_z=-2, tool="T1")
    window.execution_result = SimpleNamespace(motions=[motion])
    window._playback_movements = [SimpleNamespace(motion_end=1)]
    window._stock_timeline = SimpleNamespace(motion_count=0)
    window._stock_animation_active = True
    window._stock_tail_item = object()
    window.plotHideTool = True
    window.millingTools = {"T1": {"type": "mill_flat", "diameter": 6, "length": 30}}
    shown, hidden = [], []
    monkeypatch.setattr(
        window,
        "_milling_tool_item",
        SimpleNamespace(
            show_tool=lambda *args: shown.append(args),
            hide_tool=lambda: hidden.append(True),
        ),
        raising=False,
    )
    window._show_milling_stock_position()
    assert shown == [(window.millingTools["T1"], (4, 0, 5))]
    assert not hidden


def test_options_semantic_change_discards_deferred_execution(window):
    window.ui.editor.setText("G90\nG0 X1\nG1 X2 F100\nM30")
    assert window.updateData(show_errors=False)
    previous = window.execution_result
    window.execution_result = None
    window._deferred_execution_result = previous
    window._deferred_execution_source = window.ui.editor.text()
    dialog = window.optionsDlg
    dialog.show()
    dialog.ui.unitsCombo.setCurrentIndex(1)
    dialog.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).click()
    assert window.execution_result is not previous
    assert window.execution_result.motions[-1].end_x == pytest.approx(50.8)
    assert window._deferred_execution_result is None


def test_visual_options_keep_execution_and_inactive_document_current(window):
    window.ui.editor.setText("G0 X1\nG1 X2 F100\nM30")
    assert window.updateData(show_errors=False)
    first = window.execution_result
    window.newFile()
    window.ui.editor.setText("G0 Y3\nG1 Y4 F100\nM30")
    assert window.updateData(show_errors=False)
    second = window.execution_result
    dialog = window.optionsDlg
    dialog.show()
    dialog.ui.lineWidthSpin.setValue(3)
    dialog.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).click()
    assert window.execution_result is second
    assert window._activate_document(0)
    assert window.execution_result is first
    assert not window._plot_source_stale
    assert window.plotLineWidth == 3


@pytest.mark.parametrize("blocked", [False, True])
def test_playback_configuration_preserves_signal_blocking(window, blocked):
    slider = window.ui.horizontalSlider
    window._playback_movements = [None] * 10
    window._fit_view_after_program_load = False
    slider.blockSignals(blocked)
    changed = QSignalSpy(slider.valueChanged)
    try:
        assert window._configure_playback_controls(SimpleNamespace(motions=[None]), 5) == 5
        assert slider.value() == 5
        assert slider.signalsBlocked() == blocked
        assert len(changed) == 0
    finally:
        slider.blockSignals(False)


@pytest.mark.parametrize("blocked", [False, True])
def test_post_profile_reload_restores_signal_blocking_on_error(window, monkeypatch, blocked):
    dialog = window.exportDlg
    combo = dialog.targetCncCombo
    combo.blockSignals(blocked)

    def fail_load(_target):
        raise OSError("Cannot read profile")

    monkeypatch.setattr(dialog.postLibrary, "load", fail_load)
    try:
        with pytest.raises(OSError, match="Cannot read profile"):
            dialog.reload_post_profiles()
        assert combo.signalsBlocked() == blocked
    finally:
        combo.blockSignals(False)


def test_temporary_editor_menus_are_deleted_without_deleting_shared_actions(window, monkeypatch):
    existing = window.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly)
    monkeypatch.setattr(QMenu, "exec", lambda _menu, _position: None)
    for _ in range(3):
        window.editorContextMenu(QPoint())
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly) == existing
    assert window.ui.actionUndo in window.ui.menu_Edit.actions()
    window.ui.actionUndo.trigger()


@pytest.mark.parametrize("kind", ["milling", "turning"])
@pytest.mark.parametrize("result", [QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected])
def test_temporary_tool_editor_is_deleted_after_accept_or_cancel(window, monkeypatch, kind, result):
    dialog = window.toolLibraryDlg
    editors, destroyed, saved = [], [], []

    def finish(editor):
        editors.append(editor)
        destroyed.append(QSignalSpy(editor.destroyed))
        return result

    monkeypatch.setattr(dialog._editor_type(kind), "exec", finish)
    monkeypatch.setattr(dialog, "_persist_library_change", lambda *args: saved.append(args))
    dialog.add_library_tool(kind)
    assert len(editors) == 1
    assert bool(saved) == (result == QDialog.DialogCode.Accepted)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(destroyed[0]) == 1
