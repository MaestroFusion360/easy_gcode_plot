"""Custom widgets referenced by Qt Designer forms."""

from math import cos, radians, sin, tan

import numpy as np
from OpenGL import GL
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QMatrix4x4, QPainter, QVector3D
from pyqtgraph.opengl import GLViewWidget


class Editor(QsciScintilla):
    """QScintilla editor used by the main window Designer form."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(False)


class PlotView(GLViewWidget):
    """OpenGL plot widget with explicit perspective and orthographic projections."""

    orthographicOrbitStarted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._background_gradient = False
        self._projection_mode = "perspective"
        self._orthographic_width = 2.0
        self._orthographic_near = 0.01
        self._orthographic_far = 1000.0

    def setBackgroundGradient(self, enabled, color):
        """Configure the optional CNCEditor-style vertical canvas gradient."""
        self._background_gradient = bool(enabled)
        self.setBackgroundColor(color)

    def projectionMode(self):
        """Return the active camera projection mode."""
        return self._projection_mode

    def isOrthographic(self):
        """Return whether the view currently uses a parallel projection."""
        return self._projection_mode == "orthographic"

    def setProjectionMode(self, mode):
        """Switch between the native perspective path and the orthographic path."""
        if mode not in {"perspective", "orthographic"}:
            raise ValueError("projection mode must be 'perspective' or 'orthographic'")
        if mode == self._projection_mode:
            return
        self._projection_mode = mode
        self.update()

    def setOrthographicProjection(self, width, near_clip, far_clip):
        """Set the visible horizontal span and depth range for parallel projection."""
        width = max(float(width), 1e-9)
        near_clip = max(float(near_clip), 1e-6)
        far_clip = max(float(far_clip), near_clip + 1e-6)
        self._orthographic_width = width
        self._orthographic_near = near_clip
        self._orthographic_far = far_clip
        self._projection_mode = "orthographic"
        self.update()

    def orthographicWidth(self):
        """Return the visible horizontal world span in orthographic mode."""
        return self._orthographic_width

    def projectionMatrix(self, region, viewport):
        """Build a true orthographic matrix for fixed milling views."""
        if not self.isOrthographic():
            return super().projectionMatrix(region, viewport)

        x0, y0, viewport_width, viewport_height = viewport
        viewport_width = max(float(viewport_width), 1.0)
        viewport_height = max(float(viewport_height), 1.0)
        half_width = self._orthographic_width * 0.5
        half_height = half_width * viewport_height / viewport_width

        left = half_width * ((region[0] - x0) * (2.0 / viewport_width) - 1.0)
        right = half_width * ((region[0] + region[2] - x0) * (2.0 / viewport_width) - 1.0)
        bottom = half_height * ((region[1] - y0) * (2.0 / viewport_height) - 1.0)
        top = half_height * ((region[1] + region[3] - y0) * (2.0 / viewport_height) - 1.0)

        matrix = QMatrix4x4()
        matrix.ortho(left, right, bottom, top, self._orthographic_near, self._orthographic_far)
        return matrix

    def pixelSize(self, pos):
        """Return a constant world-units-per-pixel scale for orthographic views."""
        if not self.isOrthographic():
            return super().pixelSize(pos)
        scale = self._orthographic_width / max(float(self.width()), 1.0)
        if isinstance(pos, np.ndarray):
            return np.full(pos.shape[:-1], scale, dtype=float)
        return scale

    def pan(self, dx, dy, dz, relative="global"):
        """Pan orthographic views without deriving scale from perspective FOV."""
        if not self.isOrthographic() or relative != "view" or self.opts["rotationMethod"] != "euler":
            return super().pan(dx, dy, dz, relative=relative)

        scale = self._orthographic_width / max(float(self.width()), 1.0)
        elev = radians(self.opts["elevation"])
        azim = radians(self.opts["azimuth"])
        z = scale * cos(elev) * dy
        x = scale * (sin(azim) * dx - sin(elev) * cos(azim) * dy)
        y = scale * (cos(azim) * dx + sin(elev) * sin(azim) * dy)
        self.opts["center"] += QVector3D(x, -y, z)
        self.update()

    def zoomBy(self, factor):
        """Zoom using projection-appropriate state."""
        factor = max(float(factor), 1e-6)
        if self.isOrthographic():
            self._orthographic_width = max(self._orthographic_width * factor, 1e-9)
            self.update()
        else:
            self.setCameraPosition(distance=max(float(self.opts["distance"]) * factor, 1e-9))

    def orbit(self, azim, elev):
        """Start free rotation in perspective when leaving a fixed orthographic view."""
        was_orthographic = self.isOrthographic()
        if was_orthographic:
            fov = 60.0
            half_angle = radians(fov) * 0.5
            self._projection_mode = "perspective"
            self.opts["fov"] = fov
            self.opts["distance"] = max(self._orthographic_width * 0.5 / tan(half_angle), 1e-9)
        super().orbit(azim, elev)
        if was_orthographic:
            self.orthographicOrbitStarted.emit()

    def wheelEvent(self, ev):
        """Zoom parallel views by changing their world span rather than camera depth."""
        if not self.isOrthographic():
            return super().wheelEvent(ev)
        delta = ev.angleDelta().x()
        if delta == 0:
            delta = ev.angleDelta().y()
        self.zoomBy(0.999**delta)
        ev.accept()

    @staticmethod
    def _adjust_color(color, amount):
        red, green, blue, alpha = QColor(color).getRgbF()
        return QColor.fromRgbF(
            max(0.0, min(1.0, red + amount)),
            max(0.0, min(1.0, green + amount)),
            max(0.0, min(1.0, blue + amount)),
            alpha,
        )

    def paintGL(self):
        if not self._background_gradient:
            super().paintGL()
            return

        background = QColor.fromRgbF(*self.opts["bgcolor"])
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, self._adjust_color(background, -0.12))
        gradient.setColorAt(1.0, self._adjust_color(background, 0.18))
        painter = QPainter(self)
        painter.fillRect(self.rect(), gradient)
        painter.end()

        region = self.getViewport()
        self.setProjection(region, region)
        self.setModelview()
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        self.drawItemTree()

    def mouseMoveEvent(self, ev):
        position = ev.position() if hasattr(ev, "position") else ev.localPos()
        if not hasattr(self, "mousePos"):
            self.mousePos = position
        diff = position - self.mousePos
        self.mousePos = position

        if ev.buttons() == Qt.MouseButton.LeftButton:
            if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.pan(diff.x(), diff.y(), 0, relative="view")
            elif self.opts["rotationMethod"] == "euler":
                self.orbit(-diff.x(), diff.y())
            else:
                self.pan(diff.x(), diff.y(), 0, relative="view")
        elif ev.buttons() == Qt.MouseButton.MiddleButton:
            if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.pan(diff.x(), diff.y(), 0, relative="view")
            elif self.opts["rotationMethod"] == "euler":
                self.orbit(-diff.x(), diff.y())
            else:
                self.pan(diff.x(), diff.y(), 0, relative="view")
