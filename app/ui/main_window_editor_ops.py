"""Editor-facing helpers for the main window."""

import re
import time

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QLabel, QMenu, QMessageBox, QProgressBar


class MainWindowEditorMixin:
    def updateStatusBar(self):
        """Update status bar with text length and cursor position."""
        text = self.ui.editor.text()
        line, index = self.ui.editor.getCursorPosition()
        self.chrCountLabel.setText("Length: {}".format(len(text.replace("\n", "\r\n"))))
        self.cursorPosLabel.setText("Ln: {}/{}, Col:{}".format(line + 1, self.ui.editor.lines(), index + 1))

    def changeLang(self, idx):
        """Switch editor lexer and fonts based on language selection."""
        start = time.time()
        self.ui.editor.setLexer(None)
        self.ui.editor.setMarginsForegroundColor(QColor(self.marginColor))
        self.ui.editor.setMarginsFont(QFont(self.marginFontFamily, self.marginSizeTxt))
        if idx == 0:
            self.ui.editor.setFont(
                QFont(
                    self.fontFamily,
                    self.sizeTxt,
                    weight=self.fontWeight,
                    italic=self.fontItalic,
                )
            )
            self.ui.editor.SendScintilla(QsciScintilla.SCI_CLEARDOCUMENTSTYLE)
        else:
            self.lexer.setFont(
                QFont(
                    self.fontFamily,
                    self.sizeTxt,
                    weight=self.fontWeight,
                    italic=self.fontItalic,
                )
            )
            self.ui.editor.setLexer(self.lexer)
        end = time.time()
        print(f"Paint Execution time: {(end - start) * 1000:.3f} ms")

    def createLabelStatBar(self):
        """Create status bar widgets for cursor info, text length, and progress."""
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setMaximum(100)
        self.progressBar.setTextVisible(False)
        self.chrCountLabel = QLabel()
        self.chrCountLabel.setMinimumWidth(100)

        self.cursorPosLabel = QLabel()
        self.cursorPosLabel.setMinimumWidth(150)
        self.ui.statusbar.addPermanentWidget(self.chrCountLabel)
        self.ui.statusbar.addPermanentWidget(self.cursorPosLabel)
        self.ui.statusbar.addPermanentWidget(self.progressBar)

        self.updateStatusBar()

    def editorContextMenu(self, point):
        """Show context menu for editor editing actions."""
        menu = QMenu()
        menu.addAction(self.ui.actionUndo)
        menu.addAction(self.ui.actionRedo)
        menu.addSeparator()
        menu.addAction(self.ui.actionCut)
        menu.addAction(self.ui.actionCopy)
        menu.addAction(self.ui.actionPaste)
        menu.addAction(self.ui.actionSelectAll)
        menu.exec(self.ui.editor.mapToGlobal(point))

    def runFindDlg(self):
        """Show the find/replace dialog, seeding it with the current selection."""
        text = self.ui.editor.selectedText()
        if text:
            self.findDlg.ui.lineEditFind.setText(text)
        self.findDlg.show()

    def find(self, findText, checkCase, checkWholeWord, wrapAround):
        """Search within the editor using the provided options."""
        doc = self.ui.editor
        forward = True
        if forward:
            line, index = doc.getSelection()[2:]
        else:
            line, index = doc.getSelection()[:2]

        state = (
            False,
            checkCase,
            checkWholeWord,
            wrapAround,
            forward,
            line,
            index,
            True,
            False,
        )
        if not doc.findFirst(findText, *state):
            if wrapAround:
                doc.setCursorPosition(0, 0)
                if not doc.findFirst(findText, *state):
                    QMessageBox.information(self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText)
            else:
                QMessageBox.information(self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText)

    def replace(self, findText, replaceText, checkCase, checkWholeWord, wrapAround):
        """Replace the current match and continue searching."""
        doc = self.ui.editor
        if findText == doc.selectedText():
            doc.replace(replaceText)
        self.find(findText, checkCase, checkWholeWord, wrapAround)

    def replaceAll(self, findText, replaceText, checkCase, checkWholeWord):
        """Replace every occurrence of the search term in the editor."""
        doc = self.ui.editor
        state = (False, checkCase, checkWholeWord, False, True)
        doc.setCursorPosition(0, 0)
        while True:
            if not doc.findFirst(findText, *state):
                break
            doc.replace(replaceText)

    def _process_selected_lines(self, handler):
        """Apply a line transformer to selected text or the whole document."""
        if not self.ui.editor.text():
            return
        text = self.ui.editor.selectedText()
        if not text:
            self.ui.editor.selectAll()
            text = self.ui.editor.text()
        lines = text.splitlines(True)
        transformed = handler(lines)
        if transformed is not None:
            self.ui.editor.replaceSelectedText("".join(transformed))

    def renumber(self):
        """Add or update block numbers for the selected or full document."""
        st = self.seqNumStart
        incr = self.seqNumIncr
        delim = " " if self.seqNumSpacing else ""

        def handler(lines):
            nonlocal st
            lst = []
            for line in lines:
                skipline = "".join(re.findall(r"^[%O\r\n]", line))
                if skipline:
                    lst.append(line)
                    continue
                num = "".join(re.findall(r"^N\d+", line))
                if num:
                    new_line = "N{}".format(st) + delim + re.sub(r"^N\d+", "", line).lstrip()
                else:
                    new_line = "N{}".format(st) + delim + line.lstrip()
                lst.append(new_line)
                st = st + incr
            return lst

        self._process_selected_lines(handler)

    def numbRemove(self):
        """Remove block numbers from the selected or full document."""

        def handler(lines):
            lst = []
            for line in lines:
                num = "".join(re.findall(r"^N\d+", line))
                if num:
                    new_line = re.sub(r"^N\d+", "", line).lstrip()
                else:
                    new_line = line
                lst.append(new_line)
            return lst

        self._process_selected_lines(handler)

    def removeSpaces(self):
        """Strip spaces from code while preserving every parenthesized comment verbatim."""

        def handler(lines):
            transformed = []
            for line in lines:
                parts = re.split(r"(\([^()]*\))", line)
                transformed.append(
                    "".join(
                        part if part.startswith("(") and part.endswith(")") else part.replace(" ", "") for part in parts
                    )
                )
            return transformed

        self._process_selected_lines(handler)

    def removeLines(self):
        """Trim empty lines from the selection or whole document."""

        def handler(lines):
            lst = []
            for line in lines:
                emptyline = "".join(re.findall(r"^[\r\n]", line))
                if emptyline:
                    new_line = line.lstrip()
                else:
                    new_line = line
                lst.append(new_line)
            return lst

        self._process_selected_lines(handler)
