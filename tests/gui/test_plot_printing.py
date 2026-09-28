"""Plot print action and page rendering."""

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QImage, QKeySequence
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QApplication

from app import settings as app_settings
from app.main_window import MainWindow
from app.ui.windows.plot_printing import paint_plot_page


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_print_action_is_in_file_menu_and_toolbar(qt_app):
    window = MainWindow()
    actions = window.ui.menu_File.actions()
    assert actions.index(window.ui.actionPrint) < actions.index(window.ui.actionExit)
    assert window.ui.actionPrint in window.ui.fileToolBar.actions()
    assert window.ui.actionPrint.shortcut() == QKeySequence("Ctrl+P")
    assert not window.ui.actionPrint.icon().isNull()
    assert window.ui.actionFAQ.shortcut() == QKeySequence("F3")
    assert window.ui.actionGrid.shortcut() == QKeySequence("F4")
    window.deleteLater()
    qt_app.processEvents()


def test_existing_empty_faq_and_grid_shortcuts_migrate_once(qt_app):
    settings = QSettings(app_settings.config_path(), QSettings.Format.IniFormat)
    settings.setValue("HOTKEYS/actionFAQ", "")
    settings.setValue("HOTKEYS/actionGrid", "")
    settings.sync()
    window = MainWindow()
    assert window.ui.actionFAQ.shortcut() == QKeySequence("F3")
    assert window.ui.actionGrid.shortcut() == QKeySequence("F4")
    assert settings.value("HOTKEYS/actionFAQ") == "F3"
    assert settings.value("HOTKEYS/actionGrid") == "F4"
    window.deleteLater()
    qt_app.processEvents()

    settings.setValue("HOTKEYS/actionFAQ", "")
    settings.setValue("HOTKEYS/actionGrid", "")
    settings.sync()
    restored = MainWindow()
    assert restored.ui.actionFAQ.shortcut().isEmpty()
    assert restored.ui.actionGrid.shortcut().isEmpty()
    restored.deleteLater()
    qt_app.processEvents()


def test_plot_snapshot_is_printed_to_one_pdf_page(qt_app, tmp_path):
    image = QImage(320, 160, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)
    path = tmp_path / "plot.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    paint_plot_page(printer, image)
    assert path.read_bytes().startswith(b"%PDF")
    qt_app.processEvents()


def test_print_action_captures_plot_for_preview(qt_app, monkeypatch):
    window = MainWindow()
    window.show()
    qt_app.processEvents()
    image = QImage(320, 160, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)
    original_background = window.plotBackground
    original_line = window.plotLineColor
    captured_style = []

    def grab_for_print():
        captured_style.append((window.plotBackground, window.plotLineColor, window.plotGridColor))
        return image

    monkeypatch.setattr(window.ui.graphicsView, "grabFramebuffer", grab_for_print)
    painted = []

    class FakePrinter:
        class PrinterMode:
            HighResolution = 1

        def __init__(self, _mode):
            pass

        def setPageOrientation(self, orientation):
            painted.append(orientation)

    class FakeSignal:
        def connect(self, callback):
            self.callback = callback

    class FakePreview:
        def __init__(self, printer, _parent):
            self.printer = printer
            self.paintRequested = FakeSignal()

        def setWindowTitle(self, _title):
            pass

        def exec(self):
            self.paintRequested.callback(self.printer)

    monkeypatch.setattr("app.main_window.QPrinter", FakePrinter)
    monkeypatch.setattr("app.main_window.QPrintPreviewDialog", FakePreview)
    monkeypatch.setattr("app.main_window.paint_plot_page", lambda printer, captured: painted.append(captured))
    window.ui.actionPrint.trigger()
    assert painted[-1] is image
    assert captured_style == [("#ffffff", "#000000", "#dddddd")]
    assert (window.plotBackground, window.plotLineColor) == (original_background, original_line)
    window.deleteLater()
