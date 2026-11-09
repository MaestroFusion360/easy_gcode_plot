"""Screen-sized orientation cube with face, edge and corner view selection."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPolygonF, QTransform
from PyQt6.QtWidgets import QWidget

from app.ui.plot.camera_basis import camera_basis


class ViewCube(QWidget):
    """Transparent overlay that emits the camera angles for a picked region."""

    viewRequested = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ViewCube")
        self.setAccessibleName(self.tr("View cube"))
        self.setFixedSize(128, 128)
        self.setMouseTracking(True)
        self.yaw, self.pitch = 43.0, 28.0
        self._basis = None
        self._hover = None

    def set_orientation(self, yaw, pitch, right=None, up=None):
        """Set the camera angles and, optionally, the camera's screen basis.

        A yaw/pitch pair is enough for the euler camera. Quaternion views can
        roll the camera, so the projection also accepts the actual right/up
        vectors used by the plot.
        """
        basis = None
        if right is not None and up is not None:
            basis = (
                float(right.x()),
                float(right.y()),
                float(right.z()),
                float(up.x()),
                float(up.y()),
                float(up.z()),
            )
        if (yaw, pitch, basis) != (self.yaw, self.pitch, self._basis):
            self.yaw, self.pitch, self._basis = yaw, pitch, basis
            self._hover = None
            self.update()

    def _faces(self):
        eye, right, up = ((vector.x(), vector.y(), vector.z()) for vector in camera_basis(self.yaw, self.pitch))
        if self._basis is not None:
            right = self._basis[:3]
            up = self._basis[3:]
        labels = (
            (self.tr("Left"), self.tr("Right")),
            (self.tr("Front"), self.tr("Back")),
            (self.tr("Bottom"), self.tr("Top")),
        )
        faces = []
        for axis in range(3):
            for sign in (-1, 1):
                facing = eye[axis] * sign
                if facing <= 1e-6:
                    continue
                axes = [index for index in range(3) if index != axis]

                def project(u, v, axis=axis, sign=sign, axes=axes):
                    point = [0, 0, 0]
                    point[axis] = sign
                    point[axes[0]], point[axes[1]] = u, v
                    x = sum(a * b for a, b in zip(point, right))
                    y = sum(a * b for a, b in zip(point, up))
                    return QPointF(self.width() / 2 + x * 30, self.height() / 2 - y * 30)

                polygon = QPolygonF([project(-1, -1), project(1, -1), project(1, 1), project(-1, 1)])
                faces.append((axis, sign, axes, labels[axis][sign > 0], facing, polygon))
        return faces

    def _regions(self):
        regions = []
        divisions = (-1, -0.6, 0.6, 1)
        for axis, sign, axes, label, _facing, polygon in self._faces():
            origin = polygon[0]
            u, v = (polygon[1] - origin) * 0.5, (polygon[3] - origin) * 0.5
            for row in range(3):
                for column in range(3):
                    low_u, high_u = divisions[column : column + 2]
                    low_v, high_v = divisions[row : row + 2]
                    patch = QPolygonF(
                        [
                            origin + u * (x + 1) + v * (y + 1)
                            for x, y in ((low_u, low_v), (high_u, low_v), (high_u, high_v), (low_u, high_v))
                        ]
                    )
                    direction = [0, 0, 0]
                    direction[axis] = sign
                    direction[axes[0]] = column - 1
                    direction[axes[1]] = row - 1
                    regions.append((patch, tuple(direction), label))
        return regions

    def _hit(self, position):
        return next(
            (
                direction
                for patch, direction, _label in self._regions()
                if patch.containsPoint(position, Qt.FillRule.OddEvenFill)
            ),
            None,
        )

    def paintEvent(self, _event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            faces = self._faces()
            for axis, sign, _axes, _label, facing, polygon in faces:
                shade = round(185 + facing * 45)
                hovered_face = (
                    self._hover is not None
                    and sum(value != 0 for value in self._hover) == 1
                    and self._hover[axis] == sign
                )
                painter.setBrush(QColor("#85b9e1") if hovered_face else QColor(shade, shade + 2, shade + 4))
                painter.setPen(QPen(QColor("#8b9198"), 1.4))
                painter.drawPolygon(polygon)
            for patch, direction, _label in self._regions():
                if direction == self._hover and sum(value != 0 for value in direction) > 1:
                    painter.setBrush(QColor("#85b9e1"))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawPolygon(patch)
            for axis, sign, _axes, label, _facing, polygon in faces:
                self._paint_label(painter, polygon, axis, sign, label)
        finally:
            painter.end()

    def _paint_label(self, painter, polygon, axis, sign, label):
        origin = polygon[0]
        u, v = (polygon[1] - origin) * 0.5, (polygon[3] - origin) * 0.5
        right = sign if axis == 0 else -sign if axis == 1 else 1
        up = sign if axis == 2 else 1
        top_left = origin + u * (1 - right) + v * (1 + up)
        top_right = origin + u * (1 + right) + v * (1 + up)
        bottom_left = origin + u * (1 - right) + v * (1 - up)
        horizontal, vertical = (top_right - top_left) / 64, (bottom_left - top_left) / 64
        painter.save()
        try:
            painter.setTransform(
                QTransform(horizontal.x(), horizontal.y(), vertical.x(), vertical.y(), top_left.x(), top_left.y()),
                True,
            )
            font = painter.font()
            font.setBold(True)
            font.setPixelSize(13)
            text = label.upper()
            width = QFontMetrics(font).horizontalAdvance(text)
            font.setPixelSize(max(8, round(13 * min(1, 54 / max(1, width)))))
            painter.setFont(font)
            painter.setPen(QColor("#20272f"))
            painter.drawText(QRectF(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, text)
        finally:
            painter.restore()

    def mouseMoveEvent(self, event):
        hovered = self._hit(event.position())
        if hovered != self._hover:
            self._hover = hovered
            self.setCursor(Qt.CursorShape.PointingHandCursor if hovered else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        self._hover = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        direction = self._hit(event.position())
        if event.button() == Qt.MouseButton.LeftButton and direction is not None:
            x, y, z = direction
            horizontal = math.hypot(x, y)
            yaw = math.degrees(math.atan2(y, x)) if horizontal else -90.0
            pitch = math.degrees(math.atan2(z, horizontal))
            self.viewRequested.emit(yaw, pitch)
            event.accept()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.viewRequested.emit(43.0, 28.0)
            event.accept()
        else:
            event.ignore()
