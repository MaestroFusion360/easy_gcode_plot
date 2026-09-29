"""Built-in Markdown help window."""

from __future__ import annotations

import logging
import re

from PyQt6.QtCore import QCoreApplication, QFile, QIODevice, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPalette,
    QShortcut,
    QSyntaxHighlighter,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app import i18n
from app.settings import ui_language
from app.ui.generated.dialogs.help import Ui_HelpDialog

_SLUG_PUNCTUATION = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_WHITESPACE = re.compile(r"\s")
LOGGER = logging.getLogger(__name__)
_EXTERNAL_SCHEMES = frozenset({"http", "https", "mailto"})
_DEFAULT_FAQ_RESOURCE = ":/resource/FAQ.md"
_LOCALIZED_FAQ_RESOURCES = {"ru": ":/resource/FAQ_RU.md"}


def heading_anchor(text: str) -> str:
    """Reproduce the GitHub-style slug used by the FAQ table of contents.

    GitHub replaces every space with a hyphen after dropping punctuation, so
    runs of spaces around removed characters become consecutive hyphens.
    """
    return _SLUG_WHITESPACE.sub("-", _SLUG_PUNCTUATION.sub("", text.lower()))


def _read_resource(path: str, fallback: str) -> str:
    resource = QFile(path)
    if not resource.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        return fallback
    try:
        return bytes(resource.readAll()).decode("utf-8")
    finally:
        resource.close()


class MarkdownSyntaxHighlighter(QSyntaxHighlighter):
    """Lightweight syntax highlighting for fenced Markdown code blocks."""

    _STRINGS = re.compile(r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""")
    _NUMBERS = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])")

    _POWERSHELL_KEYWORDS = re.compile(
        r"\b(?:if|else|elseif|foreach|for|while|switch|function|param|return|break|continue|"
        r"try|catch|finally|throw|class|enum|filter|begin|process|end)\b",
        re.IGNORECASE,
    )
    _POWERSHELL_COMMANDS = re.compile(
        r"\b(?:Get|Set|New|Remove|Add|Clear|Copy|Move|Rename|Start|Stop|Test|Write|Read|"
        r"Select|Where|ForEach|Sort|Measure|Import|Export|Invoke|ConvertTo|ConvertFrom)-"
        r"[A-Za-z][A-Za-z0-9-]*\b"
    )
    _POWERSHELL_VARIABLES = re.compile(r"\$(?:\{[^}]+\}|[A-Za-z_?^][\w:?^.-]*)")

    _SHELL_KEYWORDS = re.compile(
        r"\b(?:if|then|else|elif|fi|for|while|until|do|done|case|esac|in|function|select|time)\b"
    )
    _SHELL_VARIABLES = re.compile(r"\$(?:\{[^}]+\}|[A-Za-z_][A-Za-z0-9_]*|[?#@*!$0-9-])")

    _PYTHON_KEYWORDS = re.compile(
        r"\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|"
        r"finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|"
        r"return|True|try|while|with|yield)\b"
    )

    _GCODE_WORDS = re.compile(
        r"(?<!\w)(?:[GMTFSHDPQRIJKXYZABC]-?\d+(?:\.\d*)?)(?!\w)",
        re.IGNORECASE,
    )
    _MACRO_VARIABLES = re.compile(r"#(?:\d+|\[[^\]]+\])")

    def __init__(self, document, browser: QTextBrowser, *, dark: bool):
        super().__init__(document)
        self._browser = browser
        self._dark = dark

    @staticmethod
    def _format(color: QColor, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if bold:
            fmt.setFontWeight(QFont.Weight.DemiBold)
        fmt.setFontItalic(italic)
        return fmt

    def _colors(self) -> dict[str, QTextCharFormat]:
        if self._dark:
            return {
                "keyword": self._format(QColor("#82aaff"), bold=True),
                "command": self._format(QColor("#c3e88d"), bold=True),
                "variable": self._format(QColor("#c792ea")),
                "string": self._format(QColor("#ecc48d")),
                "number": self._format(QColor("#f78c6c")),
                "comment": self._format(QColor("#8b949e"), italic=True),
                "gcode": self._format(QColor("#89ddff"), bold=True),
                "macro": self._format(QColor("#ff5370"), bold=True),
            }
        return {
            "keyword": self._format(QColor("#005cc5"), bold=True),
            "command": self._format(QColor("#22863a"), bold=True),
            "variable": self._format(QColor("#6f42c1")),
            "string": self._format(QColor("#9a6700")),
            "number": self._format(QColor("#d73a49")),
            "comment": self._format(QColor("#6a737d"), italic=True),
            "gcode": self._format(QColor("#174ea6"), bold=True),
            "macro": self._format(QColor("#b31d28"), bold=True),
        }

    def _is_code_block(self) -> bool:
        block_format = self.currentBlock().blockFormat()
        return block_format.hasProperty(QTextFormat.Property.BlockCodeFence) or block_format.hasProperty(
            QTextFormat.Property.BlockCodeLanguage
        )

    def _language(self) -> str:
        value = self.currentBlock().blockFormat().property(QTextFormat.Property.BlockCodeLanguage)
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore").strip().lower()
        return str(value).strip().lower()

    def _apply(self, pattern: re.Pattern[str], text: str, fmt: QTextCharFormat) -> None:
        for match in pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), fmt)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API name.
        if not self._is_code_block():
            return

        colors = self._colors()
        language = self._language()

        self._apply(self._STRINGS, text, colors["string"])
        self._apply(self._NUMBERS, text, colors["number"])

        if language in {"powershell", "ps1", "pwsh"}:
            self._apply(self._POWERSHELL_KEYWORDS, text, colors["keyword"])
            self._apply(self._POWERSHELL_COMMANDS, text, colors["command"])
            self._apply(self._POWERSHELL_VARIABLES, text, colors["variable"])
            self._highlight_comment(text, "#", colors["comment"])
            return

        if language in {"bash", "sh", "shell", "zsh"}:
            self._apply(self._SHELL_KEYWORDS, text, colors["keyword"])
            self._apply(self._SHELL_VARIABLES, text, colors["variable"])
            self._highlight_comment(text, "#", colors["comment"])
            return

        if language in {"python", "py"}:
            self._apply(self._PYTHON_KEYWORDS, text, colors["keyword"])
            self._highlight_comment(text, "#", colors["comment"])
            return

        if language in {"gcode", "nc", "fanuc", "macro-b", "macrob"}:
            self._apply(self._GCODE_WORDS, text, colors["gcode"])
            self._apply(self._MACRO_VARIABLES, text, colors["macro"])
            self._highlight_comment(text, ";", colors["comment"])

    def _highlight_comment(self, text: str, marker: str, fmt: QTextCharFormat) -> None:
        index = text.find(marker)
        if index >= 0:
            self.setFormat(index, len(text) - index, fmt)


def _style_heading(block: QTextBlock, *, dark: bool) -> None:
    block_format = block.blockFormat()
    level = block_format.headingLevel()
    if level == 1:
        top, bottom, size = 30.0, 16.0, 18.0
    elif level == 2:
        top, bottom, size = 26.0, 13.0, 15.0
    else:
        top, bottom, size = 20.0, 10.0, 12.5
    block_format.setTopMargin(top)
    block_format.setBottomMargin(bottom)
    QTextCursor(block).setBlockFormat(block_format)

    cursor = QTextCursor(block)
    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#f3f6f9" if level == 1 else "#b8d9ef") if dark else QColor("#1d4667"))
    fmt.setFontWeight(QFont.Weight.Bold)
    fmt.setFontPointSize(size)
    cursor.mergeCharFormat(fmt)


def _style_code_block(block: QTextBlock, *, dark: bool, font: QFont) -> None:
    block_format = block.blockFormat()
    block_format.setBackground(QColor("#3a424c" if dark else "#edf1f5"))
    block_format.setLeftMargin(18.0)
    block_format.setRightMargin(18.0)
    block_format.setTopMargin(0.0)
    block_format.setBottomMargin(0.0)
    QTextCursor(block).setBlockFormat(block_format)

    cursor = QTextCursor(block)
    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
    fmt = QTextCharFormat()
    fmt.setFont(font)
    fmt.setForeground(QColor("#f3f6f9" if dark else "#202830"))
    cursor.mergeCharFormat(fmt)


def _style_markdown_browser(browser: QTextBrowser, *, dark: bool) -> None:
    """Apply readable typography and stronger visual hierarchy."""
    document = browser.document()
    document.setDocumentMargin(24.0)
    base_font = browser.font()
    base_font.setPointSizeF(max(base_font.pointSizeF(), 11.5))
    document.setDefaultFont(base_font)
    code_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    code_font.setPointSizeF(max(code_font.pointSizeF(), 10.8))

    block = document.begin()
    first_block = True
    while block.isValid():
        block_format = block.blockFormat()
        is_code = block_format.hasProperty(QTextFormat.Property.BlockCodeFence) or block_format.hasProperty(
            QTextFormat.Property.BlockCodeLanguage
        )
        if block_format.headingLevel() > 0:
            _style_heading(block, dark=dark)
        elif is_code:
            _style_code_block(block, dark=dark, font=code_font)
        else:
            if block.text().strip():
                block_format.setTopMargin(2.0)
                block_format.setBottomMargin(6.0 if block.textList() is not None else 11.0)
                QTextCursor(block).setBlockFormat(block_format)
        if first_block:
            first_format = block.blockFormat()
            first_format.setTopMargin(0.0)
            QTextCursor(block).setBlockFormat(first_format)
            first_block = False
        block = block.next()


def _set_markdown_link_palette(browser: QTextBrowser, *, dark: bool) -> None:
    """Give the dark FAQ explicit colors across native Qt theme variants."""
    palette = browser.palette()
    if dark:
        palette.setColor(QPalette.ColorRole.Base, QColor("#252526"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#e6e6e6"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#9cc9ee" if dark else "#245a86"))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#b8a6df" if dark else "#654a83"))
    browser.setPalette(palette)


def _recolor_dark_links(browser: QTextBrowser) -> None:
    """Override Qt's hard-coded Markdown link blue without changing the text."""
    document = browser.document()
    ranges: list[tuple[int, int]] = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.charFormat().isAnchor():
                ranges.append((fragment.position(), fragment.length()))
            iterator += 1
        block = block.next()

    color = QTextCharFormat()
    color.setForeground(QColor("#9cc9ee"))
    for position, length in reversed(ranges):
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(color)


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
        self.resize(820, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.browser = QTextBrowser(self)
        dark = getattr(parent, "_theme_name", "light") == "dark"
        _set_markdown_link_palette(self.browser, dark=dark)
        self.browser.setMarkdown(
            _read_resource(":/resource/LICENSE.md", "# License\n\nThe packaged license could not be opened.")
        )
        _style_markdown_browser(self.browser, dark=dark)
        if dark:
            _recolor_dark_links(self.browser)
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
        self.resize(980, 760)
        self.browser = self.ui.browser
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(QCoreApplication.translate("HelpDialog", "Find in FAQ"))
        self.search_edit.setClearButtonEnabled(True)
        search_row.addWidget(self.search_edit)
        self.search_previous_button = QPushButton(self)
        self.search_previous_button.setIcon(QIcon(":/resource/icons/up.png"))
        self.search_previous_button.setIconSize(QSize(18, 18))
        self.search_previous_button.setToolTip(QCoreApplication.translate("HelpDialog", "Previous match"))
        self.search_previous_button.setAccessibleName(QCoreApplication.translate("HelpDialog", "Previous match"))
        self.search_next_button = QPushButton(self)
        self.search_next_button.setIcon(QIcon(":/resource/icons/down.png"))
        self.search_next_button.setIconSize(QSize(18, 18))
        self.search_next_button.setToolTip(QCoreApplication.translate("HelpDialog", "Next match"))
        self.search_next_button.setAccessibleName(QCoreApplication.translate("HelpDialog", "Next match"))
        search_row.addWidget(self.search_previous_button)
        search_row.addWidget(self.search_next_button)
        self.search_count = QLabel(self)
        search_row.addWidget(self.search_count)
        self.ui.verticalLayout.insertLayout(1, search_row)
        self._search_matches: list[QTextCursor] = []
        self._search_index = -1
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._run_pending_search)
        self.search_edit.textChanged.connect(self._queue_search)
        self.search_edit.returnPressed.connect(self.search_next)
        self.search_previous_button.clicked.connect(self.search_previous)
        self.search_next_button.clicked.connect(self.search_next)
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self.search_edit.setFocus)
        self.license_dialog: LicenseDialog | None = None
        self.syntax_highlighter: MarkdownSyntaxHighlighter | None = None
        self._theme_name = ""
        self.apply_theme(getattr(parent, "uiTheme", "light"))

        # setMarkdown renders the TOC links but registers no heading anchors, so
        # resolve "#slug" fragments against the document headings ourselves.
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.open_link)

    def apply_theme(self, theme_name: str) -> None:
        """Rebuild the FAQ colors when the application theme changes."""
        selected = "dark" if theme_name == "dark" else "light"
        if selected == self._theme_name:
            return
        self._theme_name = selected
        dark = selected == "dark"
        if self.syntax_highlighter is not None:
            self.syntax_highlighter.setDocument(None)
        _set_markdown_link_palette(self.browser, dark=dark)
        self.browser.setMarkdown(self._read_faq())
        _style_markdown_browser(self.browser, dark=dark)
        if dark:
            _recolor_dark_links(self.browser)
        self.syntax_highlighter = MarkdownSyntaxHighlighter(self.browser.document(), self.browser, dark=dark)
        if hasattr(self, "search_edit"):
            self._search_timer.stop()
            self._search_text_changed(self.search_edit.text())

    def _queue_search(self, query: str) -> None:
        if not query:
            self._search_timer.stop()
            self._search_text_changed("")
        else:
            self._search_timer.start()

    def _run_pending_search(self) -> None:
        self._search_timer.stop()
        self._search_text_changed(self.search_edit.text())

    def _search_text_changed(self, query: str) -> None:
        self._search_matches = []
        self._search_index = -1
        if query:
            document = self.browser.document()
            position = 0
            while True:
                match = document.find(query, position)
                if match.isNull():
                    break
                self._search_matches.append(match)
                position = match.selectionEnd()
            if self._search_matches:
                self._show_search_match(0)
                return
            self.search_count.setText("0 / 0")
        else:
            self.search_count.clear()
        cursor = self.browser.textCursor()
        cursor.clearSelection()
        self.browser.setTextCursor(cursor)

    def _show_search_match(self, index: int) -> None:
        self._search_index = index % len(self._search_matches)
        self.browser.setTextCursor(self._search_matches[self._search_index])
        self.browser.ensureCursorVisible()
        self.search_count.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def search_next(self) -> None:
        if self._search_timer.isActive():
            self._run_pending_search()
            return
        if self._search_matches:
            self._show_search_match(self._search_index + 1)
        else:
            self.search_edit.setFocus()

    def search_previous(self) -> None:
        if self._search_timer.isActive():
            self._run_pending_search()
            return
        if self._search_matches:
            self._show_search_match(self._search_index - 1)
        else:
            self.search_edit.setFocus()

    @staticmethod
    def _read_faq() -> str:
        language = i18n.normalize_language(ui_language())
        resource = _LOCALIZED_FAQ_RESOURCES.get(language, _DEFAULT_FAQ_RESOURCE)
        markdown = _read_resource(resource, "# FAQ\n\nThe packaged help resource could not be opened.")
        # Qt's Markdown parser treats <details> as an HTML block and does not
        # parse the nested Markdown TOC correctly. Keep the source file's
        # collapsible GitHub view, but show a normal Markdown heading in Qt.
        markdown = re.sub(
            r"<details>\s*<summary><h2>(.*?)</h2></summary>",
            r"## \1",
            markdown,
            count=1,
        )
        return markdown.replace("</details>", "", 1)

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
