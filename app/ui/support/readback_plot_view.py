"""Present an offscreen OpenGL viewport through a regular Qt raster widget."""

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication, QWidget


class ReadbackPlotView(QWidget):
    """Keep driver OpenGL composition out of the main window on Windows.

    The scene still renders with the hardware OpenGL context. Only presentation
    uses a framebuffer readback, avoiding native child-window stacking artifacts.
    """

    _FORWARDED_EVENTS = frozenset(
        (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        )
    )

    def __init__(self, renderer_type, parent=None):
        super().__init__(parent)
        # It must remain a separate top-level: a GL child would switch the main
        # window's backing store back to OpenGL composition.
        self._renderer = renderer_type()
        self._renderer.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self._renderer.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._renderer.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self._renderer.installEventFilter(self)
        self.destroyed.connect(self._renderer.deleteLater)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._renderer.resize(self.size())
        self._renderer.show()

    def __getattr__(self, name):
        renderer = self.__dict__.get("_renderer")
        if renderer is None:
            raise AttributeError(name)
        # Hidden widgets defer resizeEvent until they are shown. Camera fitting
        # and picking must already use the presentation widget's current size.
        if renderer.size() != self.size():
            renderer.resize(self.size())
        return getattr(renderer, name)

    def eventFilter(self, watched, event):
        renderer = self.__dict__.get("_renderer")
        if renderer is not None and watched is renderer and event.type() == QEvent.Type.UpdateRequest:
            self.update()
        return super().eventFilter(watched, event)

    def event(self, event):
        if event.type() in self._FORWARDED_EVENTS:
            QApplication.sendEvent(self._renderer, event)
            self.update()
            return True
        return super().event(event)

    def resizeEvent(self, event):
        self._renderer.resize(event.size())
        super().resizeEvent(event)

    def paintEvent(self, event):
        image = self._renderer.grabFramebuffer()
        painter = QPainter(self)
        painter.drawImage(self.rect(), image)
