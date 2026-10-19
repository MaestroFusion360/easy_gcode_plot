"""Read-only token and diagnostic view for the current editor document."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from app import theme
from app.gcode.core import format_gcode_number
from app.gcode.kernel.api.types import ExecutionResult
from app.gcode.kernel.frontend.heidenhain_syntax import HeidenhainSyntax
from app.gcode.kernel.frontend.lang import try_literal_int
from app.ui.generated.dialogs.tokens import Ui_TokensDlg
from app.ui.support.execution_variables import (
    step_for_playback,
    variables_for_playback,
    variables_for_step,
)
from app.ui.support.execution_variables import (
    variable_name as _variable_name,
)

__all__ = [
    "TABLE_HEADINGS",
    "TABLE_WIDTHS",
    "TokenRow",
    "TokensDialog",
    "rows_from_execution",
    "variables_for_playback",
]

TABLE_HEADINGS = (
    "Ln",
    "Raw",
    "Support",
    "Action",
    "Valid",
    "Words",
    "Opt",
    "N",
    "O",
    "M",
    "Motion G",
    "Plane G",
    "Units G",
    "Correction G",
    "Cycle G",
    "Mode G",
    "Spindle G",
    "Flow",
)
TABLE_WIDTHS = (42, 240, 90, 260, 58, 250, 38, 50, 50, 48, 82, 78, 72, 92, 92, 72, 78, 140)
VARIABLE_HEADINGS = ("Variable", "Value")
_STATUS_COLORS = {
    "light": {
        "OK": QColor("#e7f6e7"),
        "WARNING": QColor("#fff0d9"),
        "ERROR": QColor("#ffe6e6"),
    },
    "dark": {
        "OK": QColor("#23331f"),
        "WARNING": QColor("#4a321c"),
        "ERROR": QColor("#3a2323"),
    },
}
_STATUS_FOREGROUND = {"light": QColor("#111111"), "dark": QColor("#e6e6e6")}

_EXPLICIT_SOURCE_LINE_RE = re.compile(r"\bat\s+line\s+(\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TokenRow:
    values: tuple[str, ...]
    status: str

    def as_values(self) -> tuple[str, ...]:
        return self.values


_G_GROUPS = {
    "motion": {0, 1, 2, 3, 32, 33},
    "plane": {17, 18, 19},
    "units": {20, 21},
    "correction": {40, 41, 42},
    "cycle": {70, 71, 72, 73, 74, 75, 76, 80, 81, 82, 83, 84, 85, 86},
    "mode": {28, 30, 53, 54, 55, 56, 57, 58, 59, 90, 91, 92, 94, 95, 98, 99},
    "spindle": {50, 96, 97},
}


def _code_text(words, letter: str) -> str:
    return ",".join(word.expr for word in words if word.letter == letter)


def _diagnostic_source_line(diagnostic: object, line_count: int) -> int | None:
    """Prefer an explicit source-line suffix over nested parser exception line numbers."""
    message = str(getattr(diagnostic, "message", ""))
    explicit_lines = _EXPLICIT_SOURCE_LINE_RE.findall(message)
    if explicit_lines:
        line = int(explicit_lines[-1])
        if 1 <= line <= line_count:
            return line

    line = getattr(diagnostic, "line", None)
    if isinstance(line, int) and 1 <= line <= line_count:
        return line
    return None


def _native_word_text(block):
    if block is None:
        return ""
    syntax = block.native_syntax
    if isinstance(syntax, HeidenhainSyntax):
        words = " ".join(word.source for word in syntax.words)
        if syntax.assignment is not None:
            name, expression = syntax.assignment
            words = f"{name}={expression.source}"
        return " ".join(part for part in (syntax.command, words) if part)
    if syntax is not None:
        if syntax.parameter_assignment is not None:
            number, expression = syntax.parameter_assignment
            return f"R{number}={expression}"
        if syntax.named_assignments:
            return " ".join(f"{name}={expression}" for name, expression in syntax.named_assignments)
        if syntax.real_declarations:
            return "DEF REAL " + ", ".join(syntax.real_declarations)
    return " ".join(f"{word.letter}:{word.expr}" for word in block.parsed_words)


def _block_machine_codes(block):
    if block is None:
        return ""
    if isinstance(block.native_syntax, HeidenhainSyntax):
        return ",".join(function.code.source for function in block.native_syntax.machine_functions)
    return _code_text(block.parsed_words, "M")


def rows_from_execution(source: str, result: ExecutionResult) -> list[TokenRow]:
    """Adapt the kernel's parsed blocks and diagnostics without parsing source again."""
    lines = source.splitlines()
    blocks = result.program.blocks if result.program is not None else ()
    diagnostics_by_line: dict[int, list[object]] = {}
    global_diagnostics = []
    for diagnostic in result.diagnostics:
        line = _diagnostic_source_line(diagnostic, len(lines))
        if line is None:
            global_diagnostics.append(diagnostic)
        else:
            diagnostics_by_line.setdefault(line, []).append(diagnostic)

    rows = []
    for index, line in enumerate(lines, start=1):
        block = blocks[index - 1] if index <= len(blocks) else None
        words = block.parsed_words if block else ()
        diagnostics = diagnostics_by_line.get(index, [])
        if index == 1:
            diagnostics = [*global_diagnostics, *diagnostics]
        status = (
            "ERROR" if any(item.severity == "error" for item in diagnostics) else "WARNING" if diagnostics else "OK"
        )
        message = "; ".join(f"{item.code}: {item.message}" for item in diagnostics)
        g_codes = [
            (code, word.expr)
            for word in words
            if word.letter == "G" and (code := try_literal_int(word.expr)) is not None
        ]
        grouped = {
            name: ",".join(f"G{raw}" for code, raw in g_codes if code in codes) for name, codes in _G_GROUPS.items()
        }
        diagnostic_statuses = {item.status for item in diagnostics}
        support = (
            "UNSUPPORTED"
            if "unsupported" in diagnostic_statuses
            else "UNVERIFIED"
            if "unverified" in diagnostic_statuses
            else "OK"
        )
        flow = block.flow_node.kind if block and block.flow_node else ""
        values = (
            str(index),
            line,
            support,
            message,
            "Yes" if status == "OK" else "No",
            _native_word_text(block),
            "/" if block and block.optional_skip else "",
            str(block.nlabel) if block is not None and block.nlabel is not None else "",
            _code_text(words, "O"),
            _block_machine_codes(block),
            grouped["motion"],
            grouped["plane"],
            grouped["units"],
            grouped["correction"],
            grouped["cycle"],
            grouped["mode"],
            grouped["spindle"],
            flow,
        )
        rows.append(TokenRow(values, status))
    return rows


def _translated_variable_headings() -> tuple[str, str]:
    return (
        QCoreApplication.translate("TokensDlg", "Variable"),
        QCoreApplication.translate("TokensDlg", "Value"),
    )


class TokensDialog(QDialog):
    """Display parser tokens and execution diagnostics for the live editor text."""

    def __init__(
        self,
        parent,
        source_provider: Callable[[], str] | None = None,
        analysis_provider: Callable[[], ExecutionResult] | None = None,
        *,
        execution_provider: Callable[[], ExecutionResult | None] | None = None,
        playback_provider: Callable[[], tuple[object, int]] | None = None,
        stale_provider: Callable[[], bool] | None = None,
        program_end_provider: Callable[[], bool] | None = None,
    ):
        super().__init__(parent)
        self.ui = Ui_TokensDlg()
        self.ui.setupUi(self)
        self._source_provider = source_provider or (lambda: parent.ui.editor.text())
        self._analysis_provider = analysis_provider or parent.analyzeEditorSource
        self._execution_provider = execution_provider or (lambda: getattr(parent, "execution_result", None))
        self._playback_provider = playback_provider or (
            lambda: (getattr(parent, "_playback_movements", ()), parent.ui.horizontalSlider.value())
        )
        self._stale_provider = stale_provider or (lambda: bool(getattr(parent, "_plot_source_stale", False)))
        self._program_end_provider = program_end_provider or (
            lambda: bool(getattr(parent, "_playback_at_program_end", False))
        )
        self.model = QStandardItemModel(0, len(TABLE_HEADINGS), self)
        self.model.setHorizontalHeaderLabels(TABLE_HEADINGS)
        self.ui.tokenTable.setModel(self.model)
        self._token_rows: list[TokenRow] = []
        self._searchable_rows: list[str] = []
        self._displayed_source: str | None = None
        for index, status in enumerate(("ALL", "WARNING", "ERROR")):
            self.ui.filterCombo.setItemData(index, status)
        self.ui.filterCombo.currentIndexChanged.connect(self._apply_filters)
        self.ui.searchEdit.textChanged.connect(self._apply_filters)
        self.variables_model = QStandardItemModel(0, len(VARIABLE_HEADINGS), self)
        self.variables_model.setHorizontalHeaderLabels(_translated_variable_headings())
        self.ui.macroVariablesTable.setModel(self.variables_model)
        self.ui.macroVariablesTable.verticalHeader().setVisible(False)
        self.ui.macroVariablesTable.horizontalHeader().setStretchLastSection(True)
        self.ui.macroVariablesTable.setColumnWidth(0, 180)
        self.ui.tokenTable.verticalHeader().setVisible(False)
        self.ui.tokenTable.verticalHeader().setMinimumSectionSize(18)
        self.ui.tokenTable.verticalHeader().setDefaultSectionSize(22)
        self.ui.refreshButton.clicked.connect(self._refresh_current_tab)
        self.ui.exportCsvButton.clicked.connect(self.export_csv)
        self.ui.resetColumnsButton.clicked.connect(self.reset_columns)
        self.ui.tokenTable.customContextMenuRequested.connect(self._show_context_menu)
        self.ui.tokenTable.doubleClicked.connect(self._show_row_diagnostics)
        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.ui.tokenTable)
        self._copy_shortcut.activated.connect(self.copy_selected_rows)
        self.ui.tabWidget.currentChanged.connect(self._tab_changed)
        self.reset_columns()
        self._update_footer_state()
        self._apply_filters()

    def showEvent(self, event):
        self._refresh_current_tab()
        super().showEvent(event)

    def _tab_changed(self, _index):
        self._update_footer_state()
        if self.isVisible():
            self._refresh_current_tab()

    def _update_footer_state(self):
        self.ui.resetColumnsButton.setEnabled(self.ui.tabWidget.currentWidget() is self.ui.tokensTab)

    def playback_position_changed(self, _value):
        self.refresh_macro_variables_if_visible()

    def refresh_macro_variables_if_visible(self):
        if self.isVisible() and self.ui.tabWidget.currentWidget() is self.ui.macroVariablesTab:
            self.refresh_macro_variables()

    def _refresh_current_tab(self):
        if self.ui.tabWidget.currentWidget() is self.ui.macroVariablesTab:
            self.refresh_macro_variables()
        else:
            self.refresh()

    def refresh_macro_variables(self):
        """Refresh the read-only inspector from existing execution snapshots."""
        self.variables_model.removeRows(0, self.variables_model.rowCount())
        self.ui.variablesContextLabel.clear()
        self._set_row_count(0, 0)
        if self._stale_provider():
            self.ui.macroVariablesStatusLabel.setText(
                QCoreApplication.translate("TokensDlg", "Execution is stale. Update the toolpath to inspect Variables.")
            )
            return
        result = self._execution_provider()
        if result is None:
            self.ui.macroVariablesStatusLabel.setText(QCoreApplication.translate("TokensDlg", "No execution data."))
            return
        movements, playback_value = self._playback_provider()
        step = step_for_playback(result, movements, playback_value, self._program_end_provider())
        variables = variables_for_step(step, result.source_dialect)
        self._update_variable_context(result, step)
        self.ui.macroVariablesStatusLabel.setText(
            "" if variables else QCoreApplication.translate("TokensDlg", "No variables recorded at this position.")
        )
        for key, value in variables:
            name_item = QStandardItem(_variable_name(key, result.source_dialect))
            text = (
                format_gcode_number(value)
                if value is not None
                else QCoreApplication.translate("TokensDlg", "Undefined")
            )
            value_item = QStandardItem(text)
            name_item.setEditable(False)
            value_item.setEditable(False)
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.variables_model.appendRow((name_item, value_item))
        self._set_row_count(len(variables), len(variables))

    def _update_variable_context(self, result, step):
        dialect = {"heidenhain": "HEIDENHAIN iTNC 530", "sinumerik": "SINUMERIK"}.get(result.source_dialect)
        if dialect is None:
            dialect = (
                QCoreApplication.translate("TokensDlg", "FANUC Lathe")
                if result.language == "fanuc_turn"
                else QCoreApplication.translate("TokensDlg", "FANUC Mill")
            )
        context = dialect
        if step is not None:
            context = QCoreApplication.translate("TokensDlg", "{0} — Line {1} — Occurrence {2}").format(
                dialect, step.source_block + 1, step.occurrence + 1
            )
        self.ui.variablesContextLabel.setText(context)

    def refresh(self):
        source = self._source_provider()
        result = None if self._stale_provider() else self._execution_provider()
        if result is not None and result.program is not None:
            if [block.raw.rstrip("\r\n") for block in result.program.blocks] != source.splitlines():
                result = None
        if result is None and not getattr(self.parent(), "_kernel_execution_active", False):
            result = self._analysis_provider()
        if result is None and source == self._displayed_source:
            return  # The editor may already be calculating; keep its current table usable.
        rows = rows_from_execution(source, result) if result is not None else []
        self.model.removeRows(0, self.model.rowCount())
        theme_name = theme.normalize_theme(getattr(self.parent(), "uiTheme", "light"))
        status_colors = _STATUS_COLORS[theme_name]
        foreground = _STATUS_FOREGROUND[theme_name]
        for row in rows:
            items = [QStandardItem(value) for value in row.as_values()]
            color = status_colors[row.status]
            for item in items:
                item.setEditable(False)
                item.setBackground(color)
                item.setForeground(foreground)
            self.model.appendRow(items)
        self._token_rows = rows
        self._displayed_source = source
        self._searchable_rows = [" ".join(" ".join(row.values).split()).casefold() for row in rows]
        self._apply_filters()

    def _apply_filters(self, _value=None):
        """Filter existing rows only; never invoke the source or analysis providers."""
        status = self.ui.filterCombo.currentData()
        query = " ".join(self.ui.searchEdit.text().split()).casefold()
        table = self.ui.tokenTable
        visible_count = 0
        table.setUpdatesEnabled(False)
        try:
            for index, row in enumerate(self._token_rows):
                visible = (status == "ALL" or row.status == status) and query in self._searchable_rows[index]
                hidden = not visible
                if table.isRowHidden(index) != hidden:
                    table.setRowHidden(index, hidden)
                visible_count += visible
        finally:
            table.setUpdatesEnabled(True)
        if self.ui.tabWidget.currentWidget() is self.ui.tokensTab:
            self._set_row_count(visible_count, len(self._token_rows))

    def _set_row_count(self, visible_count, total_count):
        self.ui.filterCountLabel.setText(
            QCoreApplication.translate("TokensDlg", "Rows: {0} / {1}").format(visible_count, total_count)
        )

    def selected_rows_text(self) -> str:
        rows = sorted(
            {
                index.row()
                for index in self.ui.tokenTable.selectionModel().selectedRows()
                if not self.ui.tokenTable.isRowHidden(index.row())
            }
        )
        return "\n".join(
            "\t".join(self.model.item(row, column).text() for column in range(self.model.columnCount())) for row in rows
        )

    def copy_selected_rows(self):
        text = self.selected_rows_text()
        if text:
            QApplication.clipboard().setText(text)

    def _show_row_diagnostics(self, index):
        if not index.isValid():
            return
        row = index.row()
        message = self.model.item(row, TABLE_HEADINGS.index("Action")).text()
        if not message:
            return
        line = self.model.item(row, 0).text()
        source = self.model.item(row, 1).text()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self.windowTitle()} — {line}")
        dialog.resize(780, 360)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(dialog)
        text.setReadOnly(True)
        text.setPlainText(f"{line}: {source}\n\n{message}")
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _show_context_menu(self, position):
        menu = QMenu(self)
        copy_action = QAction(QCoreApplication.translate("TokensDlg", "Copy"), menu)
        copy_action.setEnabled(bool(self.ui.tokenTable.selectionModel().selectedRows()))
        copy_action.triggered.connect(self.copy_selected_rows)
        menu.addAction(copy_action)
        try:
            menu.exec(self.ui.tokenTable.viewport().mapToGlobal(position))
        finally:
            menu.deleteLater()

    def export_csv(self):
        variables_tab = self.ui.tabWidget.currentWidget() is self.ui.macroVariablesTab
        model = self.variables_model if variables_tab else self.model
        headings = VARIABLE_HEADINGS if variables_tab else TABLE_HEADINGS
        default_name = "variables.csv" if variables_tab else "tokens-validation.csv"
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            QCoreApplication.translate("TokensDlg", "Export CSV"),
            default_name,
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:
            return
        try:
            with Path(filename).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(headings)
                for row in range(model.rowCount()):
                    if not variables_tab and self.ui.tokenTable.isRowHidden(row):
                        continue
                    writer.writerow(model.item(row, column).text() for column in range(model.columnCount()))
        except OSError as exc:
            QMessageBox.critical(
                self,
                QCoreApplication.translate("TokensDlg", "Export CSV"),
                QCoreApplication.translate("TokensDlg", "Unable to write {0}:\n{1}").format(filename, exc),
            )
            return
        parent = self.parent()
        if parent is not None and hasattr(parent, "statusBar"):
            message = (
                QCoreApplication.translate("TokensDlg", "Variables exported to {0}")
                if variables_tab
                else QCoreApplication.translate("TokensDlg", "Token validation exported to {0}")
            )
            parent.statusBar().showMessage(message.format(filename), 5000)

    def reset_columns(self):
        for column, width in enumerate(TABLE_WIDTHS):
            self.ui.tokenTable.setColumnWidth(column, width)
        self.ui.tokenTable.horizontalScrollBar().setValue(0)
        self.ui.tokenTable.verticalScrollBar().setValue(0)
