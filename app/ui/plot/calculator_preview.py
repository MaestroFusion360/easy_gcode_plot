"""Lightweight 2D previews for the G-code calculator dialogs."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

Point = tuple[float, float]


class CalculatorPreview(QWidget):
    """Paint simple XY boundaries, paths and points without an OpenGL context."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._boundary: tuple[Point, ...] = ()
        self._paths: tuple[tuple[Point, ...], ...] = ()
        self._points: tuple[Point, ...] = ()
        self.setMinimumSize(240, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

    def set_geometry(
        self,
        *,
        boundary: Sequence[Point] = (),
        paths: Iterable[Sequence[Point]] = (),
        points: Sequence[Point] = (),
    ) -> None:
        self._boundary = tuple(boundary)
        self._paths = tuple(tuple(path) for path in paths)
        self._points = tuple(points)
        self.update()

    def clear(self) -> None:
        self.set_geometry()

    @property
    def points(self) -> tuple[Point, ...]:
        """Return the currently displayed point markers."""
        return self._points

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Window))

        all_points = [*self._boundary, *self._points]
        for path in self._paths:
            all_points.extend(path)
        if not all_points:
            return

        mapper = self._mapper(all_points)
        boundary_pen = QPen(self.palette().color(QPalette.ColorRole.Mid), 1.0)
        path_pen = QPen(self.palette().color(QPalette.ColorRole.Highlight), 1.6)
        point_pen = QPen(self.palette().color(QPalette.ColorRole.Highlight), 1.2)

        if len(self._boundary) > 1:
            painter.setPen(boundary_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._path(self._boundary, mapper))

        painter.setPen(path_pen)
        for path in self._paths:
            if len(path) > 1:
                painter.drawPath(self._path(path, mapper))

        if self._points:
            painter.setPen(point_pen)
            painter.setBrush(self.palette().brush(QPalette.ColorRole.Highlight))
            for point in self._points:
                mapped = mapper(point)
                painter.drawEllipse(mapped, 3.5, 3.5)

    def _mapper(self, points: Sequence[Point]):
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        scale = min(max(1.0, self.width() - 28) / span_x, max(1.0, self.height() - 28) / span_y)
        center_x = (min_x + max_x) * 0.5
        center_y = (min_y + max_y) * 0.5

        def map_point(point: Point) -> QPointF:
            return QPointF(
                self.width() * 0.5 + (point[0] - center_x) * scale,
                self.height() * 0.5 - (point[1] - center_y) * scale,
            )

        return map_point

    @staticmethod
    def _path(points: Sequence[Point], mapper) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(mapper(points[0]))
        for point in points[1:]:
            path.lineTo(mapper(point))
        return path
