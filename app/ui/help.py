"""Built-in Markdown help window."""

from __future__ import annotations

from PyQt6.QtCore import QFile, QIODevice, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QDialog

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app.ui.generated.help import Ui_HelpDialog


class HelpDialog(QDialog):
    """Display the packaged FAQ without requiring a browser or network access."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_HelpDialog()
        self.ui.setupUi(self)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.browser = self.ui.browser
        self.browser.setMarkdown(self._read_faq())
        self.ui.buttonBox.rejected.connect(self.close)

    @staticmethod
    def _read_faq() -> str:
        resource = QFile(":/resource/FAQ.md")
        if not resource.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            return "# FAQ\n\nThe packaged help resource could not be opened."
        try:
            return bytes(resource.readAll()).decode("utf-8")
        finally:
            resource.close()

    def showEvent(self, event):
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)
        super().showEvent(event)
