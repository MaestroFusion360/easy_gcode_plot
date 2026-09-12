"""OpenGL stock section and geometry-driven turning-tool overlay."""

from __future__ import annotations

import numpy as np
from OpenGL import GL
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLMeshItem, MeshData
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem

from app.gcode.stock import TurningStockTimeline, profile_interval_mesh_spans
from app.gcode.turning_tool_geometry import display_tool_geometry

STOCK_COLOR = "#4fa7a0"
TOOL_COLOR = "#ffd23f"
STOCK_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glDepthMask": (True,),
    "glBlendFuncSeparate": (
        GL.GL_SRC_ALPHA,
        GL.GL_ONE_MINUS_SRC_ALPHA,
        GL.GL_ONE,
        GL.GL_ONE_MINUS_SRC_ALPHA,
    ),
}


def _mesh_data(vertices, faces) -> MeshData:
    return MeshData(
        vertexes=np.ascontiguousarray(vertices, dtype=np.float32).reshape((-1, 3)),
        faces=np.ascontiguousarray(faces, dtype=np.uint32).reshape((-1, 3)),
    )


def _extruded_polygon(points, depth: float) -> MeshData:
    """Create a small 3D prism from an X/Z cutter silhouette."""
    count = len(points)
    half = depth * 0.5
    vertices = [(x, -half, z) for x, z in points] + [(x, half, z) for x, z in points]
    faces = []
    for index in range(1, count - 1):
        faces.append((0, index + 1, index))
        faces.append((count, count + index, count + index + 1))
    for index in range(count):
        following = (index + 1) % count
        faces.extend(((index, following, count + following), (index, count + following, count + index)))
    return _mesh_data(vertices, faces)


def _tool_geometry(spec: dict[str, object], stock_diameter: float):
    return display_tool_geometry(spec, stock_diameter)


def material_interval_mesh_spans(first, second):
    """Match radial material intervals without cross-connecting separate rings."""
    if len(first) == len(second) and all(
        min(outer0, outer1) > max(inner0, inner1)
        for (inner0, outer0), (inner1, outer1) in zip(first, second, strict=True)
    ):
        return tuple((*interval0, *interval1) for interval0, interval1 in zip(first, second, strict=True))

    # At a topology change, split the common material into independent bands.
    # Connecting one whole interval to multiple rings produces overlapping
    # triangles that visually fill a groove and gives the mesh non-manifold
    # crossings. Constant overlap bands create a clean vertical transition.
    spans = []
    for inner0, outer0 in first:
        for inner1, outer1 in second:
            inner = max(inner0, inner1)
            outer = min(outer0, outer1)
            if outer > inner:
                spans.append((inner, outer, inner, outer))
    return tuple(spans)


class TurningStockOverlayItem(GLGraphicsItem):
    """Dynamic stock section plus a 3D active turning tool."""

    def __init__(self, parentItem=None):
        super().__init__(parentItem=parentItem)
        self.setDepthValue(-20)
        self._stock_mesh = GLMeshItem(
            parentItem=self,
            meshdata=_mesh_data([], []),
            color=QColor(STOCK_COLOR),
            smooth=False,
            drawFaces=True,
            drawEdges=False,
            shader="shaded",
            glOptions=STOCK_GL_OPTIONS,
        )
        self._tool_mesh = GLMeshItem(
            parentItem=self,
            meshdata=_mesh_data([], []),
            color=QColor(TOOL_COLOR),
            smooth=False,
            drawFaces=True,
            drawEdges=True,
            edgeColor=QColor("#6f6f18"),
            # Keep the cutting insert gold regardless of scene-light direction.
            # This is local to the turning tool and does not alter stock, STL,
            # grid or toolpath lighting/material state.
            shader=None,
            glOptions=STOCK_GL_OPTIONS,
        )
        self._tool_mesh.setDepthValue(20)
        self._stock_revision = None
        self._tool_geometry_key = None
        self.last_stock_vertex_count = 0
        self.last_stock_face_count = 0
        self.setVisible(False)

    def clear(self) -> None:
        self.setVisible(False)
        self._tool_mesh.setVisible(False)
        self._stock_revision = None

    def set_frame(
        self,
        timeline: TurningStockTimeline,
        tool_position,
        tool_spec,
        *,
        update_stock: bool = True,
    ) -> None:
        if update_stock and self._stock_revision != timeline.revision:
            self._set_stock_mesh(timeline)
            self._stock_revision = timeline.revision
        self._set_tool(timeline.spec.outer_diameter, tool_position, tool_spec or {})
        self.setVisible(True)
        self.update()

    def _set_stock_mesh(self, timeline: TurningStockTimeline) -> None:
        if any(len(intervals) != 1 for intervals in timeline.material_intervals):
            self._set_interval_stock_mesh(timeline)
            return
        breaks = timeline.profile_breaks
        if not breaks:
            z_values = np.asarray(timeline.z, dtype=np.float32)
            inner = np.asarray(timeline.inner, dtype=np.float32)
            outer = np.asarray(timeline.outer, dtype=np.float32)
            count = len(z_values)
            vertices = np.empty((count * 4, 3), dtype=np.float32)
            vertices[:, 1] = 0.0
            vertices[0::4, 0] = inner
            vertices[1::4, 0] = outer
            vertices[2::4, 0] = -outer
            vertices[3::4, 0] = -inner
            vertices[0::4, 2] = z_values
            vertices[1::4, 2] = z_values
            vertices[2::4, 2] = z_values
            vertices[3::4, 2] = z_values

            interval = np.arange(max(0, count - 1), dtype=np.uint32)
            valid = (outer[:-1] > inner[:-1]) | (outer[1:] > inner[1:])
            interval = interval[valid]
            base = interval * 4
            following = base + 4
            faces = np.empty((len(interval) * 4, 3), dtype=np.uint32)
            faces[0::4] = np.column_stack((base, base + 1, following + 1))
            faces[1::4] = np.column_stack((base, following + 1, following))
            faces[2::4] = np.column_stack((base + 2, base + 3, following + 3))
            faces[3::4] = np.column_stack((base + 2, following + 3, following + 2))
            self.last_stock_vertex_count = len(vertices)
            self.last_stock_face_count = len(faces)
            self._stock_mesh.setMeshData(meshdata=MeshData(vertexes=vertices, faces=faces))
            return

        vertices = []
        faces = []
        for index in range(len(timeline.z) - 1):
            z0, z1 = timeline.z[index], timeline.z[index + 1]
            i0, i1 = timeline.inner[index], timeline.inner[index + 1]
            o0, o1 = timeline.outer[index], timeline.outer[index + 1]
            for za, zb, ia, oa, ib, ob in profile_interval_mesh_spans(z0, z1, i0, o0, i1, o1, breaks):
                if oa <= ia and ob <= ib:
                    continue
                upper = len(vertices)
                vertices.extend(((ia, 0.0, za), (oa, 0.0, za), (ob, 0.0, zb), (ib, 0.0, zb)))
                faces.extend(((upper, upper + 1, upper + 2), (upper, upper + 2, upper + 3)))
                lower = len(vertices)
                vertices.extend(((-oa, 0.0, za), (-ia, 0.0, za), (-ib, 0.0, zb), (-ob, 0.0, zb)))
                faces.extend(((lower, lower + 1, lower + 2), (lower, lower + 2, lower + 3)))
        self.last_stock_vertex_count = len(vertices)
        self.last_stock_face_count = len(faces)
        self._stock_mesh.setMeshData(meshdata=_mesh_data(vertices, faces))

    def _set_interval_stock_mesh(self, timeline: TurningStockTimeline) -> None:
        """Render stock slices that may contain disconnected radial material."""
        vertices = []
        faces = []
        for index in range(len(timeline.z) - 1):
            z0, z1 = timeline.z[index], timeline.z[index + 1]
            first = timeline.material_intervals[index]
            second = timeline.material_intervals[index + 1]
            for inner0, outer0, inner1, outer1 in material_interval_mesh_spans(first, second):
                for za, zb, ia, oa, ib, ob in profile_interval_mesh_spans(
                    z0, z1, inner0, outer0, inner1, outer1, timeline.profile_breaks
                ):
                    upper = len(vertices)
                    vertices.extend(((ia, 0.0, za), (oa, 0.0, za), (ob, 0.0, zb), (ib, 0.0, zb)))
                    faces.extend(((upper, upper + 1, upper + 2), (upper, upper + 2, upper + 3)))
                    lower = len(vertices)
                    vertices.extend(((-oa, 0.0, za), (-ia, 0.0, za), (-ib, 0.0, zb), (-ob, 0.0, zb)))
                    faces.extend(((lower, lower + 1, lower + 2), (lower, lower + 2, lower + 3)))
        self.last_stock_vertex_count = len(vertices)
        self.last_stock_face_count = len(faces)
        self._stock_mesh.setMeshData(meshdata=_mesh_data(vertices, faces))

    def _set_tool(self, stock_diameter: float, position, spec) -> None:
        points, depth, key = _tool_geometry(spec, stock_diameter)
        if key != self._tool_geometry_key:
            self._tool_mesh.setMeshData(meshdata=_extruded_polygon(points, depth))
            self._tool_geometry_key = key
        x_value, z_value = position
        self._tool_mesh.resetTransform()
        self._tool_mesh.translate(float(x_value), -0.25, float(z_value))
        self._tool_mesh.setVisible(True)
