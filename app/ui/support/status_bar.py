"""Compact transient status messages with full details available on hover."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QStatusBar

MESSAGE_MAX_WIDTH = 420


class StatusBar(QStatusBar):
    """Bound message width without changing callers or restarting timeouts on resize."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_message = ""
        self._rendering_message = False
        self._permanent_widgets = []
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self.clearMessage)
        self.messageChanged.connect(self._native_message_changed)

    def _native_message_changed(self, message):
        # Qt's status-tip events bypass Python's show/clear overrides.
        if not self._rendering_message:
            self._message_timer.stop()
            self._full_message = message
            self.setToolTip(message)

    def addPermanentWidget(self, widget, stretch=0):
        self._permanent_widgets.append(widget)
        super().addPermanentWidget(widget, stretch)

    def showMessage(self, message, timeout=0):
        self._message_timer.stop()
        self._full_message = message
        self.setToolTip(message)
        self._render_message()
        if timeout > 0:
            self._message_timer.start(timeout)

    def clearMessage(self):
        self._message_timer.stop()
        self._full_message = ""
        self.setToolTip("")
        super().clearMessage()

    def _render_message(self):
        reserved = sum(widget.sizeHint().width() + 6 for widget in self._permanent_widgets if not widget.isHidden())
        bar_width = self.width() if self.isVisible() else max(self.width(), self.window().width())
        width = max(0, min(MESSAGE_MAX_WIDTH, bar_width - reserved - 24))
        text = " ".join(self._full_message.split())
        self._rendering_message = True
        try:
            super().showMessage(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
        finally:
            self._rendering_message = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._full_message:
            self._render_message()
