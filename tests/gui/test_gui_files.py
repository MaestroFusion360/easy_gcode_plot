# pylint: disable=protected-access
from __future__ import annotations

import os
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


def test_export_diagnostics_include_line_code_message_and_source():
    result = execute("G0 X1\nG65 P8130\nM30", language="fanuc_mill")

    text = main_window_file_ops._export_diagnostic_text(result, ValueError("invalid execution"))

    assert "ERROR" in text
    assert "line 2" in text
    assert "SUBPROGRAM_MISSING" in text
    assert "G65 targets missing O8130" in text
    assert "Source: G65 P8130" in text


def test_recent_files_are_unique_case_insensitively_and_limited():
    recent = main_window._normalized_recent_files(
        ["C:/A.nc", "c:\\a.nc", "C:/B.nc", "C:/C.nc", "C:/D.nc", "C:/E.nc", "C:/F.nc"]
    )
    assert recent == ["C:/A.nc", "C:/B.nc", "C:/C.nc", "C:/D.nc", "C:/E.nc"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX filesystems are case-sensitive")
def test_recent_files_keep_distinct_posix_paths_that_differ_only_by_case():
    recent = main_window._normalized_recent_files(["/tmp/A.nc", "/tmp/a.nc"])

    assert recent == ["/tmp/A.nc", "/tmp/a.nc"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX filesystems are case-sensitive")
def test_same_file_path_respects_posix_case():
    assert not main_window_file_ops._same_file_path("/tmp/A.nc", "/tmp/a.nc")


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
        lambda *args: calls.append(args) or ("", ""),
    )
    window = SimpleNamespace(
        maybeSave=lambda: True,
        _open_file_directory=lambda: str(tmp_path),
    )
    MainWindowFileMixin.openFile(window)
    assert calls[-1][1:4] == ("Open", str(tmp_path), main_window_file_ops.NC_FILE_FILTER)
    assert "*.ptp" in main_window_file_ops.NC_FILE_FILTER.split(";;", 1)[0]

    saved = []
    monkeypatch.setattr(
        main_window_file_ops.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(save_target), main_window_file_ops.SAVE_FILE_FILTER),
    )
    window = SimpleNamespace(curFile="", saveFile=lambda path: saved.append(path) or True)
    assert MainWindowFileMixin.saveAs(window) is True
    assert saved == [str(save_target) + ".nc"]


def test_cp1251_ptp_opens_and_saves_in_original_encoding(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "program.ptp"
    original = "%\nO0001\n(ПРОГРАММИСТ ЮРИЙ)\nG0 X0\nM30\n"
    path.write_bytes(original.encode("cp1251"))
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    try:
        window.loadFile(str(path))
        assert window.curFile == str(path)
        assert window._document_encoding == "cp1251"
        assert window.fileEncoding == "utf-8"
        assert window.ui.editor.text().replace("\r\n", "\n") == original
        window.ui.editor.setText(original.replace("ЮРИЙ", "ИВАН"))
        assert window.saveFile(str(path)) is True
        assert path.read_bytes().decode("cp1251").find("ИВАН") >= 0
    finally:
        window.deleteLater()


def test_external_change_reload_replaces_editor_content(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "program.nc"
    path.write_text("G0 X0\n", encoding="utf-8")
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    prompts = []
    monkeypatch.setattr(
        main_window_file_ops.QMessageBox,
        "question",
        lambda *_args: prompts.append(_args[2]) or main_window_file_ops.QMessageBox.StandardButton.Yes,
    )
    try:
        window.loadFile(str(path))
        assert str(path.resolve()) in window._document_watcher.files()
        assert str(tmp_path.resolve()) in window._document_watcher.directories()
        window.ui.editor.setText("G0 X999\n")
        path.write_text("G1 X123\nM30\n", encoding="utf-8")
        window._check_document_disk_change()
        assert len(prompts) == 1
        assert "modified by another program" in prompts[0]
        assert "unsaved changes" in prompts[0]
        assert window.ui.editor.text().startswith("G1 X123")
        assert not window.ui.editor.isModified()
        window._check_document_disk_change()
        assert len(prompts) == 1
    finally:
        window.deleteLater()


def test_external_change_no_keeps_unsaved_work_and_reprompts_on_next_change(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "program.nc"
    path.write_text("G0 X0\n", encoding="utf-8")
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    prompts = []
    monkeypatch.setattr(
        main_window_file_ops.QMessageBox,
        "question",
        lambda *_args: prompts.append(_args[2]) or main_window_file_ops.QMessageBox.StandardButton.No,
    )
    try:
        window.loadFile(str(path))
        window.ui.editor.setText("G1 X999\n")
        path.write_text("G1 X1\n", encoding="utf-8")
        window._check_document_disk_change()
        assert len(prompts) == 1
        assert "unsaved changes" in prompts[0]
        assert window.ui.editor.text() == "G1 X999\n"
        assert window.ui.editor.isModified()
        window._check_document_disk_change()
        assert len(prompts) == 1
        path.write_text("G1 X12345\n", encoding="utf-8")
        window._check_document_disk_change()
        assert len(prompts) == 2
        assert window.ui.editor.text() == "G1 X999\n"
    finally:
        window.deleteLater()


def test_open_file_directory_prefers_remembered_directory(tmp_path):
    remembered = tmp_path / "remembered"
    remembered.mkdir()
    settings = SimpleNamespace(value=lambda key, default, **_kwargs: str(remembered))
    window = SimpleNamespace(settings=settings, curFile="")

    assert MainWindowFileMixin._open_file_directory(window) == str(remembered)


def test_open_file_directory_falls_back_to_current_file_directory(tmp_path):
    current = tmp_path / "current"
    current.mkdir()
    settings = SimpleNamespace(value=lambda key, default, **_kwargs: "")
    window = SimpleNamespace(settings=settings, curFile=str(current / "part.nc"))

    assert MainWindowFileMixin._open_file_directory(window) == str(current)


def test_successful_open_remembers_file_directory(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "program.nc"
    path.write_text("G0 X0\nM30\n", encoding="utf-8")
    window = main_window.MainWindow()
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)

    window.loadFile(str(path))

    assert window.settings.value("FILE/LAST_OPEN_DIRECTORY") == str(tmp_path)
    window.deleteLater()
