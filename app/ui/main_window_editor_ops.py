"""Editor-facing helpers for the main window."""

import logging
import re

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QLabel, QMenu, QMessageBox, QProgressBar

LOGGER = logging.getLogger(__name__)


class MainWindowEditorMixin:
    def updateStatusBar(self):
        """Update source position without reading the complete document."""
        line, index = self.ui.editor.getCursorPosition()
        self.sourceStatusLabel.setText("Ln {} / {} | Col {}".format(line + 1, self.ui.editor.lines(), index + 1))

    def changeFileType(self, idx):
        """Switch editor highlighting for the selected file type."""
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
        self.syncGuiCapabilities()
        LOGGER.debug("editor lexer changed index=%d", idx)

    def createLabelStatBar(self):
        """Create persistent execution state fields and transient progress."""
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setMaximum(100)
        self.progressBar.setTextVisible(False)
        self.progressBar.hide()
        self.executionStatusLabel = QLabel("READY")
        self.modeStatusLabel = QLabel("LATHE" if self.latheMode else "MILLING")
        self.unitsStatusLabel = QLabel(getattr(self, "defaultUnits", "mm"))
        self.sourceStatusLabel = QLabel()
        self.traceStatusLabel = QLabel("Steps: 0 | Motions: 0")
        self.diagnosticsStatusLabel = QLabel("\u2713")
        self.timeStatusLabel = QLabel("Exec: --")
        for widget in (
            self.executionStatusLabel,
            self.modeStatusLabel,
            self.unitsStatusLabel,
            self.sourceStatusLabel,
            self.traceStatusLabel,
            self.diagnosticsStatusLabel,
            self.timeStatusLabel,
        ):
            self.ui.statusbar.addPermanentWidget(widget)
        self.ui.statusbar.addPermanentWidget(self.progressBar)

        self.updateStatusBar()

    def updateExecutionStatus(self, state=None, result=None, elapsed_ms=None):
        """Reflect already-resolved kernel state without running analysis."""
        if not hasattr(self, "executionStatusLabel"):
            return
        result = result if result is not None else getattr(self, "execution_result", None)
        if state is None:
            if getattr(self, "_plot_source_stale", False) and result is not None:
                state = "STALE"
            elif result is None:
                state = "READY"
            elif not result.ok or not getattr(result, "complete", result.ok):
                state = "ERROR"
            elif any(getattr(item, "severity", "error").lower() == "warning" for item in result.diagnostics):
                state = "WARNING"
            else:
                state = "OK"
        self.executionStatusLabel.setText(state)
        self.modeStatusLabel.setText("LATHE" if self.latheMode else "MILLING")
        steps = () if result is None else getattr(result, "execution_steps", ())
        motions = () if result is None else result.motions
        self.traceStatusLabel.setText(f"Steps: {len(steps)} | Motions: {len(motions)}")
        errors = sum(
            getattr(d, "severity", "error").lower() == "error" for d in (() if result is None else result.diagnostics)
        )
        warnings = sum(
            getattr(d, "severity", "error").lower() == "warning" for d in (() if result is None else result.diagnostics)
        )
        parts = ([f"E: {errors}"] if errors else []) + ([f"W: {warnings}"] if warnings else [])
        self.diagnosticsStatusLabel.setText(" / ".join(parts) or "\u2713")
        if result is not None and steps:
            self.unitsStatusLabel.setText("inch" if float(steps[-1].unit_scale) == 25.4 else "mm")
        else:
            self.unitsStatusLabel.setText(getattr(self, "defaultUnits", "mm"))
        if elapsed_ms is not None:
            self.timeStatusLabel.setText(f"Exec: {elapsed_ms:.1f} ms")

    def updatePlaybackStatus(self, value):
        """Expose the already-available playback motion position."""
        if not hasattr(self, "traceStatusLabel"):
            return
        maximum = self.ui.horizontalSlider.maximum()
        if self.ui.actionPlay.isChecked() and maximum:
            self.traceStatusLabel.setText(f"Motion {value} / {maximum}")
        else:
            self.updateExecutionStatus()

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
        if not findText:
            return False
        cursor = doc.getCursorPosition()
        selection = doc.getSelection()
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
                if doc.findFirst(findText, *state):
                    return True
                self._restore_editor_state(cursor, selection)
                QMessageBox.information(self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText)
            else:
                self._restore_editor_state(cursor, selection)
                QMessageBox.information(self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText)
            return False
        return True

    def replace(self, findText, replaceText, checkCase, checkWholeWord, wrapAround):
        """Replace the current match and continue searching."""
        doc = self.ui.editor
        if not findText:
            return
        selected = doc.selectedText()
        matches = selected == findText if checkCase else selected.casefold() == findText.casefold()
        if matches:
            doc.replace(replaceText)
        self.find(findText, checkCase, checkWholeWord, wrapAround)

    def replaceAll(self, findText, replaceText, checkCase, checkWholeWord):
        """Replace every occurrence of the search term in the editor."""
        doc = self.ui.editor
        if not findText:
            return 0
        cursor = doc.getCursorPosition()
        selection = doc.getSelection()
        state = (False, checkCase, checkWholeWord, False, True)
        count = 0
        doc.beginUndoAction()
        try:
            doc.setCursorPosition(0, 0)
            while doc.findFirst(findText, *state):
                doc.replace(replaceText)
                count += 1
        finally:
            doc.endUndoAction()
            self._restore_editor_state(cursor, selection)
        return count

    def _clamped_position(self, line, index):
        doc = self.ui.editor
        last_line = max(0, doc.lines() - 1)
        line = max(0, min(int(line), last_line))
        length = max(0, doc.lineLength(line))
        return line, max(0, min(int(index), length))

    def _restore_editor_state(self, cursor, selection):
        """Restore a caret or selection after an editor operation."""
        doc = self.ui.editor
        if selection[0] >= 0:
            start = self._clamped_position(selection[0], selection[1])
            end = self._clamped_position(selection[2], selection[3])
            doc.setSelection(start[0], start[1], end[0], end[1])
        else:
            line, index = self._clamped_position(*cursor)
            doc.setCursorPosition(line, index)

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
