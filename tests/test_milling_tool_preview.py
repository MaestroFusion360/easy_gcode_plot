from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.milling_tool_preview import TOOL_ALPHA, MillingToolPreviewItem


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_flat_mill_geometry_is_reused_when_only_playback_position_changes(qt_app):
    item = MillingToolPreviewItem("#336699")
    spec = {"type": "mill_flat", "diameter": 10.0, "length": 40.0}

    assert item.show_tool(spec, (1.0, 2.0, 3.0))
    meshes = item.meshes
    assert item.geometry_key == ("mill_flat", 10.0, 40.0, 0.0)
    assert len(meshes) == 1
    assert meshes[0].opts["color"].alphaF() == pytest.approx(TOOL_ALPHA, abs=0.01)

    assert item.show_tool(spec, (10.0, 20.0, 30.0))
    assert item.meshes == meshes
    translation = item.transform().column(3)
    assert (translation.x(), translation.y(), translation.z()) == pytest.approx((10.0, 20.0, 30.0))


def test_drill_has_conical_point_and_cylindrical_body(qt_app):
    item = MillingToolPreviewItem()

    assert item.show_tool({"type": "drill", "diameter": 12.0, "length": 50.0}, (0.0, 0.0, 0.0))
    assert item.geometry_key == ("drill", 12.0, 50.0, 0.0)
    assert len(item.meshes) == 1


def test_drill_geometry_change_updates_existing_scene_mesh(qt_app):
    item = MillingToolPreviewItem()
    assert item.show_tool({"type": "drill", "diameter": 3.0, "length": 30.0}, (1.0, 2.0, 3.0))
    mesh = item.meshes[0]
    first_radius = abs(mesh.opts["meshdata"].vertexes()[:, 0]).max()

    assert item.show_tool({"type": "drill", "diameter": 10.0, "length": 30.0}, (1.0, 2.0, 3.0))

    assert item.visible()
    assert item.meshes == (mesh,)
    assert item.geometry_key == ("drill", 10.0, 30.0, 0.0)
    assert abs(mesh.opts["meshdata"].vertexes()[:, 0]).max() > first_radius


@pytest.mark.parametrize(
    ("spec", "expected_key"),
    [
        (
            {"type": "mill_bull", "diameter": 12.0, "cornerRadius": 2.0, "length": 50.0},
            ("mill_bull", 12.0, 50.0, 2.0),
        ),
        (
            {"type": "mill_ball", "diameter": 12.0, "cornerRadius": 0.0, "length": 50.0},
            ("mill_ball", 12.0, 50.0, 6.0),
        ),
    ],
)
def test_round_mills_use_configured_cutting_profiles(qt_app, spec, expected_key):
    item = MillingToolPreviewItem()

    assert item.show_tool(spec, (0.0, 0.0, 0.0))
    assert item.geometry_key == expected_key
    assert len(item.meshes) == 1
    vertices = item.meshes[0].opts["meshdata"].vertexes()
    assert vertices[:, 2].min() == pytest.approx(0.0)
    assert vertices[:, 2].max() == pytest.approx(50.0)


def test_main_window_preview_tracks_logical_motion_and_is_hidden_for_turning(qt_app):
    window = MainWindow()
    window.latheMode = False
    window.millingTools = {"T1": {"type": "mill_flat", "diameter": 8.0, "cornerRadius": 0.0, "length": 30.0}}
    window.ui.editor.setText("G21 G90\nT1 M6\nG0 X1 Y2 Z3\nG1 X4 Y5 Z6 F100\nM30")

    assert window.updateData()
    tool_item = window._milling_tool_item  # pylint: disable=protected-access
    assert tool_item.visible()
    assert tool_item.geometry_key == ("mill_flat", 8.0, 30.0, 0.0)
    translation = tool_item.transform().column(3)
    assert (translation.x(), translation.y(), translation.z()) == pytest.approx((4.0, 5.0, 6.0))

    meshes = tool_item.meshes
    window.ui.horizontalSlider.setValue(1)
    assert tool_item.meshes == meshes
    translation = tool_item.transform().column(3)
    assert (translation.x(), translation.y(), translation.z()) == pytest.approx((1.0, 2.0, 3.0))

    window.latheMode = True
    window.valueHandler(1, sync_editor=False)
    assert not tool_item.visible()
    window.deleteLater()


def test_milling_tool_dialog_refreshes_visible_drill_geometry_in_place(qt_app):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(False)
    window.millingTools = {"T1": {"type": "drill", "diameter": 3.0, "cornerRadius": 0.0, "length": 30.0}}
    window.ui.editor.setText("G21 G90\nT1 M6\nG0 X1 Y2 Z3\nM30")
    assert window.updateData()
    tool_item = window._milling_tool_item  # pylint: disable=protected-access
    mesh = tool_item.meshes[0]

    window.millingToolsDlg.pendingTools = {
        "T1": {"type": "drill", "diameter": 10.0, "cornerRadius": 0.0, "length": 30.0}
    }
    window.millingToolsDlg.applyValues()

    assert tool_item.visible()
    assert tool_item.meshes == (mesh,)
    assert tool_item.geometry_key == ("drill", 10.0, 30.0, 0.0)
    window.deleteLater()
