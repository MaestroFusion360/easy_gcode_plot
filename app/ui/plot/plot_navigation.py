"""Mouse navigation and picking helpers for the OpenGL plot."""

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt, QTimer
from PyQt6.QtGui import QContextMenuEvent, QVector4D
from PyQt6.QtWidgets import QApplication


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


@dataclass
class _MouseGesture:
    origin: QPointF
    last: QPointF
    button: Qt.MouseButton
    pan_button: Qt.MouseButton
    pick: bool = False
    menu: bool = False
    dragged: bool = False


class PlotNavigation(QObject):
    """CAD-like viewport navigation matching the CNCEditor OpenTK controls."""

    def __init__(self, view, on_view_changed=None, on_pick=None, *, cimco_like=None):
        super().__init__(view)
        self.view = view
        self.on_view_changed = on_view_changed or (lambda: None)
        self.on_pick = on_pick or (lambda _pos: None)
        self._orbit_pivot = None
        self.measure = None
        self.cimco_like = cimco_like or (lambda: False)
        self._gesture = None

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

    def _mouse_press(self, event):
        button = event.button()
        cimco = self.cimco_like()
        pan_button = Qt.MouseButton.RightButton if cimco else Qt.MouseButton.LeftButton
        picking_allowed = self.measure is None or not self.measure.active
        if (
            picking_allowed
            and button == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._gesture = None
            self.on_pick(event.position())
            return True
        pick = cimco and picking_allowed and button == Qt.MouseButton.LeftButton
        if button not in (pan_button, Qt.MouseButton.MiddleButton) and not pick:
            return False
        self._gesture = _MouseGesture(
            event.position(), event.position(), button, pan_button, pick, cimco and button == Qt.MouseButton.RightButton
        )
        self._orbit_pivot = self._pivot_at(event.position()) if button == Qt.MouseButton.MiddleButton else None
        return True

    def _mouse_release(self, event):
        gesture = self._gesture
        if gesture is None or event.button() != gesture.button:
            return False
        moved = (event.position() - gesture.origin).manhattanLength() >= QApplication.startDragDistance()
        click = not gesture.dragged and not moved
        self._gesture = self._orbit_pivot = None
        if gesture.pick and click:
            self.on_pick(event.position())
        if gesture.menu and click:
            self.view.customContextMenuRequested.emit(event.position().toPoint())
        return True

    def _mouse_move(self, event):
        gesture = self._gesture
        if gesture is None:
            return False
        if not event.buttons() & gesture.button:
            self._gesture = self._orbit_pivot = None
            return False
        pos = event.position()
        if not gesture.dragged and (gesture.menu or gesture.pick):
            if (pos - gesture.origin).manhattanLength() < QApplication.startDragDistance():
                return True
            gesture.dragged = True
        diff = pos - gesture.last
        gesture.last = pos
        if gesture.pick:
            return True
        if gesture.button == gesture.pan_button:
            self.view.pan(diff.x(), diff.y(), 0, relative="view")
        elif gesture.button == Qt.MouseButton.MiddleButton:
            self._orbit_at_pivot(diff.x(), diff.y())
        QTimer.singleShot(0, self.on_view_changed)
        return True

    def eventFilter(self, watched, event):
        if watched is not self.view:
            return False
        event_type = event.type()
        if event_type in (QEvent.Type.FocusOut, QEvent.Type.Hide):
            self._gesture = self._orbit_pivot = None
        if self.measure is not None and self.measure.handle_event(event):
            self._gesture = self._orbit_pivot = None
            return True
        if event_type == QEvent.Type.ContextMenu and self.cimco_like():
            return event.reason() == QContextMenuEvent.Reason.Mouse
        handlers = {
            QEvent.Type.MouseButtonPress: self._mouse_press,
            QEvent.Type.MouseButtonRelease: self._mouse_release,
            QEvent.Type.MouseMove: self._mouse_move,
        }
        if event_type in handlers:
            return handlers[event_type](event)
        if event_type in (QEvent.Type.Wheel, QEvent.Type.Resize):
            QTimer.singleShot(0, self.on_view_changed)
        return False
