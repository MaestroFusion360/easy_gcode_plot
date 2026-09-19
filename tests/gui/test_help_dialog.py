from __future__ import annotations

import pytest
from PyQt6.QtCore import QFile, Qt, QUrl
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
    assert QFile(":/resource/LICENSE.md").exists()

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


def test_faq_is_resizable_and_formats_heading_spacing(qt_app):
    window = MainWindow()
    dialog = window.helpDlg
    document = dialog.browser.document()

    assert dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
    assert document.documentMargin() == pytest.approx(14.0)
    assert document.begin().blockFormat().topMargin() == pytest.approx(0.0)

    margins = {}
    block = document.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        if level in (2, 3) and level not in margins:
            margins[level] = (block.blockFormat().topMargin(), block.blockFormat().bottomMargin())
        block = block.next()

    assert margins[2][0] > 0.0 and margins[2][1] > 0.0
    assert margins[3][0] > 0.0 and margins[3][1] > 0.0

    dialog.navigate_to_anchor(QUrl("#turning-stock-removal"))
    assert dialog.browser.textCursor().block().text() == "Turning Stock Removal"

    window.close()
    window.deleteLater()


def test_faq_license_link_opens_packaged_license_dialog(qt_app):
    window = MainWindow()
    dialog = window.helpDlg

    dialog.browser.anchorClicked.emit(QUrl("LICENSE.md"))
    qt_app.processEvents()

    assert dialog.license_dialog is not None
    assert dialog.license_dialog.isVisible()
    assert "MIT License" in dialog.license_dialog.browser.toPlainText()
    assert "Permission is hereby granted" in dialog.license_dialog.browser.toPlainText()

    dialog.navigate_to_anchor(QUrl("#development"))
    assert dialog.browser.textCursor().block().text() == "Development"

    window.close()
    window.deleteLater()
