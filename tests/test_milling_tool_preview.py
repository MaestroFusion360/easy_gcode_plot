from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.settings import normalized_milling_tools, normalized_tools
from app.tools.definitions import DEFAULT_MILLING_TOOL, DEFAULT_TURNING_TOOL
from app.tools.milling_geometry import milling_tool_profile
from app.ui.milling_tool_preview import TOOL_ALPHA, MillingToolPreviewItem
from app.ui.tool_library_preview import ToolLibraryPreview


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
    assert item.geometry_key == ("drill", 12.0, 50.0, 0.0, 118.0)
    assert len(item.meshes) == 1


def test_drill_geometry_change_updates_existing_scene_mesh(qt_app):
    item = MillingToolPreviewItem()
    assert item.show_tool({"type": "drill", "diameter": 3.0, "length": 30.0}, (1.0, 2.0, 3.0))
    mesh = item.meshes[0]
    first_radius = abs(mesh.opts["meshdata"].vertexes()[:, 0]).max()

    assert item.show_tool({"type": "drill", "diameter": 10.0, "length": 30.0}, (1.0, 2.0, 3.0))

    assert item.visible()
    assert item.meshes == (mesh,)
    assert item.geometry_key == ("drill", 10.0, 30.0, 0.0, 118.0)
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


def test_turning_drill_library_preview_uses_shared_turning_geometry(qt_app, monkeypatch):
    preview = ToolLibraryPreview("turning")
    preview.set_tool({"type": "drill", "diameter": 10.0, "length": 50.0, "tipAngle": 140.0})
    captured = {}

    def fake_geometry(spec, stock_diameter):
        captured["spec"] = dict(spec)
        captured["stock_diameter"] = stock_diameter
        return ((0.0, 0.0), (-5.0, 2.0), (-5.0, 50.0), (5.0, 50.0), (5.0, 2.0)), 1.0, ("drill",)

    class Painter:
        def drawPath(self, _path):
            captured["drawn"] = True

    monkeypatch.setattr("app.ui.tool_library_preview.display_tool_geometry", fake_geometry)
    monkeypatch.setattr(preview, "_paint_trace_point", lambda *_args: None)

    preview._paint_turning(Painter())  # pylint: disable=protected-access

    assert captured["spec"]["tipAngle"] == pytest.approx(140.0)
    assert captured["stock_diameter"] == pytest.approx(50.0)
    assert captured["drawn"] is True


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
    assert tool_item.geometry_key == ("drill", 10.0, 30.0, 0.0, 118.0)
    window.deleteLater()


@pytest.mark.parametrize("tool_type", ["face_mill", "slot_mill", "chamfer_mill", "tap"])
def test_new_milling_types_have_3d_geometry(qt_app, tool_type):
    item = MillingToolPreviewItem()
    spec = {"type": tool_type, "diameter": 10.0, "length": 40.0, "cornerRadius": 0.0}

    assert item.show_tool(spec, (0.0, 0.0, 0.0))
    assert item.geometry_key[0] == tool_type
    assert item.meshes


def test_empty_tool_dialogs_clear_preview_and_duplicate_to_first_free_code(qt_app):
    window = MainWindow()
    window.tools = {}
    window.millingTools = {}
    window.turningToolsDlg.loadValues()
    window.millingToolsDlg.loadValues()

    assert window.turningToolsDlg.preview.spec == {}
    assert window.millingToolsDlg.preview.spec == {}

    window.turningToolsDlg.pendingTools = {"T0001": dict(DEFAULT_TURNING_TOOL)}
    window.turningToolsDlg.refreshTable("T0001")
    window.turningToolsDlg.duplicateTool()
    assert window.turningToolsDlg.pendingTools["T0002"] == DEFAULT_TURNING_TOOL

    window.millingToolsDlg.pendingTools = {"T1": dict(DEFAULT_MILLING_TOOL)}
    window.millingToolsDlg.refreshTable("T1")
    window.millingToolsDlg.duplicateTool()
    assert window.millingToolsDlg.pendingTools["T2"] == DEFAULT_MILLING_TOOL
    window.deleteLater()


def test_tool_preview_zoom_changes_scrollable_canvas_size(qt_app):
    window = MainWindow()
    preview = window.turningToolsDlg.preview
    original_size = preview.size()

    preview.set_zoom(2.0)

    assert preview.zoom == 2.0
    assert preview.width() == original_size.width() * 2
    assert preview.height() == original_size.height() * 2
    window.deleteLater()


def test_new_tool_types_are_normalized():
    turning = normalized_tools(
        {
            "T1": {"type": "square", "noseRadius": 0.4, "tipOrientation": 3},
            "T2": {"type": "round", "noseRadius": 3.0, "tipOrientation": 3},
            "T3": {"type": "triangle", "noseRadius": 0.4, "tipOrientation": 3},
            "T4": {"type": "tap", "diameter": 6.0, "length": 40.0, "tipAngle": 60.0},
        }
    )
    assert {spec["type"] for spec in turning.values()} == {
        "square",
        "round",
        "triangle",
        "tap",
    }
    milling = normalized_milling_tools(
        {
            f"T{index}": {"type": tool_type, "diameter": 10.0, "length": 40.0}
            for index, tool_type in enumerate(("face_mill", "slot_mill", "chamfer_mill", "tap"), 1)
        }
    )
    assert {spec["type"] for spec in milling.values()} == {"face_mill", "slot_mill", "chamfer_mill", "tap"}


def test_milling_drill_tip_angle_changes_point_length():
    sharp = milling_tool_profile({"type": "drill", "diameter": 10.0, "length": 50.0, "tipAngle": 90.0})
    blunt = milling_tool_profile({"type": "drill", "diameter": 10.0, "length": 50.0, "tipAngle": 140.0})

    assert sharp[1][0] == pytest.approx(5.0)
    assert blunt[1][0] < sharp[1][0]


def test_milling_drill_tip_angle_is_normalized():
    tools = normalized_milling_tools({"T1": {"type": "drill", "diameter": 10.0, "length": 50.0, "tipAngle": 135.0}})

    assert tools["T1"]["tipAngle"] == pytest.approx(135.0)


def test_face_mill_profile_has_chamfer_head_and_smaller_shank():
    spec = {
        "type": "face_mill",
        "diameter": 50.0,
        "length": 80.0,
        "cuttingHeight": 12.0,
        "shankDiameter": 20.0,
    }
    profile = milling_tool_profile(spec)

    assert profile[0][0] == pytest.approx(0.0)
    assert profile[0][1] < 25.0
    assert profile[1][1] == pytest.approx(25.0)
    assert profile[2] == pytest.approx((12.0, 25.0))
    assert profile[3] == pytest.approx((12.0, 10.0))
    assert profile[-1] == pytest.approx((80.0, 10.0))


def test_slot_mill_profile_is_large_cylinder_then_smaller_shank():
    profile = milling_tool_profile(
        {
            "type": "slot_mill",
            "diameter": 32.0,
            "length": 70.0,
            "cuttingHeight": 8.0,
            "shankDiameter": 16.0,
        }
    )

    expected = ((0.0, 16.0), (8.0, 16.0), (8.0, 8.0), (70.0, 8.0))
    assert len(profile) == len(expected)
    for actual_point, expected_point in zip(profile, expected, strict=True):
        assert actual_point == pytest.approx(expected_point)


def test_chamfer_mill_profile_has_flat_tip_frustum_and_cylindrical_body():
    profile = milling_tool_profile(
        {
            "type": "chamfer_mill",
            "diameter": 20.0,
            "length": 60.0,
            "tipDiameter": 4.0,
            "chamferAngle": 90.0,
        }
    )

    assert profile[0] == pytest.approx((0.0, 2.0))
    assert profile[1] == pytest.approx((8.0, 10.0))
    assert profile[-1] == pytest.approx((60.0, 10.0))


def test_new_milling_shape_fields_are_normalized_and_old_records_get_defaults():
    tools = normalized_milling_tools(
        {
            "T1": {
                "type": "face_mill",
                "diameter": 50.0,
                "length": 80.0,
                "cuttingHeight": 12.0,
                "shankDiameter": 20.0,
            },
            "T2": {
                "type": "slot_mill",
                "diameter": 32.0,
                "length": 70.0,
                "cuttingHeight": 8.0,
                "shankDiameter": 16.0,
            },
            "T3": {
                "type": "chamfer_mill",
                "diameter": 20.0,
                "length": 60.0,
                "tipDiameter": 4.0,
                "chamferAngle": 90.0,
            },
            "T4": {"type": "face_mill", "diameter": 40.0, "length": 60.0},
        }
    )

    assert tools["T1"]["cuttingHeight"] == pytest.approx(12.0)
    assert tools["T1"]["shankDiameter"] == pytest.approx(20.0)
    assert tools["T2"]["cuttingHeight"] == pytest.approx(8.0)
    assert tools["T2"]["shankDiameter"] == pytest.approx(16.0)
    assert tools["T3"]["tipDiameter"] == pytest.approx(4.0)
    assert tools["T3"]["chamferAngle"] == pytest.approx(90.0)
    assert 0.0 < tools["T4"]["cuttingHeight"] <= 60.0
    assert 0.0 < tools["T4"]["shankDiameter"] < 40.0
