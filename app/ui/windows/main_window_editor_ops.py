"""Editor-facing helpers for the main window."""

import logging
import re

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QCoreApplication, QSignalBlocker
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QLabel, QMenu, QMessageBox

LOGGER = logging.getLogger(__name__)
_TOOLCHANGE_PATTERN = re.compile(r"T\s*\d+", re.IGNORECASE)


def _code_without_comments(line: str) -> str:
    """Mask comments while preserving character offsets for editor navigation."""
    chars = list(line)
    parentheses = 0
    for index, char in enumerate(line):
        if char == ";" and parentheses == 0:
            chars[index:] = " " * (len(chars) - index)
            break
        if char == "(":
            parentheses += 1
        if parentheses:
            chars[index] = " "
        if char == ")" and parentheses:
            parentheses -= 1
    return "".join(chars)


def _code_words_without_macro_expressions(line: str) -> str:
    """Mask bracketed Macro B expressions before scanning CNC address words."""
    chars = list(line)
    depth = 0
    for index, char in enumerate(line):
        if char == "[":
            depth += 1
        if depth:
            chars[index] = " "
        if char == "]" and depth:
            depth -= 1
    return "".join(chars)


class MainWindowEditorMixin:
    def updateStatusBar(self):
        """Update source position without reading the complete document."""
        line, index = self.ui.editor.getCursorPosition()
        self.sourceStatusLabel.setText("Ln {} / {} | Col {}".format(line + 1, self.ui.editor.lines(), index + 1))

    def changeFileType(self, idx):
        """Switch editor highlighting for the selected file type."""
        self.syncFileTypeMenu(idx)
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
        self.applyUiTheme()
        self.syncGuiCapabilities()
        LOGGER.debug("editor lexer changed index=%d", idx)

    def createLabelStatBar(self):
        """Create persistent execution state fields."""
        self.executionStatusLabel = QLabel("READY")
        self.modeStatusLabel = QLabel("LATHE" if self.latheMode else "MILLING")
        self.unitsStatusLabel = QLabel(getattr(self, "defaultUnits", "mm"))
        self.sourceStatusLabel = QLabel()
        self.traceStatusLabel = QLabel("Steps: 0 | Motions: 0")
        self.diagnosticsStatusLabel = QLabel("\u2713")
        self.timeStatusLabel = QLabel("Exec: --")
        status_widgets = (
            self.executionStatusLabel,
            self.modeStatusLabel,
            self.unitsStatusLabel,
            self.sourceStatusLabel,
            self.traceStatusLabel,
            self.diagnosticsStatusLabel,
            self.timeStatusLabel,
        )
        for widget in status_widgets:
            widget.setContentsMargins(7, 0, 7, 0)
            self.ui.statusbar.addPermanentWidget(widget)
        self.traceStatusLabel.setToolTip("Executed steps and generated motions")
        self.diagnosticsStatusLabel.setToolTip("No execution diagnostics")
        self.timeStatusLabel.setToolTip("CNC kernel execution time")
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

        def tr(value):
            return QCoreApplication.translate("MainWindow", value)

        state_labels = {
            "STALE": tr("STALE"),
            "READY": tr("READY"),
            "ERROR": tr("ERROR"),
            "WARNING": tr("WARNING"),
            "OK": tr("OK"),
            "UPDATING": tr("UPDATING"),
        }
        self.executionStatusLabel.setText(state_labels.get(state, state))
        self.modeStatusLabel.setText(tr("LATHE") if self.latheMode else tr("MILLING"))
        steps = () if result is None else getattr(result, "execution_steps", ())
        motions = () if result is None else result.motions
        self.traceStatusLabel.setText(
            tr("Steps: %1 | Motions: %2").replace("%1", str(len(steps))).replace("%2", str(len(motions)))
        )
        errors = sum(
            getattr(d, "severity", "error").lower() == "error" for d in (() if result is None else result.diagnostics)
        )
        warnings = sum(
            getattr(d, "severity", "error").lower() == "warning" for d in (() if result is None else result.diagnostics)
        )
        self.executionStatusLabel.setVisible(
            state in {"READY", "UPDATING", "STALE"} or (state == "ERROR" and not errors)
        )
        parts = ([tr("Errors: %1").replace("%1", str(errors))] if errors else []) + (
            [tr("Warnings: %1").replace("%1", str(warnings))] if warnings else []
        )
        self.diagnosticsStatusLabel.setText(" / ".join(parts) or "\u2713")
        diagnostics = () if result is None else result.diagnostics
        self.diagnosticsStatusLabel.setToolTip(
            "\n".join(
                f"{('Ln ' + str(item.line) + ': ') if item.line is not None else ''}{item.code}: {item.message}"
                for item in diagnostics
            )
            or "No execution diagnostics"
        )
        if result is not None and steps:
            self.unitsStatusLabel.setText("inch" if float(steps[-1].unit_scale) == 25.4 else "mm")
        else:
            self.unitsStatusLabel.setText(getattr(self, "defaultUnits", "mm"))
        if elapsed_ms is not None:
            elapsed_ms = float(elapsed_ms)
            self.timeStatusLabel.setText(
                f"Exec: {elapsed_ms / 1000.0:.2f} s" if elapsed_ms >= 1000.0 else f"Exec: {elapsed_ms:.1f} ms"
            )

    def updatePlaybackStatus(self, value):
        """Expose the already-available playback motion position."""
        if not hasattr(self, "traceStatusLabel"):
            return
        maximum = self.ui.horizontalSlider.maximum()
        if self.ui.actionPlay.isChecked() and maximum:
            self.traceStatusLabel.setText(
                QCoreApplication.translate("MainWindow", "Motion %1 / %2")
                .replace("%1", str(value))
                .replace("%2", str(maximum))
            )
        else:
            self.updateExecutionStatus()

    def editorContextMenu(self, point):
        """Show all Edit actions followed by all CNC Functions actions."""
        menu = QMenu(self)
        menu.addActions(self.ui.menu_Edit.actions())
        menu.addSeparator()
        menu.addActions(self.ui.menuCNC_Functions.actions())
        menu.exec(self.ui.editor.mapToGlobal(point))

    def previousToolchange(self):
        """Move the editor selection to the previous T word, wrapping at the start."""
        return self._navigate_toolchange(forward=False)

    def nextToolchange(self):
        """Move the editor selection to the next T word, wrapping at the end."""
        return self._navigate_toolchange(forward=True)

    def _navigate_toolchange(self, *, forward: bool) -> bool:
        editor = self.ui.editor
        matches = [
            (line_number, match.start(), match.end())
            for line_number in range(editor.lines())
            for match in _TOOLCHANGE_PATTERN.finditer(
                _code_words_without_macro_expressions(_code_without_comments(editor.text(line_number)))
            )
        ]
        if not matches:
            self.ui.statusbar.showMessage(QCoreApplication.translate("MainWindow", "No tool changes found"), 2500)
            return False

        selection = editor.getSelection()
        if selection[0] >= 0:
            origin = selection[2:4] if forward else selection[0:2]
        else:
            origin = editor.getCursorPosition()
        if forward:
            target = next((match for match in matches if match[:2] >= origin), matches[0])
        else:
            target = next((match for match in reversed(matches) if match[:2] < origin), matches[-1])
        line, start, end = target
        editor.setSelection(line, start, line, end)
        editor.ensureLineVisible(line)
        editor.setFocus()
        self._seek_playback_to_toolchange(line, forward=forward)
        return True

    def _seek_playback_to_toolchange(self, source_line: int, *, forward: bool) -> bool:
        """Move playback to the matching executed tool-change occurrence."""
        result = getattr(self, "execution_result", None)
        if result is None or not result.motions or getattr(self, "_plot_source_stale", False):
            return False
        movements = getattr(self, "_playback_movements", ())
        motion_to_playback = getattr(self, "_motion_to_playback", ())
        if not movements or not motion_to_playback:
            return False
        candidates = self._toolchange_playback_positions(result, motion_to_playback, source_line)
        if not candidates:
            return False
        slider = self.ui.horizontalSlider
        current = slider.value()
        if forward:
            target = next((value for value in candidates if value > current), candidates[0])
        else:
            target = next((value for value in reversed(candidates) if value < current), candidates[-1])
        if target == current:
            return True

        # This is the deliberate editor -> playback exception. Block the normal
        # slider callback so it cannot move the editor away from the selected T
        # word; still refresh the trace cursor and playback-dependent inspectors.
        with QSignalBlocker(slider):
            slider.setValue(target)
        self.valueHandler(target, sync_editor=False)
        if hasattr(self, "updatePlaybackStatus"):
            self.updatePlaybackStatus(target)
        if hasattr(self, "_macro_playback_position_changed"):
            self._macro_playback_position_changed(target)
        return True

    @staticmethod
    def _toolchange_playback_positions(result, motion_to_playback, source_line):
        """Map executed tool-change blocks to one-based playback slider positions."""
        candidates = []
        motion_cursor = 0
        for step in result.execution_steps:
            step_start = motion_cursor
            motion_cursor += step.emitted_count
            owns_toolchange = any(
                event.kind == "tool_change"
                and (event.source_block == source_line or event.related_block == source_line)
                for event in step.events
            )
            # Turning tool selections and milling T blocks can be represented by
            # executed words even when the controller emits no M06 event.
            owns_tool_word = step.source_block == source_line and any(address == "T" for address, _ in step.words)
            if not (owns_toolchange or owns_tool_word):
                continue
            motion_index = step_start if step.emitted_count else motion_cursor
            if motion_index >= len(result.motions):
                motion_index = len(result.motions) - 1
            if motion_index >= 0:
                candidates.append(motion_to_playback[motion_index] + 1)
        return candidates

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
                QMessageBox.information(
                    self,
                    QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                    QCoreApplication.translate("MainWindow", "Cannot find text:\n'%s'") % findText,
                )
            else:
                self._restore_editor_state(cursor, selection)
                QMessageBox.information(
                    self,
                    QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                    QCoreApplication.translate("MainWindow", "Cannot find text:\n'%s'") % findText,
                )
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

    def _change_selected_case(self, transform):
        """Convert the selection, or the entire document when none is selected."""
        editor = self.ui.editor
        had_selection = editor.hasSelectedText()
        cursor = editor.getCursorPosition()
        if not had_selection:
            if not editor.text():
                return
            editor.selectAll()
        selection = editor.getSelection()
        selected = editor.selectedText()
        changed = transform(selected)
        if changed != selected:
            editor.replaceSelectedText(changed)
            if had_selection:
                last_before = selected.splitlines()[-1] if selected.splitlines() else selected
                last_after = changed.splitlines()[-1] if changed.splitlines() else changed
                editor.setSelection(
                    selection[0], selection[1], selection[2], selection[3] + len(last_after) - len(last_before)
                )
            else:
                editor.setCursorPosition(*cursor)

    def uppercaseSelection(self):
        self._change_selected_case(str.upper)

    def lowercaseSelection(self):
        self._change_selected_case(str.lower)

    def addBlockSkip(self):
        """Insert one optional-block slash at column zero of selected blocks."""
        editor = self.ui.editor
        if not editor.hasSelectedText():
            return
        selection = editor.getSelection()
        first, last = selection[0], selection[2]
        if selection[3] == 0 and last > first:
            last -= 1
        changed_lines = set()
        editor.beginUndoAction()
        try:
            for line in range(first, last + 1):
                content = editor.text(line).rstrip("\r\n")
                if content.strip() and not content.startswith(("/", "%")):
                    editor.insertAt("/", line, 0)
                    changed_lines.add(line)
        finally:
            editor.endUndoAction()
        editor.setSelection(
            selection[0],
            selection[1] + (selection[0] in changed_lines),
            selection[2],
            selection[3] + (selection[2] in changed_lines and selection[3] > 0),
        )

    def removeBlockSkip(self):
        """Remove one leading optional-block slash from selected blocks."""
        editor = self.ui.editor
        if not editor.hasSelectedText():
            return
        selection = editor.getSelection()
        first, last = selection[0], selection[2]
        if selection[3] == 0 and last > first:
            last -= 1
        changed_lines = set()
        editor.beginUndoAction()
        try:
            for line in range(first, last + 1):
                if editor.text(line).startswith("/"):
                    editor.setSelection(line, 0, line, 1)
                    editor.removeSelectedText()
                    changed_lines.add(line)
        finally:
            editor.endUndoAction()
        editor.setSelection(
            selection[0],
            max(0, selection[1] - (selection[0] in changed_lines)),
            selection[2],
            max(0, selection[3] - (selection[2] in changed_lines)),
        )

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
