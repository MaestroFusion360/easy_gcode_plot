"""Persistent OpenGL representation of one parsed STL mesh."""

from __future__ import annotations

import numpy as np
from OpenGL import GL
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLLinePlotItem, GLMeshItem, MeshData

from app.ui.stl import StlMesh, stl_face_colors, stl_feature_edges

STL_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: False,
    GL.GL_CULL_FACE: False,
    "glDepthMask": (True,),
}


class StlOverlay:
    """Own immutable STL geometry and rebuild only when its appearance changes."""

    def __init__(self, mesh: StlMesh):
        self.mesh = mesh
        self._vertices = np.ascontiguousarray(mesh.triangles.reshape((-1, 3)))
        self._faces = np.arange(len(self._vertices), dtype=np.uint32).reshape((-1, 3))
        self._wire_positions = None
        self._appearance = None
        self.item = None

    def item_for(self, color, wireframe: bool):
        """Return the current GL item, rebuilding only for a changed visual style."""
        base = QColor(color)
        appearance = (base.rgba(), bool(wireframe))
        if self.item is not None and appearance == self._appearance:
            return self.item

        self.item = self._create_wireframe_item(base) if wireframe else self._create_solid_item(base)
        self._appearance = appearance
        return self.item

    def _create_wireframe_item(self, base: QColor):
        if self._wire_positions is None:
            edges = stl_feature_edges(self.mesh)
            self._wire_positions = np.ascontiguousarray(self._vertices[edges].reshape((-1, 3)))
        edge_color = QColor("#606060" if base.lightnessF() < 0.35 else "#383838")
        item = GLLinePlotItem(
            pos=self._wire_positions,
            color=edge_color,
            width=1.0,
            antialias=False,
            mode="lines",
        )
        item.setGLOptions(STL_GL_OPTIONS)
        return item

    def _create_solid_item(self, base: QColor):
        red, green, blue, _alpha = base.getRgbF()
        mesh_data = MeshData(
            vertexes=self._vertices,
            faces=self._faces,
            faceColors=stl_face_colors(self.mesh, base_color=(red, green, blue)),
        )
        item = GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            drawFaces=True,
            drawEdges=False,
            shader=None,
        )
        item.setGLOptions(STL_GL_OPTIONS)
        return item
