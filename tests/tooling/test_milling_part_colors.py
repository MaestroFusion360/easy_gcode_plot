"""Rendered material separation at the explicit cutting/body boundary."""

import numpy as np
import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from app import theme
from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.ui.plot.milling_tool_preview import MillingToolPreviewItem
from app.ui.plot.tool_library_preview import ToolLibraryPreview


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_library_renders_cutting_part_gold_and_body_gray(qt_app):
    preview = ToolLibraryPreview("milling")
    preview.set_tool(DEFAULT_MILLING_TOOL)
    image = preview.grab().toImage()
    assert image.pixelColor(120, 158).name() == "#e3aa37"
    assert image.pixelColor(120, 62).name() == "#94999f"
    preview.deleteLater()


@pytest.mark.parametrize("name,body_color", [("dark", "#f0f0f0"), ("light", "#3b3b3b")])
@pytest.mark.parametrize("flute", [30.0, 25.4])
def test_3d_face_colors_align_with_vertices_and_theme(qt_app, name, body_color, flute):
    item = MillingToolPreviewItem()
    item.set_theme(name)
    assert item.show_tool({**DEFAULT_MILLING_TOOL, "fluteLength": flute}, (0, 0, 0))
    mesh = item.meshes[0]
    mesh.parseMeshData()
    assert mesh.colors.shape[:2] == mesh.vertexes.shape[:2]
    cutting = mesh.vertexes[:, :, 2].max(axis=1) <= np.float32(flute)
    assert cutting.any() and (~cutting).any()
    assert np.allclose(mesh.colors[cutting][..., :3], QColor("#e3aa37").getRgbF()[:3])
    assert np.allclose(mesh.colors[~cutting][..., :3], QColor(body_color).getRgbF()[:3])


def test_theme_and_custom_cutting_color_update_existing_mesh(qt_app):
    item = MillingToolPreviewItem()
    item.show_tool(DEFAULT_MILLING_TOOL, (0, 0, 0))
    mesh = item.meshes[0]
    item.set_theme("dark")
    item.set_color("#abcdef")
    assert item.meshes == (mesh,)
    mesh.parseMeshData()
    cutting = mesh.vertexes[:, :, 2].mean(axis=1) <= 30
    assert np.allclose(mesh.colors[cutting][..., :3], QColor("#abcdef").getRgbF()[:3])
    assert np.allclose(mesh.colors[~cutting][..., :3], QColor("#f0f0f0").getRgbF()[:3])


def test_legacy_tools_do_not_invent_a_gray_body(qt_app):
    spec = {"type": "mill_flat", "diameter": 10, "length": 50}
    item = MillingToolPreviewItem()
    item.show_tool(spec, (0, 0, 0))
    assert not item.meshes[0].opts["meshdata"].hasFaceColor()
    preview = ToolLibraryPreview("milling")
    preview.set_tool(spec)
    assert preview.grab().toImage().pixelColor(120, 62).name() == "#e3aa37"
    preview.deleteLater()


@pytest.mark.parametrize("color", ["#4d99ff", "#7fb2ff"])
def test_old_default_blue_becomes_theme_gold_but_custom_colors_remain(color):
    assert theme.themed_plot_value(color, "tool", "light") == "#e3aa37"
    assert theme.themed_plot_value(color, "tool", "dark") == "#f1c75b"
    assert theme.themed_plot_value("#123456", "tool", "dark") == "#123456"
