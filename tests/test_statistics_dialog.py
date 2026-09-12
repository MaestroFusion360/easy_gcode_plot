from __future__ import annotations

import pytest
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.gcode.kernel import execute
from app.gcode.trace_tools import trace_statistics
from app.main_window import MainWindow
from app.ui.statistics import StatisticsDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_statistics_dialog_keeps_long_report_inside_scrollable_text(qt_app):
    dialog = StatisticsDialog()
    report = "Toolpath Statistics\n" + "\n".join(f"Tool T{index}: {index} mm" for index in range(100))

    dialog.show_report(report)
    qt_app.processEvents()

    assert dialog.reportText.isReadOnly()
    assert dialog.reportText.toPlainText().startswith("Tool T0: 0 mm")
    assert "Toolpath Statistics" not in dialog.reportText.toPlainText()
    assert dialog.reportText.verticalScrollBar().maximum() > 0
    assert dialog.height() <= 700
    dialog.close()
    dialog.deleteLater()


def test_main_window_reuses_statistics_dialog_for_current_execution(qt_app):
    window = MainWindow()
    dialog = window.statisticsDlg
    window.execution_result = execute("G21 G90\nG0 X10 Z0\nG1 X20 Z-5 F100\nM30")

    window.statistics()

    assert window.statisticsDlg is dialog
    assert dialog.isVisible()
    assert "Execution: complete" in dialog.reportText.toPlainText()
    assert "Motions: 2" in dialog.reportText.toPlainText()
    assert dialog.inchesCheck.isEnabled()
    window.close()
    window.deleteLater()


def test_statistics_inches_checkbox_converts_all_lengths_and_speeds(qt_app):
    dialog = StatisticsDialog()
    result = execute("G21 G90\nG0 X25.4\nG1 X50.8 F25.4\nM30", language="fanuc_mill")
    statistics = trace_statistics(result, rapid_feed=2540.0)

    dialog.show_statistics(statistics)
    dialog.inchesCheck.setChecked(True)
    qt_app.processEvents()
    imperial = dialog.reportText.toPlainText()

    assert "Length: 2.000 in" in imperial
    assert "Feed length: 1.000 in" in imperial
    assert "Average feed: 1.000 in/min" in imperial
    assert "Assumed rapid speed: 100.000 in/min" in imperial
    assert "Bounds in programmed coordinates (in):" in imperial
    assert " mm" not in imperial

    dialog.inchesCheck.setChecked(False)
    metric = dialog.reportText.toPlainText()
    assert "Length: 50.800 mm" in metric
    assert "Assumed rapid speed: 2540.000 mm/min" in metric
    dialog.close()
    dialog.deleteLater()


def test_statistics_context_menu_uses_application_copy_and_select_all_icons(qt_app):
    dialog = StatisticsDialog()
    menu = dialog.create_report_context_menu()
    actions = {action.text().split("\t", 1)[0].replace("&", ""): action for action in menu.actions()}

    for label, resource in (
        ("Copy", ":/resource/icons/copy.png"),
        ("Select All", ":/resource/icons/select-all.png"),
    ):
        actual = actions[label].icon().pixmap(16, 16).toImage()
        expected = QIcon(resource).pixmap(16, 16).toImage()
        assert not actual.isNull()
        assert actual == expected

    menu.deleteLater()
    dialog.deleteLater()
    qt_app.processEvents()
