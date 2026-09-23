"""Read-only token and diagnostic view for the current editor document."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMenu, QMessageBox

from app import theme
from app.gcode.core import format_gcode_number
from app.gcode.kernel.api_types import ExecutionResult
from app.gcode.kernel.lang import try_literal_int
from app.ui.generated.dialogs.tokens import Ui_TokensDlg

TABLE_HEADINGS = (
    "Ln",
    "Raw",
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
    "Support",
    "Action",
    "Valid",
)
TABLE_WIDTHS = (42, 240, 250, 38, 50, 50, 48, 82, 78, 72, 92, 92, 72, 78, 140, 120, 260, 58)
VARIABLE_HEADINGS = ("#", "Value")
_STATUS_COLORS = {
    "light": {
        "OK": QColor("#e7f6e7"),
        "WARNING": QColor("#ffe6e6"),
        "ERROR": QColor("#ffe6e6"),
    },
    "dark": {
        "OK": QColor("#23331f"),
        "WARNING": QColor("#3a2323"),
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
    "mode": {28, 30, 53, 54, 55, 56, 57, 58, 59, 90, 91, 92, 94, 95, 98, 99, 190, 191},
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
            " ".join(f"{word.letter}:{word.expr}" for word in words),
            "/" if block and block.optional_skip else "",
            _code_text(words, "N"),
            _code_text(words, "O"),
            _code_text(words, "M"),
            grouped["motion"],
            grouped["plane"],
            grouped["units"],
            grouped["correction"],
            grouped["cycle"],
            grouped["mode"],
            grouped["spindle"],
            flow,
            support,
            message,
            "Yes" if status == "OK" else "No",
        )
        rows.append(TokenRow(values, status))
    return rows


def _variable_name(key: str) -> str:
    name = str(key)
    if name.startswith("#"):
        return name
    return f"#{name}" if name.isdigit() else f"#<{name}>"


def _variable_sort_key(item: tuple[str, float]) -> tuple[int, int | str]:
    key = str(item[0])
    plain = key[1:] if key.startswith("#") else key
    if plain.isdigit():
        return 0, int(plain)
    if plain.startswith("<") and plain.endswith(">"):
        plain = plain[1:-1]
    return 1, plain.casefold()


def variables_for_playback(
    execution_result: ExecutionResult | None,
    playback_movements,
    playback_value: int,
    at_program_end: bool = False,
) -> tuple[tuple[str, float], ...]:
    """Return the captured Macro B state for one logical playback position."""
    if execution_result is None or playback_value <= 0:
        return ()
    steps = execution_result.execution_steps
    if not steps:
        return ()
    if at_program_end:
        return tuple(sorted(steps[-1].variables, key=_variable_sort_key))
    movements = tuple(playback_movements)
    if not movements:
        return ()
    playback_index = min(int(playback_value), len(movements)) - 1
    target_motion = movements[playback_index].motion_end - 1
    emitted_end = 0
    for step in steps:
        emitted_end += step.emitted_count
        if step.emitted_count and target_motion < emitted_end:
            return tuple(sorted(step.variables, key=_variable_sort_key))
    return ()


def _translated_variable_headings() -> tuple[str, str]:
    return (
        QCoreApplication.translate("TokensDlg", "#"),
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
        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.ui.tokenTable)
        self._copy_shortcut.activated.connect(self.copy_selected_rows)
        self.ui.tabWidget.currentChanged.connect(self._tab_changed)
        self.reset_columns()
        self._update_footer_state()

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
        if self._stale_provider():
            self.ui.macroVariablesStatusLabel.setText(
                QCoreApplication.translate(
                    "TokensDlg", "Execution is stale. Update the toolpath to inspect Macro Variables."
                )
            )
            return
        result = self._execution_provider()
        if result is None:
            self.ui.macroVariablesStatusLabel.setText(QCoreApplication.translate("TokensDlg", "No execution data."))
            return
        movements, playback_value = self._playback_provider()
        variables = variables_for_playback(
            result,
            movements,
            playback_value,
            self._program_end_provider(),
        )
        self.ui.macroVariablesStatusLabel.clear()
        for key, value in variables:
            name_item = QStandardItem(_variable_name(key))
            value_item = QStandardItem(format_gcode_number(value))
            name_item.setEditable(False)
            value_item.setEditable(False)
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.variables_model.appendRow((name_item, value_item))

    def refresh(self):
        source = self._source_provider()
        rows = rows_from_execution(source, self._analysis_provider())
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

    def selected_rows_text(self) -> str:
        rows = sorted({index.row() for index in self.ui.tokenTable.selectionModel().selectedRows()})
        return "\n".join(
            "\t".join(self.model.item(row, column).text() for column in range(self.model.columnCount())) for row in rows
        )

    def copy_selected_rows(self):
        text = self.selected_rows_text()
        if text:
            QApplication.clipboard().setText(text)

    def _show_context_menu(self, position):
        menu = QMenu(self)
        copy_action = QAction(QCoreApplication.translate("TokensDlg", "Copy"), menu)
        copy_action.setEnabled(bool(self.ui.tokenTable.selectionModel().selectedRows()))
        copy_action.triggered.connect(self.copy_selected_rows)
        menu.addAction(copy_action)
        menu.exec(self.ui.tokenTable.viewport().mapToGlobal(position))

    def export_csv(self):
        variables_tab = self.ui.tabWidget.currentWidget() is self.ui.macroVariablesTab
        model = self.variables_model if variables_tab else self.model
        headings = VARIABLE_HEADINGS if variables_tab else TABLE_HEADINGS
        default_name = "macro-variables.csv" if variables_tab else "tokens-validation.csv"
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
                QCoreApplication.translate("TokensDlg", "Macro variables exported to {0}")
                if variables_tab
                else QCoreApplication.translate("TokensDlg", "Token validation exported to {0}")
            )
            parent.statusBar().showMessage(message.format(filename), 5000)

    def reset_columns(self):
        for column, width in enumerate(TABLE_WIDTHS):
            self.ui.tokenTable.setColumnWidth(column, width)
        self.ui.tokenTable.horizontalScrollBar().setValue(0)
        self.ui.tokenTable.verticalScrollBar().setValue(0)
