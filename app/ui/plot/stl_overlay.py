"""Persistent OpenGL representation of one transformed STL scene object."""

from __future__ import annotations

import numpy as np
from OpenGL import GL
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLLinePlotItem, GLMeshItem, MeshData

from app.ui.plot.stl import StlMesh, stl_face_colors, stl_feature_edges
from app.ui.plot.stl_transform import StlObject, transform_normals

STL_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: False,
    GL.GL_CULL_FACE: False,
    "glDepthFunc": (GL.GL_LEQUAL,),
    "glDepthMask": (True,),
}


class StlOverlay:
    """Own one immutable STL object and rebuild GL geometry only after object edits."""

    def __init__(self, obj: StlObject):
        self.object = obj
        self.mesh = obj.mesh
        self._feature_edges = None
        self._wire_positions = None
        self._appearance = None
        self.item = None
        self._rebuild_geometry()

    @property
    def bounds(self):
        return self._bounds

    def set_object(self, obj: StlObject):
        """Replace the object's transform while preserving its immutable source mesh."""
        if obj.mesh is not self.mesh:
            self.mesh = obj.mesh
            self._feature_edges = None
        self.object = obj
        self._wire_positions = None
        self._appearance = None
        self.item = None
        self._rebuild_geometry()

    def _rebuild_geometry(self):
        triangles = self.object.world_triangles()
        normals = transform_normals(self.mesh.normals, self.object.matrix)
        points = triangles.reshape((-1, 3))
        self._vertices = np.ascontiguousarray(points)
        self._faces = np.arange(len(self._vertices), dtype=np.uint32).reshape((-1, 3))
        self._render_mesh = StlMesh(
            triangles,
            normals,
            tuple((float(points[:, axis].min()), float(points[:, axis].max())) for axis in range(3)),
        )
        self._bounds = self._render_mesh.bounds

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
        if self._feature_edges is None:
            self._feature_edges = stl_feature_edges(self.mesh)
        if self._wire_positions is None:
            self._wire_positions = np.ascontiguousarray(self._vertices[self._feature_edges].reshape((-1, 3)))
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
            faceColors=stl_face_colors(self._render_mesh, base_color=(red, green, blue)),
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
