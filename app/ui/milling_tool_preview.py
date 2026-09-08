"""Milling cutter preview attached to the existing pyqtgraph GL scene."""

from __future__ import annotations

import math

import numpy as np
from OpenGL import GL
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLMeshItem, MeshData
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem

TOOL_ALPHA = 0.45
TOOL_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glDepthMask": (False,),
    "glBlendFuncSeparate": (
        GL.GL_SRC_ALPHA,
        GL.GL_ONE_MINUS_SRC_ALPHA,
        GL.GL_ONE,
        GL.GL_ONE_MINUS_SRC_ALPHA,
    ),
}
SUPPORTED_TOOL_TYPES = frozenset({"mill_flat", "mill_bull", "mill_ball", "drill"})


def _tool_color(value) -> QColor:
    color = QColor(value)
    color.setAlphaF(TOOL_ALPHA)
    return color


class MillingToolPreviewItem(GLGraphicsItem):
    """Translucent configured milling cutter whose tip follows playback."""

    def __init__(self, color="#4d99ff", parentItem=None):
        super().__init__(parentItem=parentItem)
        self.setDepthValue(20)
        self._color = _tool_color(color)
        self._geometry_key = None
        self._meshes: list[GLMeshItem] = []
        self.setVisible(False)

    @property
    def geometry_key(self):
        """Current immutable geometry signature, primarily useful to diagnostics/tests."""
        return self._geometry_key

    @property
    def meshes(self):
        """Meshes owned by this scene item."""
        return tuple(self._meshes)

    def set_color(self, value) -> None:
        """Update material color without recreating cutter geometry."""
        color = _tool_color(value)
        if color.rgba() == self._color.rgba():
            return
        self._color = color
        for mesh in self._meshes:
            mesh.setColor(color)
        self.update()

    def show_tool(self, spec: dict[str, object] | None, position) -> bool:
        """Show a configured cutter with its tip at the resolved motion endpoint."""
        geometry = self._validated_geometry(spec)
        if geometry is None:
            self.hide_tool()
            return False
        if geometry != self._geometry_key:
            self._rebuild(*geometry)
        self.resetTransform()
        self.translate(*(float(value) for value in position))
        self.setVisible(True)
        self.update()
        return True

    def hide_tool(self) -> None:
        """Hide the preview while retaining reusable GPU-side mesh objects."""
        if self.visible():
            self.setVisible(False)
            self.update()

    @staticmethod
    def _validated_geometry(spec):
        if not isinstance(spec, dict):
            return None
        tool_type = str(spec.get("type", "")).strip().lower()
        if tool_type not in SUPPORTED_TOOL_TYPES:
            return None
        try:
            diameter = float(spec.get("diameter", 0.0))
            length = float(spec.get("length", 0.0))
            corner_radius = float(spec.get("cornerRadius", 0.0))
        except (TypeError, ValueError):
            return None
        if diameter <= 0.0 or length <= 0.0:
            return None
        radius = diameter * 0.5
        if tool_type == "mill_ball":
            corner_radius = radius
        elif tool_type == "mill_bull":
            corner_radius = min(max(corner_radius, 0.0), radius)
        else:
            corner_radius = 0.0
        return tool_type, diameter, length, corner_radius

    def _rebuild(self, tool_type: str, diameter: float, length: float, corner_radius: float) -> None:
        for mesh in self._meshes:
            mesh.setParentItem(None)
        self._meshes.clear()

        radius = diameter * 0.5
        if tool_type == "drill":
            # CNCEditor's preview uses a 120-degree included drill point.
            cone_height = min(length, radius / (3.0**0.5))
            profile = [(0.0, 0.0), (cone_height, radius), (length, radius)]
        elif tool_type == "mill_ball":
            # Lower hemisphere: the sphere pole is the programmed cutter tip.
            profile = [
                (radius * step / 12.0, math.sqrt(max(0.0, radius**2 - (radius * step / 12.0 - radius) ** 2)))
                for step in range(13)
            ]
            if length > radius:
                profile.append((length, radius))
        elif tool_type == "mill_bull" and corner_radius > 0.0:
            base_radius = radius - corner_radius
            profile = [
                (
                    corner_radius * step / 12.0,
                    base_radius
                    + math.sqrt(
                        max(
                            0.0,
                            corner_radius**2 - (corner_radius - corner_radius * step / 12.0) ** 2,
                        )
                    ),
                )
                for step in range(13)
            ]
            if length > corner_radius:
                profile.append((length, radius))
        else:
            profile = [(0.0, radius), (length, radius)]
        self._mesh(self._surface_of_revolution(profile))
        self._geometry_key = (tool_type, diameter, length, corner_radius)

    @staticmethod
    def _surface_of_revolution(profile, sides=32) -> MeshData:
        """Build one capped solid from ``(z, radius)`` profile samples."""
        vertices = []
        for z_value, radius in profile:
            vertices.extend(
                (
                    radius * math.cos(2.0 * math.pi * side / sides),
                    radius * math.sin(2.0 * math.pi * side / sides),
                    z_value,
                )
                for side in range(sides)
            )

        faces = []
        for ring in range(len(profile) - 1):
            first = ring * sides
            second = first + sides
            for side in range(sides):
                following = (side + 1) % sides
                faces.append((first + side, second + side, second + following))
                faces.append((first + side, second + following, first + following))

        for ring, reverse in ((0, True), (len(profile) - 1, False)):
            if profile[ring][1] <= 0.0:
                continue
            center = len(vertices)
            vertices.append((0.0, 0.0, profile[ring][0]))
            first = ring * sides
            for side in range(sides):
                following = (side + 1) % sides
                face = (center, first + following, first + side)
                faces.append(face if reverse else tuple(reversed(face)))

        return MeshData(
            vertexes=np.ascontiguousarray(vertices, dtype=np.float32),
            faces=np.ascontiguousarray(faces, dtype=np.uint32),
        )

    def _mesh(self, meshdata: MeshData) -> GLMeshItem:
        item = GLMeshItem(
            parentItem=self,
            meshdata=meshdata,
            color=self._color,
            smooth=True,
            drawFaces=True,
            drawEdges=False,
            shader="shaded",
            glOptions=TOOL_GL_OPTIONS,
        )
        self._meshes.append(item)
        return item
