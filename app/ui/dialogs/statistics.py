"""Scrollable toolpath-statistics dialog."""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QFontDatabase, QIcon, QTextCursor
from PyQt6.QtWidgets import QDialog

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app.gcode.trace_tools import format_trace_statistics
from app.ui.generated.dialogs.statistics import Ui_StatisticsDialog


class StatisticsDialog(QDialog):
    """Reusable window for reports that are too large for a message box."""

    _REPORT_HEADING = "Toolpath Statistics"

    @staticmethod
    def _report_labels() -> dict[str, str]:
        translate = QCoreApplication.translate
        return {
            "heading": translate("StatisticsReport", "Toolpath Statistics"),
            "execution": translate("StatisticsReport", "Execution"),
            "complete": translate("StatisticsReport", "complete"),
            "partial": translate("StatisticsReport", "PARTIAL / INVALID"),
            "motions": translate("StatisticsReport", "Motions"),
            "executed_steps": translate("StatisticsReport", "executed steps"),
            "rapid_motions": translate("StatisticsReport", "Rapid motions"),
            "arc_motions": translate("StatisticsReport", "arc motions"),
            "cycle_motions": translate("StatisticsReport", "cycle motions"),
            "estimated_time": translate("StatisticsReport", "Estimated motion time"),
            "length": translate("StatisticsReport", "Length"),
            "rapid_length": translate("StatisticsReport", "Rapid length"),
            "feed_length": translate("StatisticsReport", "Feed length"),
            "rapid_time": translate("StatisticsReport", "Rapid time"),
            "feed_time": translate("StatisticsReport", "Feed time"),
            "known_time": translate("StatisticsReport", "Known motion time"),
            "average_feed": translate("StatisticsReport", "Average feed"),
            "unknown": translate("StatisticsReport", "UNKNOWN"),
            "unknown_time_motions": translate("StatisticsReport", "Motions with unknown time"),
            "rapid_speed": translate("StatisticsReport", "Assumed rapid speed"),
            "estimate_note": translate(
                "StatisticsReport", "Kinematic estimate only; excludes dwell, tool changes and acceleration."
            ),
            "bounds": translate("StatisticsReport", "Bounds in programmed coordinates"),
            "tool": translate("StatisticsReport", "Tool"),
        }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_StatisticsDialog()
        self.ui.setupUi(self)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.inchesCheck = self.ui.inchesCheck
        self.reportText = self.ui.reportText
        self.buttons = self.ui.buttonBox
        self.inchesCheck.toggled.connect(self._refresh_statistics_report)
        self._statistics = None
        self.reportText.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.reportText.customContextMenuRequested.connect(self._show_report_context_menu)
        self.buttons.rejected.connect(self.close)

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
        self._set_report_text(
            format_trace_statistics(
                self._statistics,
                inches=self.inchesCheck.isChecked(),
                labels=self._report_labels(),
            )
        )

    def _set_report_text(self, report: str) -> None:
        headings = (self._REPORT_HEADING, self._report_labels()["heading"])
        body = next((report[len(value) + 1 :] for value in headings if report.startswith(f"{value}\n")), report)
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
