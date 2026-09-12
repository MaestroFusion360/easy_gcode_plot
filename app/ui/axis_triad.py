"""World-space axis triad adapted from CNCEditor's AxisTriade renderer."""

from __future__ import annotations

from OpenGL import GL
from PyQt6.QtGui import QColor, QFont, QVector3D
from pyqtgraph.opengl import GLMeshItem, GLTextItem, MeshData
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem

AXIS_LENGTH_PX = 48.0
AXIS_DEPTH = 100
# The triad is an orientation aid, not a lit scene object.  Keep these colors
# invariant under camera rotation and scene lighting.
AXIS_ORIGIN_COLOR = QColor("#ffd400")
AXIS_COLORS = {
    "X": QColor("#e02020"),
    "Y": QColor("#159447"),
    "Z": QColor("#1769d2"),
}
AXIS_OPAQUE_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: False,
    GL.GL_BLEND: False,
    GL.GL_CULL_FACE: False,
}
AXIS_TEXT_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: False,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glBlendFuncSeparate": (
        GL.GL_SRC_ALPHA,
        GL.GL_ONE_MINUS_SRC_ALPHA,
        GL.GL_ONE,
        GL.GL_ONE_MINUS_SRC_ALPHA,
    ),
}


class AxisTriadItem(GLGraphicsItem):
    """A centered, fixed-pixel-size triad with camera-facing axis labels."""

    def __init__(self, parentItem=None):
        super().__init__(parentItem=parentItem)
        self.setDepthValue(AXIS_DEPTH)
        self.center = (0.0, 0.0, 0.0)
        self.extent = 1.0
        self._meshes = []
        self._labels = []

        sphere = GLMeshItem(
            parentItem=self,
            meshdata=MeshData.sphere(rows=12, cols=18, radius=0.055),
            color=AXIS_ORIGIN_COLOR,
            smooth=True,
            shader=None,
            glOptions=AXIS_OPAQUE_GL_OPTIONS,
        )
        self._meshes.append(sphere)

        axes = (
            ("X", AXIS_COLORS["X"], (0.0, 1.0, 0.0, 90.0), (1.12, 0.0, 0.0)),
            ("Y", AXIS_COLORS["Y"], (1.0, 0.0, 0.0, -90.0), (0.0, 1.12, 0.0)),
            ("Z", AXIS_COLORS["Z"], None, (0.0, 0.0, 1.12)),
        )
        label_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        for label, color, rotation, label_position in axes:
            self._add_arrow(color, rotation)
            text = GLTextItem(
                parentItem=self,
                pos=label_position,
                color=color,
                text=label,
                font=label_font,
                glOptions=AXIS_TEXT_GL_OPTIONS,
            )
            text.setDepthValue(20)
            self._labels.append(text)

    def _add_arrow(self, color: QColor, rotation) -> None:
        shaft = GLMeshItem(
            parentItem=self,
            meshdata=MeshData.cylinder(rows=1, cols=18, radius=[0.022, 0.022], length=0.72),
            color=color,
            smooth=True,
            shader=None,
            glOptions=AXIS_OPAQUE_GL_OPTIONS,
        )
        cone = GLMeshItem(
            parentItem=self,
            meshdata=MeshData.cylinder(rows=1, cols=18, radius=[0.075, 0.0], length=0.28),
            color=color,
            smooth=True,
            shader=None,
            glOptions=AXIS_OPAQUE_GL_OPTIONS,
        )
        cone.translate(0.0, 0.0, 0.72)
        if rotation is not None:
            x, y, z, angle = rotation
            shaft.rotate(angle, x, y, z)
            cone.rotate(angle, x, y, z)
        self._meshes.extend((shaft, cone))

    def set_center(self, center) -> None:
        """Move the triad without tying its size to toolpath dimensions."""
        self.center = tuple(float(value) for value in center)
        self._apply_transform(self.extent)

    def _apply_transform(self, extent: float) -> None:
        self.extent = max(float(extent), 1e-9)
        self.resetTransform()
        self.translate(*self.center)
        self.scale(self.extent, self.extent, self.extent)

    def paint(self) -> None:
        """Adjust world scale so one unit remains ``AXIS_LENGTH_PX`` on screen."""
        self.sync_screen_size()

    def sync_screen_size(self) -> None:
        """Synchronize scale before the next scene traversal after camera changes."""
        view = self.view()
        if view is None or view.width() <= 0:
            return
        pixel_size = float(view.pixelSize(QVector3D(*self.center)))
        extent = max(pixel_size * AXIS_LENGTH_PX, 1e-9)
        if abs(extent - self.extent) > max(extent, self.extent) * 1e-6:
            self._apply_transform(extent)
