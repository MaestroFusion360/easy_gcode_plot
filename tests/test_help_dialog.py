from __future__ import annotations

import pytest
from PyQt6.QtCore import QFile
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_faq_is_packaged_and_listed_below_about_without_changing_f1(qt_app):
    window = MainWindow()
    help_actions = window.ui.menu_Help.actions()

    assert help_actions == [window.ui.actionAbout, window.ui.actionFAQ]
    assert window.ui.actionAbout.shortcut().toString() == "F1"
    assert window.ui.actionFAQ.shortcut().isEmpty()
    assert QFile(":/resource/FAQ.md").exists()

    window.ui.actionFAQ.trigger()
    qt_app.processEvents()

    assert window.helpDlg.isVisible()
    assert "Easy G-Code Plot FAQ" in window.helpDlg.browser.toPlainText()
    assert "Turning Stock Removal" in window.helpDlg.browser.toPlainText()
    window.close()
    window.deleteLater()
