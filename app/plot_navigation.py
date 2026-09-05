"""Mouse navigation and picking helpers for the OpenGL plot."""

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer


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
                handled = True
        elif event_type == QEvent.Type.MouseButtonRelease:
            if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
                self._drag_pos = None
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
                if self.view.opts["rotationMethod"] == "euler":
                    self.view.orbit(-diff.x(), diff.y())
                else:
                    self.view.pan(diff.x(), diff.y(), 0, relative="view")
                    QTimer.singleShot(0, self.on_view_changed)
                handled = True
        elif event_type == QEvent.Type.Wheel:
            QTimer.singleShot(0, self.on_view_changed)
        elif event_type == QEvent.Type.Resize:
            QTimer.singleShot(0, self.on_view_changed)

        return handled
