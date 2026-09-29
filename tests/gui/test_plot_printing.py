"""Plot print action and page rendering."""

# pylint: disable=protected-access  # Print tests inspect internal plot items.
import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QKeySequence, QMatrix4x4
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QApplication

from app import settings as app_settings
from app.main_window import MainWindow
from app.ui.plot.toolpath_vbo import ToolpathSegment, tool_color
from app.ui.windows.plot_printing import paint_plot_page, print_segment_color, project_toolpath


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


def test_complete_vector_toolpath_is_printed_to_pdf(qt_app, tmp_path):
    segments = project_toolpath(
        (ToolpathSegment((0, 0, 0), (10, 0, 0), 0, 0), ToolpathSegment((10, 0, 0), (10, 10, 0), 1, 1)),
        QMatrix4x4(),
    )
    assert len(segments) == 2
    path = tmp_path / "plot.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    paint_plot_page(printer, segments)
    assert path.read_bytes().startswith(b"%PDF")
    qt_app.processEvents()


def test_print_projection_respects_rapid_visibility_and_keeps_tool_identity():
    source = (
        ToolpathSegment((0, 0, 0), (10, 0, 0), 0, 0, "T1"),
        ToolpathSegment((10, 0, 0), (20, 0, 0), 1, 1, "T2"),
    )
    projected = project_toolpath(source, QMatrix4x4(), show_rapid=False)
    assert len(projected) == 1
    assert projected[0][4:] == (1, "T2")


def test_print_rapid_and_cutting_share_tool_color_when_enabled():
    assert print_segment_color(0, "T1", color_by_tool=True) == tool_color("T1")
    assert print_segment_color(1, "T1", color_by_tool=True) == tool_color("T1")
    assert print_segment_color(2, "T2", color_by_tool=True) == tool_color("T2")
    assert print_segment_color(0, None, color_by_tool=True) == "#b94a4a"


def test_print_action_uses_all_segments_independent_of_playback(qt_app, monkeypatch):
    window = MainWindow()
    window.ui.graphicsView.hide()
    window.show()
    qt_app.processEvents()

    class FakeItem:
        segments = (ToolpathSegment((0, 0, 0), (10, 0, 0), 0, 1),)
        source_segments = segments

    window._toolpath_item = FakeItem()
    window.ui.horizontalSlider.setValue(0)
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
    monkeypatch.setattr(
        "app.main_window.paint_plot_page", lambda printer, captured, **_options: painted.append(captured)
    )
    window.ui.actionPrint.trigger()
    assert len(painted[-1]) == 1
    assert painted[-1][0][4] == 1
    window.deleteLater()
