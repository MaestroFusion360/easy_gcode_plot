"""Scrollable toolpath-statistics dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QIcon, QTextCursor
from PyQt6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QPlainTextEdit, QVBoxLayout

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app.gcode.trace_tools import format_trace_statistics


class StatisticsDialog(QDialog):
    """Reusable window for reports that are too large for a message box."""

    _REPORT_HEADING = "Toolpath Statistics"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statisticsDialog")
        self.setWindowTitle(self._REPORT_HEADING)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.resize(680, 620)
        self.setMinimumSize(480, 320)

        self.inchesCheck = QCheckBox("Inches", self)
        self.inchesCheck.setObjectName("statisticsInchesCheck")
        self.inchesCheck.setToolTip("Display all lengths and speeds in inches")
        self.inchesCheck.toggled.connect(self._refresh_statistics_report)
        self._statistics = None

        self.reportText = QPlainTextEdit(self)
        self.reportText.setObjectName("statisticsReportText")
        self.reportText.setReadOnly(True)
        self.reportText.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.reportText.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.reportText.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.reportText.customContextMenuRequested.connect(self._show_report_context_menu)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.reportText)
        controls = QHBoxLayout()
        controls.addWidget(self.inchesCheck)
        controls.addStretch()
        controls.addWidget(self.buttons)
        layout.addLayout(controls)

    def show_report(self, report: str) -> None:
        """Replace the report, reset scrolling and bring the dialog forward."""
        self._statistics = None
        self.inchesCheck.setEnabled(False)
        self._set_report_text(report)
        self._show_dialog()

    def show_statistics(self, statistics: dict[str, object]) -> None:
        """Display statistics and allow live metric/imperial conversion."""
        self._statistics = statistics
        self.inchesCheck.setEnabled(True)
        self._refresh_statistics_report()
        self._show_dialog()

    def _refresh_statistics_report(self) -> None:
        if self._statistics is None:
            return
        self._set_report_text(format_trace_statistics(self._statistics, inches=self.inchesCheck.isChecked()))

    def _set_report_text(self, report: str) -> None:
        heading = f"{self._REPORT_HEADING}\n"
        body = report[len(heading) :] if report.startswith(heading) else report
        self.reportText.setPlainText(body)
        self.reportText.moveCursor(QTextCursor.MoveOperation.Start)
        self.reportText.horizontalScrollBar().setValue(0)

    def _show_dialog(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def create_report_context_menu(self):
        """Create the native text menu with application Copy/Select All icons."""
        menu = self.reportText.createStandardContextMenu()
        icons = {
            "Copy": QIcon(":/resource/icons/copy.png"),
            "Select All": QIcon(":/resource/icons/select-all.png"),
        }
        for action in menu.actions():
            label = action.text().split("\t", 1)[0].replace("&", "")
            icon = icons.get(label)
            if icon is not None:
                action.setIcon(icon)
        return menu

    def _show_report_context_menu(self, position) -> None:
        menu = self.create_report_context_menu()
        menu.exec(self.reportText.mapToGlobal(position))
        menu.deleteLater()
