# pylint: disable=protected-access
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from OpenGL import GL
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QVector3D, QVector4D
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.plot.stl import read_stl, stl_face_colors, stl_feature_edges

STL_FIXTURE = Path(__file__).resolve().parents[2] / "assets" / "stl" / "test.stl"
STL_CAMERA_FIXTURE = Path(__file__).resolve().parents[2] / "assets" / "stl" / "test2.stl"


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
    overlay = window._stl_overlay
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
    assert window._stl_overlay is None
    assert wireframe_item not in window.ui.graphicsView.items
    assert not window.ui.actionClearSTL.isEnabled()
    window.deleteLater()


def test_new_command_clears_stl_only_after_document_close_is_accepted(qt_app, monkeypatch):
    window = MainWindow()
    try:
        assert window.importStl(str(STL_FIXTURE)) is True
        item = window._stl_overlay.item
        assert item in window.ui.graphicsView.items

        monkeypatch.setattr(window, "maybeSave", lambda: False)
        window.ui.actionNew.trigger()
        assert window._stl_overlay.item is item
        assert item in window.ui.graphicsView.items

        monkeypatch.setattr(window, "maybeSave", lambda: True)
        window.ui.actionNew.trigger()
        assert window._stl_overlay is None
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
    assert window.ui.graphicsView.items.index(grid) < window.ui.graphicsView.items.index(window._stl_overlay.item)
    grid_options = grid.lineplot._GLGraphicsItem__glOpts
    stl_options = window._stl_overlay.item._GLGraphicsItem__glOpts
    assert grid_options["glDepthMask"] == (False,)
    assert stl_options["glDepthMask"] == (True,)
    assert grid_options[GL.GL_DEPTH_TEST] is True
    window.deleteLater()


def test_stl_item_and_mesh_data_are_reused_across_camera_views(qt_app):
    window = MainWindow()
    assert window.importStl(str(STL_CAMERA_FIXTURE)) is True
    overlay = window._stl_overlay
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
    assert not view.isOrthographic()
    assert view.projectionMode() == "perspective"
    assert overlay.item is item
    assert overlay.item.opts["meshdata"] is mesh_data
    assert item in view.items
    window.deleteLater()


def test_orbit_from_fixed_view_promotes_camera_to_perspective_3d(qt_app):
    window = MainWindow()
    assert window.importStl(str(STL_CAMERA_FIXTURE)) is True
    item = window._stl_overlay.item

    window.viewFront()
    assert window._view_mode == "front"
    assert window.ui.graphicsView.isOrthographic()

    window.ui.graphicsView.orbit(5.0, 3.0)

    assert window._view_mode == "3d"
    assert window.ui.graphicsView.projectionMode() == "perspective"
    assert window.ui.graphicsView.opts["fov"] == pytest.approx(60.0)
    assert window._stl_overlay.item is item
    assert item in window.ui.graphicsView.items
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
    assert window._stl_overlay.mesh.triangle_count == 1352
    assert window.ui.editor.text() == original_editor_text
    window.deleteLater()
