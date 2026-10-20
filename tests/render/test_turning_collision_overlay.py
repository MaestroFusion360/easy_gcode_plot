"""Turning collision mesh follows stock history without requiring a GL context."""

# pylint: disable=protected-access

import numpy as np
import pytest
from OpenGL import GL
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from app.gcode.kernel import TraceMotion
from app.gcode.stock import TurningStockSpec, TurningStockTimeline
from app.main_window import MainWindow
from app.ui.plot.stock_overlay import COLLISION_COLOR, STOCK_COLOR, TOOL_COLOR, TurningStockOverlayItem


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_overlay_draws_only_intersection_in_red_and_restores_it_on_seek(qt_app):
    tool = {"type": "groove", "width": 1, "insertLength": 2, "tipOrientation": 3}
    motions = (
        TraceMotion(0, 8, 3, 8, -13, tool="T0101", x_scale=0.5),
        TraceMotion(0, 40, -13, 40, 3, tool="T0101", x_scale=0.5),
        TraceMotion(1, 8, 3, 8, -13, tool="T0101", x_scale=0.5),
    )
    timeline = TurningStockTimeline(motions, TurningStockSpec(20, 10, resolution=0.5), {"T0101": tool})
    overlay = TurningStockOverlayItem()
    overlay.set_frame(timeline, (4, 3), tool)
    assert not overlay._collision_mesh.visible()
    timeline.set_motion_count(1)
    overlay.set_frame(timeline, (4, -13), tool)
    damage = overlay._collision_mesh.opts["meshdata"].vertexes().copy()
    assert len(damage) > 0 and overlay._collision_mesh.visible()
    assert set(np.unique(damage[:, 0])) == {-6, -4, 4, 6}
    assert damage[:, 2].min() == pytest.approx(-10, abs=1e-6)
    assert damage[:, 2].max() == pytest.approx(0, abs=1e-6)
    assert np.all(damage[:, 1] == 0)
    assert overlay._collision_mesh._GLGraphicsItem__glOpts[GL.GL_DEPTH_TEST] is False
    assert overlay._collision_mesh.opts["color"] == QColor(COLLISION_COLOR)
    assert overlay._collision_mesh.opts["shader"] is None
    assert overlay._stock_mesh.opts["color"] == QColor(STOCK_COLOR)
    assert overlay._tool_mesh.opts["color"] == QColor(TOOL_COLOR)
    timeline.set_motion_count(2)
    overlay.set_frame(timeline, (20, 3), tool)
    np.testing.assert_array_equal(overlay._collision_mesh.opts["meshdata"].vertexes(), damage)
    timeline.set_motion_count(3)
    overlay.set_frame(timeline, (4, -13), tool)
    assert not overlay._collision_mesh.visible()
    timeline.set_motion_count(1)
    overlay.set_frame(timeline, (4, -13), tool)
    np.testing.assert_array_equal(overlay._collision_mesh.opts["meshdata"].vertexes(), damage)
    timeline.set_motion_count(0)
    overlay.set_frame(timeline, (4, 3), tool)
    assert not overlay._collision_mesh.visible()
    qt_app.processEvents()


def test_overlay_replaces_history_when_new_timeline_has_same_revision(qt_app):
    tool = {"type": "groove", "width": 1, "insertLength": 2, "tipOrientation": 3}
    stock_spec = TurningStockSpec(20, 10, resolution=0.5)
    first = TurningStockTimeline((TraceMotion(0, 8, 3, 8, -13, tool="T0101"),), stock_spec, {"T0101": tool})
    second = TurningStockTimeline((TraceMotion(1, 8, 3, 8, -13, tool="T0101"),), stock_spec, {"T0101": tool})
    first.set_motion_count(1)
    second.set_motion_count(1)
    assert first.revision == second.revision
    overlay = TurningStockOverlayItem()
    overlay.set_frame(first, (4, -13), tool)
    assert overlay._collision_mesh.visible()
    overlay.set_frame(second, (4, -13), tool)
    assert not overlay._collision_mesh.visible()
    overlay.clear()
    assert not overlay.visible()
    qt_app.processEvents()


def test_trackbar_updates_real_turning_stock_collision_history(qt_app, monkeypatch):
    window = MainWindow()
    try:
        window.ui.actionLatheMode.setChecked(True)
        window.ui.editor.setText("G21 G18 G90\nT0101\nG0 X8 Z3\nG0 Z-13\nG0 X40\nG0 Z3\nG1 X8 F100\nG1 Z-13\nM30")
        assert window.updateData()
        window.timer.stop()
        window.tools["T0101"] = {"type": "groove", "width": 1, "insertLength": 2, "tipOrientation": 3}
        window.stockEnabled = window.stockConfigured = True
        window._stock_manual_override = window._stock_outline_use_configured = True
        window.turnStockDiameter, window.turnStockLength, window.turnStockResolution = 20, 10, 0.5
        window.turnStockInnerDiameter = window.turnStockFrontZ = 0
        monkeypatch.setattr(window, "fitToView", lambda: None)
        window.ui.actionStockPlayback.setChecked(True)
        assert window._stock_animation_active
        collision_motion = next(
            i for i, m in enumerate(window.execution_result.motions) if m.move == 0 and m.end_z == -13 and m.end_x == 8
        )
        marked_frame = next(
            i + 1
            for i, movement in enumerate(window._playback_movements)
            if movement.motion_end == collision_motion + 1
        )
        slider = window.ui.horizontalSlider
        slider.setValue(marked_frame)
        assert window._stock_item._collision_mesh.visible()
        damage = window._stock_item._collision_mesh.opts["meshdata"].vertexes().copy()
        slider.setValue(slider.maximum())
        assert not window._stock_item._collision_mesh.visible()
        slider.setValue(marked_frame)
        np.testing.assert_array_equal(window._stock_item._collision_mesh.opts["meshdata"].vertexes(), damage)
        slider.setValue(0)
        assert not window._stock_item._collision_mesh.visible()
    finally:
        window.timer.stop()
        window.ui.editor.setModified(False)
        window.close()
        window.deleteLater()
        qt_app.processEvents()
