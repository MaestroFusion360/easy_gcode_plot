from __future__ import annotations

import pytest
from PyQt6.QtCore import QFile, QUrl
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


def test_faq_table_of_contents_anchors_navigate_to_headings(qt_app):
    window = MainWindow()
    browser = window.helpDlg.browser

    for anchor, heading in (
        ("development", "Development"),
        ("turning-stock-removal", "Turning Stock Removal"),
        ("statistics-diagnostics-and-export", "Statistics, diagnostics and export"),
        ("why-do-ik-appear-for-an-arc-programmed-with-r", "Why do I/K appear for an arc programmed with R?"),
    ):
        window.helpDlg.navigate_to_anchor(QUrl(f"#{anchor}"))
        block = browser.textCursor().block()
        assert block.text() == heading
        assert block.blockFormat().headingLevel() > 0

    window.close()
    window.deleteLater()
