from __future__ import annotations

# pylint: disable=protected-access  # Search matches are inspected to verify wraparound.
import pytest
from PyQt6.QtCore import QFile, QSize, Qt, QTranslator, QUrl
from PyQt6.QtGui import QColor, QIcon, QTextFormat
from PyQt6.QtWidgets import QApplication, QWidget

from app import get_version
from app.main_window import MainWindow
from app.ui.dialogs.general import About


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_about_russian_catalog_translates_runtime_metadata(qt_app):
    translator = QTranslator()
    assert translator.load(":/resource/translations/app_ru.qm")
    qt_app.installTranslator(translator)
    parent = QWidget()
    try:
        dialog = About(parent)
        assert dialog.windowTitle() == "О программе Easy G-code Plot"
        assert dialog.ui.versionLabel.text() == f"Версия: {get_version()}"
        assert "трёхосевые траектории CAM для SINUMERIK 840D" in dialog.ui.descriptionLabel.text()
        assert "Свободное ПО" in dialog.ui.licenseLabel.text()
        assert "Supports" not in dialog.ui.descriptionLabel.text()
    finally:
        qt_app.removeTranslator(translator)
        parent.deleteLater()


def test_faq_is_packaged_and_listed_below_about_without_changing_f1(qt_app):
    window = MainWindow()
    help_actions = window.ui.menu_Help.actions()

    assert help_actions == [window.ui.actionAbout, window.ui.actionFAQ]
    assert window.ui.actionAbout.shortcut().toString() == "F1"
    assert window.ui.actionFAQ.shortcut().toString() == "F3"
    assert QFile(":/resource/FAQ.md").exists()
    assert QFile(":/resource/LICENSE.md").exists()

    window.ui.actionFAQ.trigger()
    qt_app.processEvents()

    assert window.helpDlg.isVisible()
    assert "Easy G-Code Plot FAQ" in window.helpDlg.browser.toPlainText()
    assert window.helpDlg.browser.toPlainText().count("Project scope and execution model") == 2
    assert "Turning Stock Removal" in window.helpDlg.browser.toPlainText()
    window.close()
    window.deleteLater()


def test_faq_table_of_contents_anchors_navigate_to_headings(qt_app):
    window = MainWindow()
    browser = window.helpDlg.browser

    for anchor, heading in (
        ("development-and-architecture", "Development and architecture"),
        ("turning-stock-removal", "Turning Stock Removal"),
        ("statistics-and-tokensmacro-variables", "Statistics and Tokens/Macro Variables"),
        ("how-are-milling-arcs-programmed", "How are milling arcs programmed?"),
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
    assert document.documentMargin() == pytest.approx(24.0)
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


def test_faq_command_blocks_have_distinct_background_and_padding(qt_app):
    window = MainWindow()
    dialog = window.helpDlg
    block = dialog.browser.document().begin()
    while block.isValid() and ".\\easy_gcode_plot_cli.exe batch" not in block.text():
        block = block.next()

    assert block.isValid()
    block_format = block.blockFormat()
    assert block_format.hasProperty(QTextFormat.Property.BlockCodeFence)
    assert block_format.background().color() != dialog.browser.palette().base().color()
    assert block_format.leftMargin() >= 12.0
    assert block_format.topMargin() == block_format.bottomMargin() == 0.0
    adjacent_code = dialog.browser.document().begin()
    while adjacent_code.isValid() and adjacent_code.next().isValid():
        if adjacent_code.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence) and (
            adjacent_code.next().blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence)
        ):
            break
        adjacent_code = adjacent_code.next()
    assert adjacent_code.isValid()
    assert adjacent_code.blockFormat().background().color() == adjacent_code.next().blockFormat().background().color()

    first_link = None
    block = dialog.browser.document().begin()
    while block.isValid() and first_link is None:
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.charFormat().isAnchor():
                first_link = fragment.charFormat().foreground().color()
                break
            iterator += 1
        block = block.next()
    assert first_link is not None
    assert first_link != QColor("#70dfff")

    window.close()
    window.deleteLater()


def test_faq_dark_theme_keeps_readable_links_and_source_text(qt_app):
    window = MainWindow()
    dialog = window.helpDlg
    original = dialog.browser.toPlainText()
    dialog.apply_theme("dark")

    assert dialog.browser.toPlainText() == original
    assert dialog.browser.palette().base().color() == QColor("#252526")
    block = dialog.browser.document().begin()
    link_color = None
    code_color = None
    while block.isValid():
        if code_color is None and block.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence):
            code_color = block.blockFormat().background().color()
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.charFormat().isAnchor():
                link_color = fragment.charFormat().foreground().color()
                break
            iterator += 1
        if link_color is not None and code_color is not None:
            break
        block = block.next()
    assert link_color == QColor("#9cc9ee")
    assert code_color == QColor("#3a424c")

    dialog.apply_theme("light")
    assert dialog.browser.toPlainText() == original
    window.close()
    window.deleteLater()


def test_faq_search_counts_wraps_and_survives_theme_change(qt_app):
    window = MainWindow()
    dialog = window.helpDlg
    assert dialog.ui.verticalLayout.itemAt(0).widget() is dialog.browser
    assert dialog.ui.verticalLayout.itemAt(1).layout() is not None
    assert not dialog.search_previous_button.icon().isNull()
    assert not dialog.search_next_button.icon().isNull()
    assert (
        dialog.search_previous_button.icon().pixmap(QSize(18, 18)).toImage()
        == QIcon(":/resource/icons/up.png").pixmap(QSize(18, 18)).toImage()
    )
    assert (
        dialog.search_next_button.icon().pixmap(QSize(18, 18)).toImage()
        == QIcon(":/resource/icons/down.png").pixmap(QSize(18, 18)).toImage()
    )
    dialog.search_edit.setText("deterministic")
    assert dialog._search_timer.isActive()
    dialog._run_pending_search()
    assert len(dialog._search_matches) > 1
    assert dialog.search_count.text() == f"1 / {len(dialog._search_matches)}"
    assert dialog.browser.textCursor().selectedText().casefold() == "deterministic"

    dialog.search_previous()
    assert dialog.search_count.text() == f"{len(dialog._search_matches)} / {len(dialog._search_matches)}"
    dialog.search_next()
    assert dialog.search_count.text() == f"1 / {len(dialog._search_matches)}"

    dialog.apply_theme("dark")
    assert dialog.browser.textCursor().selectedText().casefold() == "deterministic"
    assert dialog.search_count.text() == f"1 / {len(dialog._search_matches)}"

    dialog.search_edit.setText("no-such-faq-term-123")
    dialog._run_pending_search()
    assert dialog.search_count.text() == "0 / 0"
    dialog.search_edit.clear()
    assert dialog.search_count.text() == ""
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

    dialog.navigate_to_anchor(QUrl("#development-and-architecture"))
    assert dialog.browser.textCursor().block().text() == "Development and architecture"

    window.close()
    window.deleteLater()


def test_faq_and_statistics_dialogs_share_window_frame_without_close_button(qt_app):
    window = MainWindow()

    for dialog in (window.helpDlg, window.statisticsDlg):
        assert not hasattr(dialog.ui, "buttonBox")
        flags = dialog.windowFlags()
        assert flags & Qt.WindowType.WindowMinimizeButtonHint
        assert flags & Qt.WindowType.WindowMaximizeButtonHint
        assert flags & Qt.WindowType.WindowCloseButtonHint

    window.close()
    window.deleteLater()


def test_russian_faq_is_packaged_and_loaded_for_russian_language(qt_app, monkeypatch):
    assert QFile(":/resource/FAQ_RU.md").exists()
    monkeypatch.setattr("app.ui.dialogs.help.ui_language", lambda: "ru")

    window = MainWindow()
    dialog = window.helpDlg
    text = dialog.browser.toPlainText()

    assert "часто задаваемые вопросы" in text
    assert "Область применения проекта и модель выполнения" in text

    dialog.navigate_to_anchor(QUrl("#начало-работы"))
    assert dialog.browser.textCursor().block().text() == "Начало работы"

    dialog.apply_theme("dark")
    assert "часто задаваемые вопросы" in dialog.browser.toPlainText()

    window.close()
    window.deleteLater()
