"""Built-in Markdown help window."""

from __future__ import annotations

from PyQt6.QtCore import QFile, QIODevice, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.


class HelpDialog(QDialog):
    """Display the packaged FAQ without requiring a browser or network access."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("helpDialog")
        self.setWindowTitle("Easy G-Code Plot — FAQ")
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.resize(820, 700)
        self.setMinimumSize(520, 360)

        self.browser = QTextBrowser(self)
        self.browser.setObjectName("helpBrowser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setMarkdown(self._read_faq())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        layout.addWidget(buttons)

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
