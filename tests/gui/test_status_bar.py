"""Bounded status messages retain details and diagnostic source locations."""

from dataclasses import replace

import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QStatusBar

from app.gcode.kernel import Diagnostic, execute
from app.main_window import MainWindow
from app.ui.support.status_bar import MESSAGE_MAX_WIDTH, StatusBar


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_long_status_message_is_elided_and_full_details_survive_resize(qt_app):
    status_bar = StatusBar()
    status_bar.resize(900, 30)
    status_bar.addPermanentWidget(QLabel("MILLING | Steps: 60 | Motions: 36"))
    status_bar.show()
    qt_app.processEvents()
    message = "Export failed:\n" + "a very long file path / " * 100
    try:
        status_bar.showMessage(message)
        assert "\n" not in status_bar.currentMessage()
        assert status_bar.currentMessage().endswith("\u2026")
        assert status_bar.fontMetrics().horizontalAdvance(status_bar.currentMessage()) <= MESSAGE_MAX_WIDTH
        assert status_bar.toolTip() == message
        previous = status_bar.currentMessage()
        status_bar.resize(350, 30)
        qt_app.processEvents()
        assert len(status_bar.currentMessage()) < len(previous)
        assert status_bar.toolTip() == message
        status_bar.clearMessage()
        assert status_bar.currentMessage() == status_bar.toolTip() == ""
    finally:
        status_bar.close()
        status_bar.deleteLater()


def test_status_message_timeout_survives_resize_and_persistent_replacement(qt_app):
    status_bar = StatusBar()
    status_bar.resize(800, 30)
    status_bar.show()
    try:
        status_bar.showMessage("Temporary message " * 100, 120)
        QTest.qWait(70)
        status_bar.resize(500, 30)
        QTest.qWait(90)
        assert status_bar.currentMessage() == status_bar.toolTip() == ""
        status_bar.showMessage("Old timed message", 30)
        status_bar.showMessage("New persistent message")
        QTest.qWait(60)
        assert status_bar.currentMessage() == "New persistent message"
    finally:
        status_bar.close()
        status_bar.deleteLater()


def test_native_status_tip_does_not_resurrect_an_old_notification(qt_app):
    status_bar = StatusBar()
    status_bar.resize(800, 30)
    status_bar.show()
    try:
        status_bar.showMessage("Old notification")
        QStatusBar.showMessage(status_bar, "Native action hint")
        assert status_bar.toolTip() == "Native action hint"
        QStatusBar.clearMessage(status_bar)
        status_bar.resize(700, 30)
        qt_app.processEvents()
        assert status_bar.currentMessage() == status_bar.toolTip() == ""
    finally:
        status_bar.close()
        status_bar.deleteLater()


def test_execution_diagnostics_have_one_counter_and_complete_line_details(qt_app):
    window = MainWindow()
    result = replace(
        execute("G0 X1", language="fanuc_mill"),
        diagnostics=(
            Diagnostic("UNVERIFIED_CUTTER_COMPENSATION", "G41/G42 requires a cutter " * 100, "warning", line=2),
            Diagnostic("UNVERIFIED_CUTTER_COMPENSATION", "Another affected block", "warning", line=5),
        ),
    )
    try:
        window.updateExecutionStatus(result=result)
        assert window.executionStatusLabel.isHidden()
        assert window.diagnosticsStatusLabel.text() == "Warnings: 2"
        tooltip = window.diagnosticsStatusLabel.toolTip()
        assert "Ln 2: UNVERIFIED_CUTTER_COMPENSATION" in tooltip
        assert "Ln 5: UNVERIFIED_CUTTER_COMPENSATION" in tooltip
        assert result.diagnostics[0].message in tooltip
        window.updateExecutionStatus("UPDATING", result=result)
        assert not window.executionStatusLabel.isHidden()
        window.updateExecutionStatus("STALE", result=result)
        assert not window.executionStatusLabel.isHidden()
        window.updateExecutionStatus(result=replace(result, ok=False, diagnostics=()))
        assert not window.executionStatusLabel.isHidden()
        assert window.executionStatusLabel.text() == "ERROR"
    finally:
        window.deleteLater()


def test_execution_does_not_echo_diagnostic_paragraphs_into_status_messages(qt_app):
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.actionLatheMode.setChecked(False)
    window.millingTools = {}
    window.ui.editor.setText("G0 X0 Y10\nG41 G1 X10\nG1 X20\nG40")
    try:
        assert window.updateData()
        assert window.diagnosticsStatusLabel.text().startswith("Warnings:")
        assert "UNVERIFIED_CUTTER_COMPENSATION" in window.diagnosticsStatusLabel.toolTip()
        assert "UNVERIFIED_CUTTER_COMPENSATION" not in window.ui.statusbar.currentMessage()
        assert window.executionStatusLabel.isHidden()
    finally:
        window.deleteLater()
