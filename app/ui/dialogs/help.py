"""Built-in Markdown help window."""

from __future__ import annotations

import re

from PyQt6.QtCore import QFile, QIODevice, Qt, QUrl
from PyQt6.QtGui import QTextBlock, QTextCursor
from PyQt6.QtWidgets import QDialog

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app.ui.generated.dialogs.help import Ui_HelpDialog

_SLUG_PUNCTUATION = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_WHITESPACE = re.compile(r"\s+")


def heading_anchor(text: str) -> str:
    """Reproduce the GitHub-style slug used by the FAQ table of contents."""
    return _SLUG_WHITESPACE.sub("-", _SLUG_PUNCTUATION.sub("", text.lower()).strip())


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
        # setMarkdown renders the TOC links but registers no heading anchors, so
        # resolve "#slug" fragments against the document headings ourselves.
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.navigate_to_anchor)
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

    def navigate_to_anchor(self, url: QUrl) -> None:
        anchor = url.fragment()
        block = self._heading_block(anchor) if anchor else None
        if block is None:
            return
        self.browser.setTextCursor(QTextCursor(block))
        self.browser.ensureCursorVisible()

    def _heading_block(self, anchor: str) -> QTextBlock | None:
        block = self.browser.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel() > 0 and heading_anchor(block.text()) == anchor:
                return block
            block = block.next()
        return None

    def showEvent(self, event):
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)
        super().showEvent(event)
