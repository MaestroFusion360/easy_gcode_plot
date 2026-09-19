"""Built-in Markdown help window."""

from __future__ import annotations

import logging
import re

from PyQt6.QtCore import QCoreApplication, QFile, QIODevice, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QTextBlock, QTextCursor, QTextFormat
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app.ui.generated.dialogs.help import Ui_HelpDialog

_SLUG_PUNCTUATION = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_WHITESPACE = re.compile(r"\s+")
LOGGER = logging.getLogger(__name__)
_EXTERNAL_SCHEMES = frozenset({"http", "https", "mailto"})


def heading_anchor(text: str) -> str:
    """Reproduce the GitHub-style slug used by the FAQ table of contents."""
    return _SLUG_WHITESPACE.sub("-", _SLUG_PUNCTUATION.sub("", text.lower()).strip())


def _read_resource(path: str, fallback: str) -> str:
    resource = QFile(path)
    if not resource.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        return fallback
    try:
        return bytes(resource.readAll()).decode("utf-8")
    finally:
        resource.close()


class LicenseDialog(QDialog):
    """Display the packaged license without relying on installation paths."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("HelpDialog", "MIT License"))
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser(self)
        self.browser.setMarkdown(
            _read_resource(":/resource/LICENSE.md", "# License\n\nThe packaged license could not be opened.")
        )
        self.browser.document().setDocumentMargin(14.0)
        layout.addWidget(self.browser)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.button_box.rejected.connect(self.close)
        layout.addWidget(self.button_box)


class HelpDialog(QDialog):
    """Display the packaged FAQ without requiring a browser or network access."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_HelpDialog()
        self.ui.setupUi(self)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(900, 700)
        self.browser = self.ui.browser
        self.license_dialog: LicenseDialog | None = None
        self.browser.setMarkdown(self._read_faq())
        self._format_document()
        # setMarkdown renders the TOC links but registers no heading anchors, so
        # resolve "#slug" fragments against the document headings ourselves.
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.open_link)
        self.ui.buttonBox.rejected.connect(self.close)

    def _format_document(self) -> None:
        document = self.browser.document()
        document.setDocumentMargin(14.0)
        block = document.begin()
        first_block = True
        while block.isValid():
            block_format = block.blockFormat()
            heading_level = block_format.headingLevel()
            if heading_level == 1:
                block_format.setTopMargin(24.0)
                block_format.setBottomMargin(14.0)
            elif heading_level == 2:
                block_format.setTopMargin(22.0)
                block_format.setBottomMargin(10.0)
            elif heading_level == 3:
                block_format.setTopMargin(16.0)
                block_format.setBottomMargin(8.0)
            elif block.text().strip() and block.textList() is None and not self._is_code_block(block_format):
                block_format.setBottomMargin(8.0)
            if first_block:
                block_format.setTopMargin(0.0)
                first_block = False
            QTextCursor(block).setBlockFormat(block_format)
            block = block.next()

    @staticmethod
    def _is_code_block(block_format) -> bool:
        return block_format.hasProperty(QTextFormat.Property.BlockCodeFence) or block_format.hasProperty(
            QTextFormat.Property.BlockCodeLanguage
        )

    @staticmethod
    def _read_faq() -> str:
        return _read_resource(":/resource/FAQ.md", "# FAQ\n\nThe packaged help resource could not be opened.")

    def open_link(self, url: QUrl) -> None:
        if url.fragment() and not url.path():
            self.navigate_to_anchor(url)
            return
        if url.scheme().lower() in _EXTERNAL_SCHEMES:
            QDesktopServices.openUrl(url)
            return
        if url.path().replace("\\", "/").rsplit("/", 1)[-1].casefold() == "license.md":
            if self.license_dialog is None:
                self.license_dialog = LicenseDialog(self)
                self.license_dialog.setWindowIcon(self.windowIcon())
            self.license_dialog.show()
            self.license_dialog.raise_()
            self.license_dialog.activateWindow()
            return
        LOGGER.warning("help_link_unhandled url=%s", url.toString())

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
