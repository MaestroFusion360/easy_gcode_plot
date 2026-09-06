"""Custom widgets referenced by Qt Designer forms."""

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt
from pyqtgraph.opengl import GLViewWidget


class Editor(QsciScintilla):
    """QScintilla editor used by the main window Designer form."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(False)


class PlotView(GLViewWidget):
    """OpenGL plot widget retaining the existing mouse interaction fallback."""

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
