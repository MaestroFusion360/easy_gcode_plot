"""Scrollable toolpath-statistics dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette, QTextCursor
from PyQt6.QtWidgets import QComboBox, QDialog, QFileDialog, QMessageBox, QPushButton, QTextBrowser

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app.gcode.statistics_report import statistics_html, write_statistics_html
from app.ui.generated.dialogs.statistics import Ui_StatisticsDialog


class StatisticsBrowser(QTextBrowser):
    """Handle scrolling and scale the entire report consistently."""

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                self.parent().zoom_report(1 if delta > 0 else -1)
        else:
            scroll_bar = self.verticalScrollBar()
            delta = event.pixelDelta().y()
            if not delta:
                delta = round(event.angleDelta().y() / 120 * scroll_bar.singleStep() * 3)
            scroll_bar.setValue(scroll_bar.value() - delta)
        event.accept()

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus):
                self.parent().zoom_report(-1 if event.key() == Qt.Key.Key_Minus else 1)
                event.accept()
                return
        super().keyPressEvent(event)


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
            "warnings": translate("StatisticsReport", "WARNINGS"),
            "movement_group": translate("StatisticsReport", "Movements"),
            "time_group": translate("StatisticsReport", "Time"),
            "bounds_group": translate("StatisticsReport", "Bounds"),
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
            "trajectory": translate("StatisticsReport", "Toolpath Statistics"),
        }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_StatisticsDialog()
        self.ui.setupUi(self)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.inchesCheck = self.ui.inchesCheck
        old_report = self.ui.reportText
        self.reportText = StatisticsBrowser(self)
        self.reportText.setObjectName("reportText")
        self.reportText.setOpenExternalLinks(False)
        self.reportText.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.verticalLayout.replaceWidget(old_report, self.reportText)
        old_report.deleteLater()
        self.ui.reportText = self.reportText
        self.toolSelect = QComboBox(self)
        self.toolSelect.setObjectName("statisticsToolSelect")
        self.toolSelect.setAccessibleName(QCoreApplication.translate("StatisticsReport", "Tool"))
        self.ui.verticalLayout.insertWidget(0, self.toolSelect)
        self.toolSelect.currentIndexChanged.connect(self._refresh_statistics_report)
        self.exportHtmlButton = QPushButton("Export HTML", self)
        self.exportHtmlButton.setIcon(QIcon(":/resource/icons/export.png"))
        self.ui.controlsLayout.addWidget(self.exportHtmlButton)
        self.exportHtmlButton.clicked.connect(self.export_html)
        self.inchesCheck.toggled.connect(self._refresh_statistics_report)
        self._statistics = None
        self._execution = None
        self._plot_segments = None
        self._report_title = ""
        self._source_path = ""
        self._zoom_steps = 0
        self.resize(900, 650)
        self.reportText.customContextMenuRequested.connect(self._show_report_context_menu)

    def show_report(self, report: str) -> None:
        """Replace the report, reset scrolling and bring the dialog forward."""
        self._statistics = None
        self._execution = None
        self.inchesCheck.setEnabled(False)
        self.toolSelect.setEnabled(False)
        self.exportHtmlButton.setEnabled(False)
        self._set_report_text(report)
        self._show_dialog()

    def show_statistics(
        self, statistics: dict[str, object], *, source_path="", execution=None, plot_segments=None
    ) -> None:
        """Display statistics and allow live metric/imperial conversion."""
        self._statistics = statistics
        self._execution = execution
        self._plot_segments = plot_segments
        self._source_path = source_path
        self._report_title = Path(source_path).name if source_path else self._report_labels()["heading"]
        self.toolSelect.blockSignals(True)
        self.toolSelect.clear()
        self.toolSelect.addItem(self._report_labels()["heading"], None)
        for tool in statistics["per_tool"]:
            self.toolSelect.addItem(f"{self._report_labels()['tool']} {tool}", tool)
        self.toolSelect.blockSignals(False)
        self.toolSelect.setEnabled(True)
        self.exportHtmlButton.setEnabled(True)
        self.inchesCheck.setEnabled(True)
        self._refresh_statistics_report()
        self._show_dialog()

    def _refresh_statistics_report(self) -> None:
        if self._statistics is None:
            return
        self.reportText.setHtml(
            statistics_html(
                self._statistics,
                inches=self.inchesCheck.isChecked(),
                labels=self._report_labels(),
                selected=self.toolSelect.currentData(),
                title=self._report_title,
                theme=self._view_theme(),
            )
        )
        frame = self.reportText.document().rootFrame()
        frame_format = frame.frameFormat()
        frame_format.setMargin(20)
        frame.setFrameFormat(frame_format)
        self._align_report_blocks()

    def _align_report_blocks(self):
        """Qt adds body margins to paragraphs but not table blocks; normalize both."""
        block = self.reportText.document().begin()
        while block.isValid():
            block_format = block.blockFormat()
            block_format.setLeftMargin(0)
            block_format.setRightMargin(0)
            QTextCursor(block).setBlockFormat(block_format)
            block = block.next()

    def _view_theme(self):
        palette = self.palette()
        background = palette.color(QPalette.ColorRole.Base).name()
        foreground = palette.color(QPalette.ColorRole.Text).name()
        dark = palette.color(QPalette.ColorRole.Base).lightness() < 128
        accent = "#86d6a1" if dark else "#21664f"
        base_color = palette.color(QPalette.ColorRole.Base)
        text_color = palette.color(QPalette.ColorRole.Text)
        border = QColor.fromRgb(
            *[round(base * 0.8 + text * 0.2) for base, text in zip(base_color.getRgb()[:3], text_color.getRgb()[:3])]
        ).name()
        size = max(self.font().pointSizeF(), 12.0) * 1.1**self._zoom_steps
        return {
            "background": background,
            "foreground": foreground,
            "accent": accent,
            "border": border,
            "panel": background,
            "success_panel": "#204330" if dark else "#e5f4ea",
            "warning_panel": "#4c351b" if dark else "#fff0db",
            "error_panel": "#4b2624" if dark else "#fce8e6",
            "muted": foreground,
            "warning": "#ffbd66" if dark else "#a85400",
            "error": "#ff8a80" if dark else "#b42318",
            "size": size,
            "page_margin": 0,
        }

    def zoom_report(self, steps):
        """Rebuild all font sizes together, retaining the relative scroll position."""
        scroll_bar = self.reportText.verticalScrollBar()
        fraction = scroll_bar.value() / max(scroll_bar.maximum(), 1)
        self._zoom_steps = max(-4, min(10, self._zoom_steps + steps))
        self._refresh_statistics_report()
        scroll_bar.setValue(round(fraction * scroll_bar.maximum()))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if getattr(self, "_statistics", None) is not None:
                self._refresh_statistics_report()

    def export_html(self):
        """Save all tool summaries with a selector, using the current display units."""
        if self._statistics is None:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Export HTML", "statistics.html", "HTML (*.html)")
        if not path:
            return False
        if not path.lower().endswith((".html", ".htm")):
            path += ".html"
        try:
            report = statistics_html(
                self._statistics,
                self._report_labels(),
                inches=self.inchesCheck.isChecked(),
                selected=self.toolSelect.currentData(),
                title=self._report_title,
                portable=True,
                execution=self._execution,
                plot_segments=self._plot_segments,
            )
            write_statistics_html(path, report, source_path=self._source_path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Export HTML", str(exc))
            return False
        QMessageBox.information(
            self,
            "Export HTML",
            QCoreApplication.translate("StatisticsReport", "HTML report exported successfully:\n{0}").format(path),
        )
        return True

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
