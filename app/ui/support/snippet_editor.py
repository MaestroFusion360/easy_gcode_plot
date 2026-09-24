"""Plain-text snippet editor with local text zoom shortcuts."""

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QPlainTextEdit


class ZoomableSnippetEditor(QPlainTextEdit):
    """Zoom snippet text without changing the application's editor font."""

    _MIN_POINT_SIZE = 6
    _MAX_POINT_SIZE = 24
    _DEFAULT_POINT_SIZE = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wheel_remainder = 0
        self.viewport().installEventFilter(self)

    def _set_point_size(self, size: int):
        font = self.font()
        font.setPointSize(max(self._MIN_POINT_SIZE, min(self._MAX_POINT_SIZE, size)))
        self.setFont(font)

    def eventFilter(self, watched, event):
        if (
            watched is self.viewport()
            and event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._wheel_remainder += event.angleDelta().y()
            steps = int(self._wheel_remainder / 120)
            self._wheel_remainder -= steps * 120
            if steps:
                self._set_point_size(self.font().pointSize() + steps)
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._set_point_size(self.font().pointSize() + 1)
                return
            if event.key() == Qt.Key.Key_Minus:
                self._set_point_size(self.font().pointSize() - 1)
                return
            if event.key() == Qt.Key.Key_0:
                self._set_point_size(self._DEFAULT_POINT_SIZE)
                return
        super().keyPressEvent(event)
