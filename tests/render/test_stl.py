# pylint: disable=protected-access
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from OpenGL import GL
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPalette, QVector3D, QVector4D
from PyQt6.QtWidgets import QApplication, QCheckBox, QDialog, QPlainTextEdit

from app.main_window import MainWindow
from app.ui.plot.stl import read_stl, stl_face_colors, stl_feature_edges
from app.ui.plot.stl_transform import measure_mesh
from app.ui.plot.toolpath_vbo import ToolpathVboItem

STL_FIXTURE = Path(__file__).resolve().parents[2] / "assets" / "stl" / "test.stl"
STL_CAMERA_FIXTURE = Path(__file__).resolve().parents[2] / "assets" / "stl" / "test2.stl"
STL_SECTION_FIXTURE = Path(__file__).resolve().parents[2] / "assets" / "stl" / "test4.stl"


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_read_project_stl_fixture_with_geometry_bounds_and_feature_edges():
    mesh = read_stl(STL_FIXTURE)

    assert mesh.triangle_count == 1352
    assert np.asarray(mesh.bounds) == pytest.approx(np.asarray(((-91.0, 91.0), (-50.0, 66.0), (0.0, 22.0))))
    assert mesh.triangles.shape == (1352, 3, 3)
    assert mesh.triangles.dtype == np.float32
    assert mesh.normals.dtype == np.float32
    assert np.isfinite(mesh.normals).all()
    colors = stl_face_colors(mesh)
    assert colors.shape == (1352, 4)
    assert colors.dtype == np.float32
    assert np.all(colors[:, 3] == 1.0)
    assert colors[:, 0].max() > colors[:, 0].min()

    blue_colors = stl_face_colors(mesh, base_color=(0.1, 0.2, 0.8))
    assert blue_colors[:, 2].max() > blue_colors[:, 1].max() > blue_colors[:, 0].max()
    inverted_mesh = type(mesh)(mesh.triangles, -mesh.normals, mesh.bounds)
    assert stl_face_colors(inverted_mesh) == pytest.approx(colors)
    edges = stl_feature_edges(mesh)
    assert edges.shape == (957, 2)
    assert edges.dtype == np.uint32


@pytest.mark.parametrize(
    "content, message",
    [
        (b"solid empty\nendsolid\n", "no triangles"),
        (b"solid bad\nvertex 0 0 0\n", "Incomplete triangle"),
        (b"solid bad\nvertex nan 0 0\nvertex 0 1 0\nvertex 0 0 1\n", "non-finite"),
    ],
)
def test_read_stl_rejects_invalid_mesh(tmp_path, content, message):
    path = tmp_path / "bad.stl"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=message):
        read_stl(path)


def test_main_window_imports_persists_and_clears_stl_overlay(qt_app):
    window = MainWindow()

    assert window.ui.actionImportSTL in window.ui.menu_File.actions()
    assert window.ui.actionImportSTL in window.ui.fileToolBar.actions()
    assert not window.ui.actionClearSTL.isEnabled()
    assert window.importStl(str(STL_FIXTURE)) is True
    overlay = window._stl_entries[0].overlay
    item = overlay.item
    assert overlay.mesh.triangle_count == 1352
    assert item in window.ui.graphicsView.items
    assert window.ui.actionClearSTL.isEnabled()
    assert item.opts["drawFaces"] is True
    assert item.opts["drawEdges"] is False

    window.loadPlot()
    assert item in window.ui.graphicsView.items

    window.stlColor = "#2470c4"
    window.stlWireframe = True
    assert window.refreshStlAppearance() is True
    wireframe_item = overlay.item
    assert wireframe_item is not item
    assert wireframe_item in window.ui.graphicsView.items
    assert item not in window.ui.graphicsView.items
    assert wireframe_item.mode == "lines"
    assert wireframe_item.pos.shape == (957 * 2, 3)
    assert window.refreshStlAppearance() is False
    assert overlay.item is wireframe_item

    window.clearStl()
    assert not window._stl_entries
    assert wireframe_item not in window.ui.graphicsView.items
    assert not window.ui.actionClearSTL.isEnabled()
    window.deleteLater()


def test_recent_stl_menu_tracks_imports_reopens_models_and_clears(qt_app):
    window = MainWindow()
    try:
        window._clear_recent_stl()
        actions = window.ui.menu_File.actions()
        clear_index = actions.index(window.ui.actionClearSTL)
        assert actions[clear_index + 1] is window.recentStlMenu.menuAction()

        assert window.importStl(str(STL_FIXTURE))
        recent_path = str(STL_FIXTURE.resolve()).replace("\\", "/")
        assert window.recentStlFiles[0] == recent_path
        assert window.settings.value("FILE/RECENT_STL_FILES") == [recent_path]

        window.recentStlMenu.actions()[0].trigger()
        assert len(window._stl_entries) == 2

        window._clear_recent_stl()
        assert window.recentStlFiles == []
        assert window.settings.value("FILE/RECENT_STL_FILES") == []
    finally:
        window._clear_recent_stl()
        window.deleteLater()


def test_new_command_clears_stl_only_after_document_close_is_accepted(qt_app, monkeypatch):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE)) is True
        item = window._stl_entries[0].overlay.item
        assert item in window.ui.graphicsView.items

        monkeypatch.setattr(window, "maybeSave", lambda: False)
        window.ui.actionNew.trigger()
        assert window._stl_entries[0].overlay.item is item
        assert item in window.ui.graphicsView.items

        monkeypatch.setattr(window, "maybeSave", lambda: True)
        window.ui.actionNew.trigger()
        assert not window._stl_entries
        assert item not in window.ui.graphicsView.items
        assert not window.ui.actionClearSTL.isEnabled()
    finally:
        window.deleteLater()


def test_grid_is_drawn_after_background_but_keeps_scene_depth(qt_app):
    window = MainWindow()
    window.ui.actionGrid.setChecked(True)
    assert window.importStl(str(STL_FIXTURE)) is True

    grid = window._milling_grid_item
    axis = window._axis_triad_item
    assert grid.depthValue() < axis.depthValue()
    assert grid in window.ui.graphicsView.items
    assert window.ui.graphicsView.items.index(grid) < window.ui.graphicsView.items.index(axis)
    assert window.ui.graphicsView.items.index(grid) < window.ui.graphicsView.items.index(
        window._stl_entries[0].overlay.item
    )
    grid_options = grid.lineplot._GLGraphicsItem__glOpts
    stl_options = window._stl_entries[0].overlay.item._GLGraphicsItem__glOpts
    assert grid_options["glDepthMask"] == (False,)
    assert stl_options["glDepthMask"] == (True,)
    assert grid_options[GL.GL_DEPTH_TEST] is True
    window.deleteLater()


def test_opaque_stl_occludes_toolpath_in_depth_buffer(qt_app):
    window = MainWindow()
    view = window.ui.graphicsView
    toolpath = ToolpathVboItem()
    window._toolpath_item = toolpath
    view.addItem(toolpath)
    try:
        assert window.importStl(str(STL_FIXTURE)) is True
        stl = window._stl_entries[0].overlay.item
        stl_options = stl._GLGraphicsItem__glOpts
        toolpath_options = toolpath._GLGraphicsItem__glOpts

        assert view.format().depthBufferSize() >= 24
        assert view.items.index(stl) < view.items.index(toolpath)
        assert stl_options[GL.GL_DEPTH_TEST] is True
        assert stl_options["glDepthFunc"] == (GL.GL_LEQUAL,)
        assert stl_options["glDepthMask"] == (True,)
        assert toolpath_options[GL.GL_DEPTH_TEST] is True
        assert toolpath_options["glDepthFunc"] == (GL.GL_LEQUAL,)
        assert toolpath_options["glDepthMask"] == (False,)
    finally:
        window.deleteLater()


def test_stl_item_and_mesh_data_are_reused_across_camera_views(qt_app):
    window = MainWindow()
    assert window.importStl(str(STL_CAMERA_FIXTURE)) is True
    overlay = window._stl_entries[0].overlay
    item = overlay.item
    mesh_data = item.opts["meshdata"]
    view = window.ui.graphicsView

    window.viewTop()
    assert view.isOrthographic()
    assert view.opts["fov"] == pytest.approx(60.0)
    assert view.orthographicWidth() > 0.0
    assert overlay.item is item
    assert overlay.item.opts["meshdata"] is mesh_data

    window.viewFront()
    assert view.isOrthographic()
    assert overlay.item is item
    assert overlay.item.opts["meshdata"] is mesh_data

    window.viewLeft()
    assert view.isOrthographic()
    assert overlay.item is item
    assert overlay.item.opts["meshdata"] is mesh_data

    window.view3d()
    assert view.isOrthographic()
    assert view.projectionMode() == "orthographic"
    assert overlay.item is item
    assert overlay.item.opts["meshdata"] is mesh_data
    assert item in view.items
    window.deleteLater()


def test_orbit_from_fixed_view_keeps_orthographic_3d(qt_app):
    window = MainWindow()
    assert window.importStl(str(STL_CAMERA_FIXTURE)) is True
    item = window._stl_entries[0].overlay.item

    window.viewFront()
    assert window._view_mode == "front"
    assert window.ui.graphicsView.isOrthographic()

    window.ui.graphicsView.orbit(5.0, 3.0)

    assert window._view_mode == "3d"
    assert window.ui.graphicsView.projectionMode() == "orthographic"
    assert window.ui.graphicsView.opts["fov"] == pytest.approx(60.0)
    assert window._stl_entries[0].overlay.item is item
    assert item in window.ui.graphicsView.items
    width_after_first_orbit = window.ui.graphicsView.orthographicWidth()
    window.ui.graphicsView.orbit(4.0, -2.0)
    assert window.ui.graphicsView.orthographicWidth() == pytest.approx(width_after_first_orbit)
    window.deleteLater()


def test_table_b_isometric_view_has_y_up_and_xz_sideways_and_orbits_about_cursor(qt_app):
    window = MainWindow()
    previous = window.rotaryKinematics
    try:
        window._select_rotary_kinematics("4ax_table_b")
        window.view3d()
        view = window.ui.graphicsView
        assert view.opts["rotationMethod"] == "quaternion"
        screen_x = view.viewMatrix() * QVector4D(1, 0, 0, 0)
        screen_y = view.viewMatrix() * QVector4D(0, 1, 0, 0)
        screen_z = view.viewMatrix() * QVector4D(0, 0, 1, 0)
        assert screen_y.x() == pytest.approx(0, abs=1e-6)
        assert screen_y.y() > 0
        assert screen_x.x() > 0
        assert screen_x.y() > 0
        assert screen_z.x() > 0
        assert screen_z.y() < 0
        assert abs(screen_x.x()) > abs(screen_x.y())
        assert abs(screen_z.x()) > abs(screen_z.y())

        navigation = window._plot_navigation
        navigation._orbit_pivot = navigation._pivot_at(QPointF(view.width() * 0.7, view.height() * 0.4))
        before = view.viewMatrix() * QVector4D(navigation._orbit_pivot, 1)
        navigation._orbit_at_pivot(12, -8)
        after = view.viewMatrix() * QVector4D(navigation._orbit_pivot, 1)
        assert QVector3D(before.x() - after.x(), before.y() - after.y(), before.z() - after.z()).length() < 1e-4

        window.viewTop()
        assert view.isOrthographic()
        assert view.opts["rotationMethod"] == "euler"
        window.view3d()
        assert view.opts["rotationMethod"] == "quaternion"

        window._select_rotary_kinematics("4ax_table_a")
        window.view3d()
        assert view.opts["rotationMethod"] == "euler"
    finally:
        window._select_rotary_kinematics(previous)
        window.deleteLater()


def test_normal_file_open_routes_stl_to_importer_without_decoding_as_nc(qt_app, monkeypatch):
    window = MainWindow()
    original_editor_text = window.ui.editor.text()
    monkeypatch.setattr(
        "app.ui.windows.main_window_file_ops.read_nc_text",
        lambda *_args, **_kwargs: pytest.fail("binary STL must not enter the NC text reader"),
    )

    assert window.loadFile(str(STL_FIXTURE)) is True
    assert window._stl_entries[0].overlay.mesh.triangle_count == 1352
    assert window.ui.editor.text() == original_editor_text
    window.deleteLater()


def test_multiple_stl_objects_are_kept_in_scene_and_list(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE)) is True
        first_item = window._stl_entries[0].overlay.item
        assert window.importStl(str(STL_FIXTURE)) is True

        assert len(window._stl_entries) == 2
        assert window.stlObjectsDock.objectList.count() == 2
        assert [entry.obj.name for entry in window._stl_entries] == ["test.stl", "test (2).stl"]
        assert first_item in window.ui.graphicsView.items
        assert window._stl_entries[1].overlay.item in window.ui.graphicsView.items

        window.clearStl()
        assert not window._stl_entries
        assert window.stlObjectsDock.objectList.count() == 0
        assert first_item not in window.ui.graphicsView.items
    finally:
        window.deleteLater()


def test_stl_panel_moves_rotates_scales_and_preserves_source_mesh(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE)) is True
        source_triangles = window._stl_entries[0].obj.mesh.triangles.copy()
        panel = window.stlObjectsDock

        panel.positionX.setValue(10.0)
        panel.positionY.setValue(20.0)
        panel.positionZ.setValue(30.0)
        panel.moveButton.click()
        assert window._stl_entries[0].obj.world_pivot() == pytest.approx((10.0, 20.0, 30.0))

        panel.rotateAxis.setCurrentText("Z")
        panel.rotateAngle.setValue(90.0)
        panel.rotateButton.click()
        assert window._stl_entries[0].obj.world_pivot() == pytest.approx((10.0, 20.0, 30.0))

        panel.scaleFactor.setValue(25.4)
        panel.scaleButton.click()
        assert window._stl_entries[0].obj.world_pivot() == pytest.approx((10.0, 20.0, 30.0))
        assert window._stl_entries[0].obj.mesh.triangles == pytest.approx(source_triangles)
    finally:
        window.deleteLater()


def test_stl_rectangular_array_and_selected_delete(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE)) is True
        source_pivot = window._stl_entries[0].obj.world_pivot().copy()
        window._rectangular_array_selected_stl(2, 2, 1, 10.0, 20.0, 0.0)

        assert len(window._stl_entries) == 4
        pivots = np.asarray([entry.obj.world_pivot() for entry in window._stl_entries])
        expected = np.asarray(
            [
                source_pivot,
                source_pivot + (10.0, 0.0, 0.0),
                source_pivot + (0.0, 20.0, 0.0),
                source_pivot + (10.0, 20.0, 0.0),
            ]
        )
        assert pivots == pytest.approx(expected)
        assert window.stlObjectsDock.objectList.count() == 4

        assert window.removeSelectedStl() is True
        assert len(window._stl_entries) == 3
        assert window.stlObjectsDock.objectList.count() == 3
    finally:
        window.deleteLater()


def test_stl_panel_is_in_settings_and_history_restores_transforms_arrays_and_delete(qt_app):
    window = MainWindow()
    try:
        panel = window.stlObjectsDock
        assert panel.toggleViewAction() in window.ui.menuSettings.actions()
        assert panel.toggleViewAction() not in window.ui.menu_View.actions()
        assert panel.operationStack.count() == panel.operationCombo.count() == 6
        assert window.importStl(str(STL_FIXTURE))
        original = window._stl_entries[0].obj
        assert not panel.undoButton.isEnabled()
        assert not window.undoStl()
        assert window._stl_entries[0].obj is original
        assert "Bounding box" in panel.format_measurements(window._stl_entries[0].measurements)

        panel.positionX.setValue(25)
        panel.moveButton.click()
        moved = window._stl_entries[0].obj
        assert moved.world_pivot()[0] == pytest.approx(25)
        window._rectangular_array_selected_stl(2, 1, 1, 10, 0, 0)
        assert len(window._stl_entries) == 2
        assert window.removeSelectedStl()
        assert len(window._stl_entries) == 1

        panel.undoButton.click()
        assert len(window._stl_entries) == 2
        panel.undoButton.click()
        assert len(window._stl_entries) == 1
        panel.undoButton.click()
        assert window._stl_entries[0].obj is original
        panel.redoButton.click()
        assert np.asarray(window._stl_entries[0].obj.world_pivot()) == pytest.approx(moved.world_pivot())
    finally:
        window.deleteLater()


def test_stl_section_defaults_to_bounds_center_and_can_be_undone(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE))
        panel = window.stlObjectsDock
        bounds = window._stl_entries[0].overlay.bounds
        panel.sectionAxis.setCurrentText("Z")
        assert panel.sectionOffset.value() == pytest.approx(sum(bounds[2]) / 2)
        panel.sectionButton.click()
        assert window._stl_section_item is not None
        assert window._stl_section_item in window.ui.graphicsView.items
        panel.undoButton.click()
        assert window._stl_section_item is None
        panel.redoButton.click()
        assert window._stl_section_item is not None
    finally:
        window.deleteLater()


def test_test4_section_displays_a_clipped_3d_mesh_and_restores_original(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_SECTION_FIXTURE))
        entry = window._stl_entries[0]
        source_item = entry.overlay.item
        source_stats = entry.measurements
        assert source_stats.volume == pytest.approx(8_499_101.869, rel=1e-6)

        panel = window.stlObjectsDock
        panel.sectionAxis.setCurrentText("X")
        panel.sectionOffset.setValue(0.1234)
        panel.sectionKeepSide.setCurrentIndex(panel.sectionKeepSide.findData(True))
        panel.sectionButton.click()

        assert entry.section_overlay is not None
        cut_triangles = entry.section_overlay.object.mesh.triangles
        cut_stats = measure_mesh(cut_triangles)
        assert len(cut_triangles) < entry.obj.mesh.triangle_count
        assert float(cut_triangles[:, :, 0].min()) == pytest.approx(0.1234, abs=1e-4)
        assert float(cut_triangles[:, :, 0].max()) > 100
        assert 0 < cut_stats.volume < source_stats.volume
        assert entry.section_overlay.item in window.ui.graphicsView.items
        assert source_item not in window.ui.graphicsView.items

        panel.clearSectionButton.click()
        assert entry.section_overlay is None
        assert source_item in window.ui.graphicsView.items
        assert window.undoStl()
        assert window._stl_entries[0].section_overlay is not None
        assert window.redoStl()
        assert window._stl_entries[0].section_overlay is None
    finally:
        window.deleteLater()


def test_stl_statistics_dialog_uses_copyable_text(qt_app, monkeypatch):
    window = MainWindow()
    dialogs = []
    try:
        assert window.importStl(str(STL_SECTION_FIXTURE))
        monkeypatch.setattr(QDialog, "exec", lambda dialog: dialogs.append(dialog) or 0)
        window._show_selected_stl_statistics()
        text = dialogs[0].findChild(QPlainTextEdit, "stlStatisticsText")
        assert text is not None
        assert text.isReadOnly()
        assert "8499101" in text.toPlainText()
        assert "mm" in text.toPlainText()
        assert "Xmin = -127.870 mm" in text.toPlainText()
        assert "Xmax = 127.870 mm" in text.toPlainText()
        assert "Length = 255.740 mm" in text.toPlainText()
        inches = dialogs[0].findChild(QCheckBox, "stlStatisticsInchesCheck")
        assert inches is not None
        inches.setChecked(True)
        assert "Xmin = -5.034 in" in text.toPlainText()
        assert "Xmax = 5.034 in" in text.toPlainText()
        assert "Length = 10.069 in" in text.toPlainText()
        assert " mm" not in text.toPlainText()
    finally:
        window.deleteLater()


def test_stl_base_point_modes_show_coordinates_and_plot_marker(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE))
        panel = window.stlObjectsDock
        entry = window._stl_entries[0]
        pivot = entry.obj.pivot
        assert panel.pivotMode.currentData() == "center"
        assert all(field.isReadOnly() for field in (panel.pivotX, panel.pivotY, panel.pivotZ))
        assert (panel.pivotX.value(), panel.pivotY.value(), panel.pivotZ.value()) == pytest.approx(pivot)
        assert window._stl_pivot_item is not None
        assert window._stl_pivot_item.pos[0] == pytest.approx(entry.obj.world_pivot())

        panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("min"))
        assert entry.obj.pivot_mode == "min"
        assert window._stl_bbox_item in window.ui.graphicsView.items
        assert window._stl_bbox_picks_item in window.ui.graphicsView.items
        assert window._stl_bbox_picks_item.pos.shape == (8, 3)
        window.loadPlot()
        assert window._stl_bbox_item in window.ui.graphicsView.items
        assert window._stl_bbox_picks_item in window.ui.graphicsView.items
        stats = panel.format_measurements(entry.measurements)
        assert "Xmin = -91.000 mm; Xmax = 91.000 mm; Length = 182.000 mm" in stats
        pick_screen = window._project_world_to_screen(*window._stl_bbox_picks_item.pos[0])
        assert pick_screen is not None
        assert window._pick_stl_bbox_point(QPointF(*pick_screen))
        assert entry.obj.pivot_mode == "custom"
        assert entry.obj.pivot == pytest.approx((-91, -50, 0))
        assert window._stl_bbox_item in window.ui.graphicsView.items
        assert window._stl_bbox_picks_item in window.ui.graphicsView.items
        assert window._stl_bbox_picked_index == 0
        assert window._stl_bbox_picks_item.color[0] == pytest.approx((0.15, 0.9, 1.0, 1.0))
        assert window._stl_bbox_picks_item.size[0] == pytest.approx(16)
        second_pick = window._project_world_to_screen(*window._stl_bbox_picks_item.pos[1])
        assert second_pick is not None
        assert window._pick_stl_bbox_point(QPointF(*second_pick))
        assert window._stl_bbox_picked_index == 1
        assert window._stl_bbox_picks_item.color[1] == pytest.approx((0.15, 0.9, 1.0, 1.0))

        panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("origin"))
        assert entry.obj.pivot == pytest.approx((0, 0, 0))
        assert entry.obj.pivot_mode == "origin"
        assert window._stl_pivot_item.pos[0] == pytest.approx((0, 0, 0))

        panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("custom"))
        assert all(not field.isReadOnly() for field in (panel.pivotX, panel.pivotY, panel.pivotZ))
        panel.apply_theme("dark")
        panel.show()
        qt_app.processEvents()
        image = panel.grab().toImage()
        expected_border = panel.palette().color(QPalette.ColorRole.Mid)
        actual_border = image.pixelColor(0, image.height() // 2)
        assert actual_border.name() == expected_border.name()
    finally:
        window.deleteLater()


def test_stl_clear_and_import_are_independent_history_steps(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE))
        panel = window.stlObjectsDock
        first = window._stl_entries[0].obj
        assert not panel.undoButton.isEnabled()
        assert not window.undoStl()
        assert len(window._stl_entries) == 1
        assert not window.stlObjectsDock.isHidden()

        assert window.importStl(str(STL_FIXTURE))
        assert len(window._stl_entries) == 2
        window.clearStl()
        assert not window._stl_entries

        assert window.undoStl()
        assert len(window._stl_entries) == 2
        assert window.undoStl()
        assert [entry.obj for entry in window._stl_entries] == [first]
        assert window.redoStl()
        assert len(window._stl_entries) == 2
        assert window.redoStl()
        assert not window._stl_entries
    finally:
        window.deleteLater()


def test_stl_noop_transform_does_not_create_history_entry(qt_app):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE))
        depth = len(window._stl_undo)
        window._rotate_selected_stl("Z", 0)
        window._scale_selected_stl(1)
        window._rectangular_array_selected_stl(1, 1, 1, 10, 10, 10)
        assert len(window._stl_undo) == depth
    finally:
        window.deleteLater()
