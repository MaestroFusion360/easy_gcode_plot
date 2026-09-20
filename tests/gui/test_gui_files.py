# pylint: disable=protected-access
from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest
from PyQt6.QtWidgets import QApplication

from app import main_window
from app.gcode.exporter import DXF_MODE
from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace
from app.ui.windows import main_window_file_ops
from app.ui.windows.main_window_editor_ops import MainWindowEditorMixin
from app.ui.windows.main_window_file_ops import MainWindowFileMixin


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


class _StatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, timeout):
        self.messages.append((message, timeout))


def test_recent_files_are_unique_case_insensitively_and_limited():
    recent = main_window._normalized_recent_files(
        ["C:/A.nc", "c:\\a.nc", "C:/B.nc", "C:/C.nc", "C:/D.nc", "C:/E.nc", "C:/F.nc"]
    )
    assert recent == ["C:/A.nc", "C:/B.nc", "C:/C.nc", "C:/D.nc", "C:/E.nc"]


class _DropUrl:
    def __init__(self, path, *, local=True):
        self._path = path
        self._local = local

    def isLocalFile(self):
        return self._local

    def toLocalFile(self):
        return self._path


class _DropEvent:
    def __init__(self, urls):
        self._mime = SimpleNamespace(hasUrls=lambda: bool(urls), urls=lambda: urls)
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def test_drop_event_opens_first_local_file_only():
    opened = []

    class Window(MainWindowFileMixin):
        def maybeSave(self):
            return True

        def loadFile(self, fileName):
            opened.append(fileName)

    event = _DropEvent(
        [
            _DropUrl("https://example.invalid/program.nc", local=False),
            _DropUrl("C:/first.nc"),
            _DropUrl("C:/second.nc"),
        ]
    )

    Window().dropEvent(event)

    assert opened == ["C:/first.nc"]
    assert event.accepted is True
    assert event.ignored is False


def test_file_export_writes_selected_dxf_from_current_trace(monkeypatch, tmp_path):
    result = execute("G21 G90\nG0 X1 Y2 Z3\nG1 X4 Y5 Z6 F100\nM30", language="fanuc_mill")
    target_without_suffix = tmp_path / "toolpath.txt"
    monkeypatch.setattr(
        "app.ui.windows.main_window_file_ops.QFileDialog.getSaveFileName",
        lambda *args: (str(target_without_suffix), "DXF (*.dxf)"),
    )

    class Window(MainWindowFileMixin):
        exportMode = DXF_MODE
        latheMode = False
        execution_result = result
        render_points = render_trace(result)
        ui = SimpleNamespace(
            horizontalSlider=SimpleNamespace(value=lambda: 0),
            statusbar=_StatusBar(),
        )

        def updateData(self):
            return True

        def valueHandler(self, value):
            assert value == 0

    Window().export()

    output = target_without_suffix.with_suffix(".dxf")
    assert output.exists()
    assert [entity.dxftype() for entity in ezdxf.readfile(output).modelspace()] == ["LINE", "LINE"]


def test_remove_spaces_preserves_multiple_parenthesized_comments():
    class Window(MainWindowEditorMixin):
        def __init__(self):
            self.transformed = None

        def _process_selected_lines(self, handler):
            self.transformed = handler(["G1 X1 (first comment) Y2 (second comment) F100\n"])

    window = Window()
    window.removeSpaces()

    assert window.transformed == ["G1X1(first comment)Y2(second comment)F100\n"]


def test_file_open_requests_execution_dialog_for_initial_refresh(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "program.nc"
    path.write_text("G0 X0\nM30\n", encoding="utf-8")
    window = main_window.MainWindow()
    scheduled = []
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **kwargs: scheduled.append(kwargs))

    window.loadFile(str(path))

    assert scheduled == [{"show_dialog": True}]
    window.deleteLater()


def test_file_save_detects_external_modification(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "program.nc"
    path.write_text("G0 X0\n", encoding="utf-8")
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    window.loadFile(str(path))
    path.write_text("EXTERNAL CHANGE\n", encoding="utf-8")
    window.ui.editor.setText("G1 X1\n")
    monkeypatch.setattr(
        main_window_file_ops.QMessageBox,
        "warning",
        lambda *_args, **_kwargs: main_window_file_ops.QMessageBox.StandardButton.No,
    )

    assert window.saveFile(str(path)) is False
    assert path.read_text(encoding="utf-8") == "EXTERNAL CHANGE\n"
    window.deleteLater()


def test_file_dialog_filters_and_extensions(monkeypatch, tmp_path):
    calls = []
    save_target = tmp_path / "program"

    monkeypatch.setattr(
        main_window_file_ops.QFileDialog,
        "getOpenFileName",
        lambda *args: calls.append(("open", args[-1])) or ("", ""),
    )
    MainWindowFileMixin.openFile(SimpleNamespace(maybeSave=lambda: True))
    assert calls[-1] == ("open", main_window_file_ops.NC_FILE_FILTER)

    saved = []
    monkeypatch.setattr(
        main_window_file_ops.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(save_target), "NC programs (*.nc *.cnc *.tap *.txt)"),
    )
    window = SimpleNamespace(curFile="", saveFile=lambda path: saved.append(path) or True)
    assert MainWindowFileMixin.saveAs(window) is True
    assert saved == [str(save_target) + ".nc"]
