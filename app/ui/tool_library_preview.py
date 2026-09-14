"""Compact painter-based previews used by both tool-library dialogs."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from app.gcode.turning_tool_geometry import display_tool_geometry, lathe_view_point
from app.tools.milling_geometry import milling_tool_profile


class ToolLibraryPreview(QWidget):
    """Render the selected tool without requiring an OpenGL context."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.spec: dict[str, object] = {}
        self.zoom = 1.0
        self.setFixedSize(240, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_tool(self, spec: dict[str, object] | None) -> None:
        self.spec = dict(spec) if spec is not None else {}
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = min(4.0, max(0.5, float(zoom)))
        side = round(240 * self.zoom)
        self.setFixedSize(side, side)
        self.update()

    def wheelEvent(self, event):
        step = 0.15 if event.angleDelta().y() > 0 else -0.15
        self.set_zoom(self.zoom + step)
        event.accept()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f7f8fa"))
        if not self.spec:
            return
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.setPen(QPen(QColor("#9a6500"), 2))
        painter.setBrush(QColor("#e3aa37"))
        if self.kind == "milling":
            self._paint_milling(painter)
        else:
            self._paint_turning(painter)

    def _paint_milling(self, painter: QPainter) -> None:
        profile = milling_tool_profile(self.spec)
        if not profile:
            return
        length = max(point[0] for point in profile)
        radius = max(point[1] for point in profile)
        span = max(length, radius * 2.0, 1.0)
        scale = 90.0 / span * self.zoom
        height = length * scale
        painter.translate(0.0, height / 2.0)

        path = QPainterPath()
        left = [QPointF(-tool_radius * scale, -z_value * scale) for z_value, tool_radius in profile]
        right = [QPointF(tool_radius * scale, -z_value * scale) for z_value, tool_radius in reversed(profile)]
        points = left + right
        if not points:
            return
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)
        self._paint_trace_point(painter, QPointF(0.0, 0.0))

    def _paint_turning(self, painter: QPainter) -> None:
        points, _depth, _cache_key = display_tool_geometry(self.spec, 50.0)
        if not points:
            return
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_z = min(point[1] for point in points)
        max_z = max(point[1] for point in points)
        span = max(max_x - min_x, max_z - min_z, 1.0)
        scale = 80.0 / span * self.zoom
        center_x = (min_x + max_x) * 0.5
        center_z = (min_z + max_z) * 0.5
        path = QPainterPath()
        for index, (x_value, z_value) in enumerate(points):
            screen_x, screen_y = lathe_view_point(x_value - center_x, z_value - center_z)
            point = QPointF(screen_x * scale, screen_y * scale)
            path.moveTo(point) if index == 0 else path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)
        trace_x, trace_y = lathe_view_point(-center_x, -center_z)
        trace_point = QPointF(trace_x * scale, trace_y * scale)
        self._paint_trace_point(painter, trace_point)

    @staticmethod
    def _paint_trace_point(painter: QPainter, point: QPointF) -> None:
        """Mark the programmed tracing point independently from tool geometry."""
        painter.save()
        painter.setBrush(QColor("#e02020"))
        painter.setPen(QPen(QColor("#9d0000"), 1.5))
        painter.drawEllipse(point, 4.5, 4.5)
        painter.drawLine(QPointF(point.x() - 9.0, point.y()), QPointF(point.x() + 9.0, point.y()))
        painter.drawLine(QPointF(point.x(), point.y() - 9.0), QPointF(point.x(), point.y() + 9.0))
        painter.restore()


class ToolLibraryPreviewPane(QWidget):
    """Scrollable preview viewport with explicit zoom controls."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.preview = ToolLibraryPreview(kind, self)
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidget(self.preview)
        self.scrollArea.setWidgetResizable(False)
        self.scrollArea.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scrollArea.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scrollArea.setStyleSheet("QScrollArea, QScrollArea > QWidget { background: #f7f8fa; }")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(QLabel("Red cross: trace point", self))
        controls.addStretch()
        for text, callback in (
            ("−", lambda: self.preview.set_zoom(self.preview.zoom - 0.25)),
            ("Fit", self.fit_preview),
            ("+", lambda: self.preview.set_zoom(self.preview.zoom + 0.25)),
        ):
            button = QToolButton(self)
            button.setText(text)
            button.setToolTip({"−": "Zoom out", "Fit": "Fit preview", "+": "Zoom in"}[text])
            button.clicked.connect(callback)
            controls.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scrollArea)
        layout.addLayout(controls)

    def fit_preview(self):
        viewport = self.scrollArea.viewport().size()
        zoom = min(viewport.width(), viewport.height()) / 240.0
        self.preview.set_zoom(min(1.0, max(0.5, zoom)))
