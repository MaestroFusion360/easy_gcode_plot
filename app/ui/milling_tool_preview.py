"""Milling cutter preview attached to the existing pyqtgraph GL scene."""

from __future__ import annotations

import math

import numpy as np
from OpenGL import GL
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLMeshItem, MeshData
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem

from app.tools.milling_geometry import milling_geometry_key, milling_tool_profile

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
SUPPORTED_TOOL_TYPES = frozenset(
    {"mill_flat", "mill_bull", "mill_ball", "face_mill", "slot_mill", "chamfer_mill", "drill", "tap"}
)


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
        return milling_geometry_key(spec)

    def _rebuild(self, *geometry_key) -> None:
        tool_type, diameter, length, corner_radius, *extra = geometry_key
        spec = {
            "type": tool_type,
            "diameter": diameter,
            "length": length,
            "cornerRadius": corner_radius,
        }
        if tool_type in {"face_mill", "slot_mill"}:
            spec.update(cuttingHeight=extra[0], shankDiameter=extra[1])
        elif tool_type == "chamfer_mill":
            spec.update(tipDiameter=extra[0], chamferAngle=extra[1])
        elif tool_type == "drill":
            spec["tipAngle"] = extra[0]
        profile = milling_tool_profile(spec)
        meshdata = self._surface_of_revolution(profile)
        if self._meshes:
            # Keep the scene-registered GL item and its context lifecycle.
            # Replacing the child after its first paint can leave the new item
            # without a repaint/initialization on some OpenGL drivers.
            self._meshes[0].setMeshData(meshdata=meshdata)
            self._meshes[0].setColor(self._color)
            for obsolete in self._meshes[1:]:
                obsolete.setParentItem(None)
            del self._meshes[1:]
        else:
            self._mesh(meshdata)
        self._geometry_key = geometry_key

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
