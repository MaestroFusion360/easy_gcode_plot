from __future__ import annotations

import pytest
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.gcode.kernel import execute
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
    window.close()
    window.deleteLater()


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
