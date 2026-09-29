"""Mouse navigation and picking helpers for the OpenGL plot."""

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QVector4D


def point_segment_distance(px, py, ax, ay, bx, by):
    """Return the 2D distance from a point to a line segment."""
    dx = bx - ax
    dy = by - ay
    if dx == 0.0 and dy == 0.0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    qx = ax + t * dx
    qy = ay + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


class PlotNavigation(QObject):
    """CAD-like viewport navigation matching the CNCEditor OpenTK controls."""

    def __init__(self, view, on_view_changed=None, on_pick=None):
        super().__init__(view)
        self.view = view
        self.on_view_changed = on_view_changed or (lambda: None)
        self.on_pick = on_pick or (lambda _pos: None)
        self._drag_pos = None
        self._orbit_pivot = None

    def _pivot_at(self, position):
        """Intersect the cursor ray with the view plane through the current center."""
        view = self.view
        center = view.opts["center"]
        pixel = view.pixelSize(center)
        camera_to_world = view.viewMatrix().inverted()[0]
        right = camera_to_world * QVector4D(1, 0, 0, 0)
        up = camera_to_world * QVector4D(0, 1, 0, 0)
        dx = (position.x() - view.width() / 2.0) * pixel
        dy = (view.height() / 2.0 - position.y()) * pixel
        return center + right.toVector3D() * dx + up.toVector3D() * dy

    def _orbit_at_pivot(self, dx, dy):
        view = self.view
        pivot = self._orbit_pivot
        before = view.viewMatrix() * QVector4D(pivot, 1)
        view.orbit(-dx, dy)
        after_matrix = view.viewMatrix()
        after = after_matrix * QVector4D(pivot, 1)
        delta = QVector4D(after.x() - before.x(), after.y() - before.y(), after.z() - before.z(), 0)
        view.opts["center"] += (after_matrix.inverted()[0] * delta).toVector3D()
        view.update()

    def eventFilter(self, watched, event):
        if watched is not self.view:
            return False

        handled = False
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._drag_pos = None
                self.on_pick(event.position())
                handled = True
            elif event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
                self._drag_pos = event.position()
                self._orbit_pivot = (
                    self._pivot_at(self._drag_pos) if event.button() == Qt.MouseButton.MiddleButton else None
                )
                handled = True
        elif event_type == QEvent.Type.MouseButtonRelease:
            if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
                self._drag_pos = None
                self._orbit_pivot = None
                handled = True
        elif event_type == QEvent.Type.MouseMove and self._drag_pos is not None:
            pos = event.position()
            diff = pos - self._drag_pos
            self._drag_pos = pos

            if event.buttons() & Qt.MouseButton.LeftButton:
                self.view.pan(diff.x(), diff.y(), 0, relative="view")
                QTimer.singleShot(0, self.on_view_changed)
                handled = True
            elif event.buttons() & Qt.MouseButton.MiddleButton:
                self._orbit_at_pivot(diff.x(), diff.y())
                QTimer.singleShot(0, self.on_view_changed)
                handled = True
        elif event_type == QEvent.Type.Wheel:
            QTimer.singleShot(0, self.on_view_changed)
        elif event_type == QEvent.Type.Resize:
            QTimer.singleShot(0, self.on_view_changed)

        return handled
