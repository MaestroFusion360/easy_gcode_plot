# pylint: disable=protected-access
from __future__ import annotations

import os
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import ezdxf
import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app import main_window
from app.gcode.export_file import ExportRequest, export_file
from app.gcode.exporter import DXF_MODE, EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE
from app.gcode.kernel import execute
from app.gcode.source_mode import SOURCE_DIALECT_FANUC, SOURCE_DIALECT_SINUMERIK
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
    notices = []
    monkeypatch.setattr("app.ui.windows.main_window_file_ops.QMessageBox.information", lambda *a: notices.append(a))

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
    assert len(notices) == 1 and str(output) in notices[0][2]


@pytest.mark.parametrize("cancelled", [False, True])
def test_program_export_failure_or_cancellation_never_reports_success(monkeypatch, tmp_path, cancelled):
    result = execute("G1 X10 F100\nM30")
    monkeypatch.setattr(main_window_file_ops, "_export_target", lambda _owner: (str(tmp_path / "out.nc"), False))
    monkeypatch.setattr(main_window_file_ops, "_ensure_current_export_trace", lambda _owner: True)
    notices, errors = [], []
    monkeypatch.setattr(main_window_file_ops.QMessageBox, "information", lambda *a: notices.append(a))
    monkeypatch.setattr(main_window_file_ops, "_show_export_error", lambda *a: errors.append(a))

    def worker(*_a, **_kw):
        if cancelled:
            return False
        raise OSError("disk write failed")

    monkeypatch.setattr(main_window_file_ops, "run_execution", worker)

    class Window(MainWindowFileMixin):
        execution_result = result
        render_points = render_trace(result)
        latheMode = True
        ui = SimpleNamespace(statusbar=_StatusBar())

    Window().export()
    if cancelled:
        assert len(notices) == 1 and "cancelled" in notices[0][2]
        assert not errors
    else:
        assert len(errors) == 1 and "disk write failed" in str(errors[0][1])
        assert not notices


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
    nc_filter = main_window_file_ops.NC_FILE_FILTER.split(";;", 1)[0]
    assert "*.ptp" in nc_filter
    assert "*.mpf" not in nc_filter and "*.spf" not in nc_filter
    assert "*.mpf" in main_window_file_ops.SINUMERIK_FILE_FILTER
    assert "*.spf" in main_window_file_ops.SINUMERIK_FILE_FILTER

    saved = []
    monkeypatch.setattr(
        main_window_file_ops.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(save_target), main_window_file_ops.SAVE_FILE_FILTER),
    )
    window = SimpleNamespace(curFile="", saveFile=lambda path: saved.append(path) or True)
    assert MainWindowFileMixin.saveAs(window) is True
    assert saved == [str(save_target) + ".nc"]


@pytest.mark.parametrize(
    "source_name,mode,target,expected_name,siemens",
    [
        ("part.mpf", EXPANDED_EXECUTION_MODE, 1, "part_export.nc", False),
        ("part.nc", EXPANDED_EXECUTION_MODE, 2, "part_export.mpf", True),
        ("part.nc", EXPANDED_EXECUTION_MODE, 3, "part_export.mpf", True),
        ("part.nc", EXPANDED_EXECUTION_MODE, 5, "part_export.mpf", True),
        ("part.spf", EXPANDED_EXECUTION_MODE, 0, "part_export.spf", True),
        ("part.nc", EXPANDED_EXECUTION_MODE, 0, "part_export.nc", False),
        ("part.mpf", MILL_FULL_PROGRAM_MODE, 1, "part_export.mpf", True),
        ("part.nc", MILL_FULL_PROGRAM_MODE, 2, "part_export.nc", False),
        ("part.nc", MILL_FULL_PROGRAM_MODE, 3, "part_export.nc", False),
    ],
)
def test_export_dialog_prefills_target_extension_directory_and_filter(
    monkeypatch, tmp_path, source_name, mode, target, expected_name, siemens
):
    calls = []

    def select(*args):
        calls.append(args)
        return args[2], args[4]

    monkeypatch.setattr(main_window_file_ops.QFileDialog, "getSaveFileName", select)
    owner = SimpleNamespace(
        curFile=str(tmp_path / source_name), exportMode=mode, exportTargetCnc=target, latheMode=False
    )
    assert main_window_file_ops._export_target(owner) == (str(tmp_path / expected_name), False)
    assert calls[0][3] == main_window_file_ops.SAVE_FILE_FILTER
    expected_filter = main_window_file_ops.SINUMERIK_FILE_FILTER if siemens else main_window_file_ops.NC_PROGRAM_FILTER
    assert calls[0][4] == expected_filter


def test_export_dialog_selected_group_controls_missing_extension(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main_window_file_ops.QFileDialog,
        "getSaveFileName",
        lambda *_args: (str(tmp_path / "manual"), main_window_file_ops.SINUMERIK_FILE_FILTER),
    )
    owner = SimpleNamespace(curFile=str(tmp_path / "part.mpf"), exportMode=1, exportTargetCnc=1)
    assert main_window_file_ops._export_target(owner) == (str(tmp_path / "manual.mpf"), False)


@pytest.mark.parametrize(
    ("source", "source_dialect", "expected"),
    [
        (
            "O0001\nG21 G17 G90\nG0 X0 Y0\nG1 X10 F100\nM30\n",
            SOURCE_DIALECT_FANUC,
            "O0001\nG21G17G90\nG0X0Y0\nG1X10F100\nM30\n",
        ),
        (
            "G291\nO0001\nG21 G17 G90\nG0 X0 Y0\nG1 X10 F100\nM30\n",
            SOURCE_DIALECT_SINUMERIK,
            "G291\nO0001\nG21G17G90\nG0X0Y0\nG1X10F100\nM30\n",
        ),
    ],
)
def test_full_program_export_preserves_source_dialect(source, source_dialect, expected, tmp_path):
    result = execute(source, language="fanuc_mill", source_dialect=source_dialect)
    assert result.ok and result.complete
    output = tmp_path / "converted.nc"
    request = ExportRequest(language="fanuc_mill", format="nc", mode="full", spaces=False)

    main_window_file_ops._write_export(
        None,
        path=str(output),
        result=result,
        request=request,
        source=source,
        render_points=(),
        cancellation=Event(),
    )

    assert output.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize(
    ("source", "source_dialect"),
    [
        ("G21 G17 G90\nG0 X0 Y0\nM30\n", SOURCE_DIALECT_FANUC),
        ("G291\nG21 G17 G90\nG0 X0 Y0\nM30\n", SOURCE_DIALECT_SINUMERIK),
    ],
)
def test_full_program_export_accepts_its_source_dialect(source, source_dialect, tmp_path):
    result = execute(source, language="fanuc_mill", source_dialect=source_dialect)
    output = tmp_path / "same-dialect.nc"
    request = ExportRequest(language="fanuc_mill", format="nc", mode="full")

    main_window_file_ops._write_export(
        None,
        path=str(output),
        result=result,
        request=request,
        source=source,
        render_points=(),
        cancellation=Event(),
    )

    assert output.exists()
    assert (
        "G291" in output.read_text(encoding="utf-8")
        if source_dialect == SOURCE_DIALECT_SINUMERIK
        else "G291" not in output.read_text(encoding="utf-8")
    )


def test_full_program_normalization_applies_formatting_without_changing_geometry(tmp_path):
    source = "O0001\nN5 G21 G17 G90\nN10 G0 X0 Y0\nN20 G1 X10 F100\nM30\n"
    result = execute(source, language="fanuc_mill")
    output = tmp_path / "formatted.mpf"
    request = ExportRequest(
        language="fanuc_mill",
        format="nc",
        mode="full",
        sequence_numbers=True,
        sequence_start=100,
        sequence_increment=10,
        spaces=True,
        leading_zero=True,
    )

    main_window_file_ops._write_export(
        None,
        path=str(output),
        result=result,
        request=request,
        source=source,
        render_points=(),
        cancellation=Event(),
    )

    assert output.read_text(encoding="utf-8") == (
        "O0001\nN100 G21 G17 G90\nN110 G00 X0 Y0\nN120 G01 X10 F100\nN130 M30\n"
    )


def test_full_program_normalization_applies_start_end_and_safety_options(tmp_path):
    source = "O0001\nG21 G17 G90\nG0 X0 Y0\nG1 X10 F100\nM30\n"
    result = execute(source, language="fanuc_mill")
    output = tmp_path / "program-wrappers.mpf"
    request = ExportRequest(
        language="fanuc_mill",
        format="nc",
        mode="full",
        start_program="O0002",
        end_program="M30",
        safety_line=True,
        spaces=True,
    )

    main_window_file_ops._write_export(
        None,
        path=str(output),
        result=result,
        request=request,
        source=source,
        render_points=(),
        cancellation=Event(),
    )

    assert output.read_text(encoding="utf-8") == (
        "O0002\nG80\nG0 G17 G40 G49 G90\nG21 G17 G90\nG0 X0 Y0\nG1 X10 F100\nM30\n"
    )


def test_full_program_normalization_can_remove_frame_numbers_and_spaces(tmp_path):
    source = "G291\nO0001\nN5 G21 G17 G90\nN10 G0 X0 Y0\nN20 G1 X10 F100\nM30\n"
    result = execute(source, language="fanuc_mill", source_dialect=SOURCE_DIALECT_SINUMERIK)
    output = tmp_path / "compact.nc"
    request = ExportRequest(language="fanuc_mill", format="nc", mode="full", sequence_numbers=False, spaces=False)

    main_window_file_ops._write_export(
        None,
        path=str(output),
        result=result,
        request=request,
        source=source,
        render_points=(),
        cancellation=Event(),
    )

    assert output.read_text(encoding="utf-8") == "G291\nO0001\nG21G17G90\nG0X0Y0\nG1X10F100\nM30\n"


def test_full_program_normalization_validates_with_the_gui_wcs_offsets(tmp_path):
    source = "G21 G17 G90\nG54\nG0 X0 Y0\nG1 X10 F100\nM30\n"
    execution_options = {"wcs_offsets": {54: (125.0, -40.0, 0.0)}}
    result = execute(source, language="fanuc_mill", **execution_options)
    output = tmp_path / "wcs.mpf"
    request = ExportRequest(language="fanuc_mill", format="nc", mode="full", spaces=True)

    main_window_file_ops._write_export(
        None,
        path=str(output),
        result=result,
        request=request,
        source=source,
        render_points=(),
        cancellation=Event(),
    )

    replay = execute(output.read_text(encoding="utf-8"), language="fanuc_mill", **execution_options)
    assert replay.ok and replay.complete
    assert [(m.end_x, m.end_y, m.end_z) for m in replay.motions] == [
        (m.end_x, m.end_y, m.end_z) for m in result.motions
    ]


@pytest.mark.parametrize(("target", "mode"), [(2, "G291"), (3, "G290"), (5, "G290")])
def test_export_dialog_accept_keeps_sinumerik_mode_first_with_custom_wrappers(
    qt_app, tmp_path, monkeypatch, target, mode
):
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30"
    result = execute(source, language="fanuc_mill")
    window = main_window.MainWindow()
    output = tmp_path / "dialog-output.mpf"
    window.latheMode = False
    window.ui.editor.setText(source)

    def save_export():
        request, request_source, _encoding = main_window_file_ops._export_request(window)
        main_window_file_ops._write_export(
            window,
            path=str(output),
            result=result,
            request=request,
            source=request_source,
            render_points=(),
            cancellation=Event(),
        )

    monkeypatch.setattr(window, "export", save_export)
    try:
        dialog = window.exportDlg
        dialog.show()
        qt_app.processEvents()
        dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
        dialog.targetCncCombo.setCurrentIndex(target)
        dialog.ui.arcOutputCmbBox.setCurrentIndex(1)
        dialog.ui.startLineEdit.setText("123")
        dialog.ui.endLineEdit.setText("1234")
        dialog.ui.safLineCmbBox.setCurrentIndex(0)
        dialog.ui.seqNumCmbBox.setCurrentIndex(1)
        dialog.ui.seqStartSpinBox.setValue(1)
        dialog.ui.seqIntervalSpinBox.setValue(1)
        dialog.ui.delimCmbBox.setCurrentIndex(0)
        dialog.accept()

        lines = output.read_text(encoding="utf-8").splitlines()
        assert lines[0] == mode
        assert lines[1] == "N1123"
        assert lines[-1].endswith("1234")
        assert any(line.startswith("N1") for line in lines)
        assert window.exportTargetCnc == target
    finally:
        window.deleteLater()


def test_gui_expanded_export_uses_owner_output_fields(qt_app, tmp_path):
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nX20\nM30"
    result = execute(source, language="fanuc_mill")
    output = tmp_path / "gui-output.nc"
    owner = SimpleNamespace(
        exportMode=EXPANDED_EXECUTION_MODE,
        latheMode=False,
        exportTargetCnc=0,
        modalFeed=False,
        exportDecimalPlaces=2,
        exportForceDecimal=True,
        exportPlusOutput=True,
        ui=SimpleNamespace(editor=SimpleNamespace(text=lambda: source)),
    )
    request, request_source, _encoding = main_window_file_ops._export_request(owner)

    main_window_file_ops._write_export(
        owner,
        path=str(output),
        result=result,
        request=request,
        source=request_source,
        render_points=(),
        cancellation=Event(),
    )

    text = output.read_text(encoding="utf-8")
    assert text.count("F+100.") == 2
    assert "X+10." in text


@pytest.mark.parametrize(
    ("export_mode", "target_cnc", "language"),
    [
        (EXPANDED_EXECUTION_MODE, 0, "fanuc_mill"),
        (EXPANDED_EXECUTION_MODE, 1, "fanuc_mill"),
        (EXPANDED_EXECUTION_MODE, 2, "fanuc_mill"),
        (EXPANDED_EXECUTION_MODE, 3, "fanuc_mill"),
        (EXPANDED_EXECUTION_MODE, 4, "fanuc_mill"),
        (EXPANDED_EXECUTION_MODE, 5, "fanuc_mill"),
        (MILL_FULL_PROGRAM_MODE, 0, "fanuc_mill"),
        (DXF_MODE, 0, "fanuc_mill"),
        (EXPANDED_EXECUTION_MODE, 2, "fanuc_turn"),
    ],
)
def test_gui_and_cli_export_are_byte_identical(qt_app, tmp_path, export_mode, target_cnc, language):
    """The GUI must only fill the shared contract; it must not convert on its own."""
    if language == "fanuc_turn":
        source = "O1234\nG21 G18 G90\nG0 X0 Z0\nG1 X20 Z-10 F100\nG3 X40 Z-20 I0 K-10\nM30\n"
    else:
        source = "O1234\nG21 G17 G90\nG0 X0 Y0\nG2 X10 Y10 I10 J0 F100\nM30\n"
    source_path = tmp_path / "part.nc"
    source_path.write_bytes(source.encode("utf-8"))
    result = execute(source, language=language)
    owner = SimpleNamespace(
        exportMode=export_mode,
        latheMode=language == "fanuc_turn",
        exportTargetCnc=target_cnc,
        ui=SimpleNamespace(editor=SimpleNamespace(text=lambda: source)),
    )
    request, request_source, _encoding = main_window_file_ops._export_request(owner)

    gui_output = tmp_path / "gui.out"
    main_window_file_ops._write_export(
        owner,
        path=str(gui_output),
        result=result,
        request=request,
        source=request_source,
        render_points=(),
        cancellation=Event(),
    )
    cli_output = tmp_path / "cli.out"
    export_file(source_path, cli_output, request)

    assert gui_output.read_bytes() == cli_output.read_bytes()


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
        assert str(path.parent.resolve()) in window._document_watcher.directories()
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


@pytest.mark.parametrize("atomic", [False, True])
def test_external_save_notifies_through_filesystem_events(qt_app, tmp_path, monkeypatch, atomic):
    path = tmp_path / "watched.nc"
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
        window.show()
        QTest.qWait(400)
        # Rechecking an unchanged document must not attach a Windows file
        # handle that would block the next editor's atomic replacement.
        window._check_document_disk_change()
        if os.name == "nt":
            assert not window._document_watcher.files()
        for text in ("G1 X123\n", "G1 X4567\n"):
            previous_count = len(prompts)
            if atomic:
                replacement = tmp_path / "replacement.nc"
                replacement.write_text(text, encoding="utf-8")
                replacement.replace(path)
            else:
                path.write_text(text, encoding="utf-8")
            for _ in range(40):
                QTest.qWait(50)
                if len(prompts) > previous_count:
                    break
            assert len(prompts) == previous_count + 1
            assert window.ui.editor.text().replace("\r\n", "\n") == text
            if os.name == "nt":
                assert str(path.parent.resolve()) in window._document_watcher.directories()
                assert not window._document_watcher.files()
            else:
                assert str(path.resolve()) in window._document_watcher.files()
    finally:
        window.hide()
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


def test_pasted_native_text_selects_dialect_without_saving_and_follows_undo(qt_app):
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    window.latheMode = False
    window.rotaryKinematics = None
    window.curFile = ""
    source = "G90 G0 X1 Y0 Z0\nCIP X-1 I1=0 J1=0.7071067811865476 K1=0.7071067811865476 F100\nM30"
    try:
        window.ui.editor.setText("")
        window.ui.editor.SendScintilla(window.ui.editor.SCI_EMPTYUNDOBUFFER)
        qt_app.clipboard().setText(source)
        window.ui.editor.paste()
        assert window.curFile == ""
        assert window._document_source_dialect == "sinumerik"
        assert window._document_comment_style == "semicolon"
        assert window._document_arc_type == 1
        window.updateData(show_errors=False)
        assert window.execution_result.ok and window.execution_result.complete, window.execution_result.diagnostics
        assert window.execution_result.source_dialect == "sinumerik"
        assert window.execution_result.motions[-1].source_kind == "cip"
        window.ui.editor.undo()
        assert window._document_source_dialect == "fanuc"
        assert window._document_comment_style is None
        window.ui.editor.redo()
        assert window._document_source_dialect == "sinumerik"
    finally:
        window.autoUpdateTimer.stop()
        window.timer.stop()
        window.deleteLater()
        qt_app.processEvents()


def test_sinumerik_mpf_document_defaults_follow_initial_g290_g291_mode(qt_app, tmp_path, monkeypatch):
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    actions = (window.ui.actionRelative_to_start, window.ui.actionAbsolute, window.ui.actionRadius_value)
    main_window_file_ops._set_arc_action(window, 1)
    window.arc_type = 1
    window._select_rotary_kinematics("4ax_table_b")
    try:
        native = tmp_path / "native.mpf"
        native.write_text("%_N_NATIVE_MPF\n; native source\nN10 G290\nCYCLE800(1,2,3)\n", encoding="utf-8")
        window.loadFile(str(native))
        assert window._document_source_dialect == "sinumerik"
        assert window.rotaryKinematics == "4ax_table_b"
        assert window._rotary_kinematics_actions["4ax_table_b"].isChecked()
        assert window._rotary_kinematics_actions["5ax_table_ac_angled"].isEnabled()
        assert window._rotary_kinematics_actions["5ax_table_bc_angled"].isEnabled()
        assert window.optionsDlg.ui.rotaryKinematicsCombo.isEnabled()
        assert window._document_arc_type == 1
        assert window._document_comment_style == "semicolon"
        assert window.lexer.comment_style == "semicolon"
        assert window.ui.actionRelative_to_start.isChecked()
        assert [action.isChecked() for action in actions] == [True, False, False]
        assert window.ui.actionGroupArcType.checkedAction() is window.ui.actionRelative_to_start
        assert window.arc_type == 1

        iso = tmp_path / "iso.spf"
        iso.write_text("%_N_ISO_SPF\nN10 G291\nN20 G90 G54\nN30 G0 X10\n", encoding="utf-8")
        window.loadFile(str(iso))
        assert window._document_source_dialect == "sinumerik"
        assert window._document_arc_type is None
        assert window._document_comment_style is None
        assert window.lexer.comment_style == window.commentStyle
        assert [action.isChecked() for action in actions] == [True, False, False]
        assert window.ui.actionGroupArcType.checkedAction() is window.ui.actionRelative_to_start

        fanuc = tmp_path / "ordinary_fanuc.nc"
        fanuc.write_text("G21 G17 G90\nG0 X0 Y0\nG1 X10 F100\nM30\n", encoding="utf-8")
        window.loadFile(str(fanuc))
        assert window._document_source_dialect == "fanuc"
        assert window.rotaryKinematics == "4ax_table_b"
        assert window._rotary_kinematics_actions["4ax_table_b"].isEnabled()
        assert window.optionsDlg.ui.rotaryKinematicsCombo.isEnabled()
        assert window._document_arc_type is None
        assert window._document_comment_style is None
        assert window.lexer.comment_style == window.commentStyle
        monkeypatch.setattr(window, "updateData", lambda: None)
        window.ui.actionRadius_value.trigger()
        assert [action.isChecked() for action in actions] == [False, False, True]
        assert window.arc_type == 3
    finally:
        window.deleteLater()


@pytest.mark.parametrize("profile,axis", [("5ax_table_ac_angled", "A"), ("5ax_table_bc_angled", "B")])
def test_native_rotary_selection_reaches_gui_execution_and_plot(qt_app, tmp_path, monkeypatch, profile, axis):
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    source = f"""G710 G17 G90 G94
CYCLE800(2,"TISCH",200000,57,0,0,50,-15,0,0,0,0,0,1,,1)
G0 X0 Y0 Z5
CYCLE800()
G0 X10 Y0 Z5
TRAORI
G1 X10 Y0 Z0 {axis}=10 C=0 F300
G3 X0 Y10 CR=10 {axis}=20 C=IC(90)
TRAFOOF
M30
"""
    path = tmp_path / "native.mpf"
    path.write_text(source, encoding="utf-8")
    try:
        window.loadFile(str(path))
        combo = window.optionsDlg.ui.rotaryKinematicsCombo
        assert combo.isEnabled()
        assert window._rotary_kinematics_actions[profile].isEnabled()
        window._rotary_kinematics_actions[profile].trigger()
        assert window.rotaryKinematics == profile
        assert combo.currentData() == profile
        assert window.execution_result.ok and window.execution_result.complete, window.execution_result.diagnostics
        assert window.execution_result.kinematics_profile == profile
        assert window.execution_result.source_dialect == "sinumerik"
        assert any(m.arc is not None for m in window.execution_result.motions)
        assert {e.kind for e in window.execution_result.events} >= {"TILTED_WORK_PLANE_ON", "TCP_CONTROL_ON"}
        other = "5ax_table_bc_angled" if axis == "A" else "5ax_table_ac_angled"
        combo.setCurrentIndex(combo.findData(other))
        assert window.rotaryKinematics == other
        assert not window.execution_result.ok
        assert window.execution_result.diagnostics[-1].code == "UNCONFIGURED_ROTARY_AXIS"
        # Opening a different native file must retain the user's selected profile.
        path.write_text("G710 G90\nG0 X1\nM30\n", encoding="utf-8")
        window.loadFile(str(path))
        assert window.rotaryKinematics == other
        assert combo.currentData() == other
    finally:
        window.deleteLater()


def test_supplied_full_native_cam_file_executes_in_gui(qt_app, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "tmp/cnc programs/5ax/smpl_sim08_5ax_sinumerik_mm.mpf"
    if not path.exists():
        pytest.skip("User's full CAM reference is not present")
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    try:
        window._select_rotary_kinematics("5ax_table_ac_angled")
        window.loadFile(str(path))
        assert window.updateData()
        result = window.execution_result
        assert result.ok and result.complete, result.diagnostics
        # G41 adds two short corner joins in the tilted G55 contour.
        assert len(result.motions) == 5001
        for label in (18670, 18680):
            corner = [motion for motion in result.motions if motion.source_nlabel == label]
            assert [motion.move for motion in corner] == [1, 2]
            assert all(motion.compensation_applied for motion in corner)
        assert len(result.execution_steps) == 5232
        assert window._document_arc_type == 1
        assert window.optionsDlg.ui.rotaryKinematicsCombo.isEnabled()
        assert all(d.status != "unsupported" for d in result.diagnostics)
    finally:
        window.deleteLater()


def test_sinumerik_checkbox_reexecutes_native_cycles_with_selected_interface(qt_app, tmp_path, monkeypatch):
    path = tmp_path / "sl.mpf"
    path.write_text("G710 G90\nF100\nG0 Z5\nMCALL CYCLE81(5,0,2,-5,,0,0,1,12)\nX2\nMCALL\nM30")
    window = main_window.MainWindow()
    original = window.sinumerik840dSl
    window.autoUpdateEnabled = False
    monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
    try:
        window.sinumerik840dSl = True
        window.loadFile(str(path))
        assert window.updateData()
        assert window.execution_result.ok
        for enabled in (False, True):
            dialog = window.optionsDlg
            dialog.show()
            qt_app.processEvents()
            dialog.ui.sinumerik840dSlCheck.setChecked(enabled)
            dialog.accept()
            result = window.execution_result
            assert result.sinumerik_840d_sl == enabled
            assert result.ok == enabled, result.diagnostics
            if not enabled:
                assert any(d.code == "UNSUPPORTED_SINUMERIK_CYCLE" for d in result.diagnostics)
    finally:
        window.sinumerik840dSl = original
        window.saveSettings()
        window.deleteLater()


@pytest.mark.parametrize("enabled,parameter_count", [(False, 5), (True, 9)])
def test_gui_sinumerik_checkbox_selects_native_cycle_post(qt_app, tmp_path, enabled, parameter_count):
    source = "G21 G17 G90\nG0 Z5\nG98 G81 X-25 Y10 Z-17 R4 F400\nX25\nG80\nM30"
    window = main_window.MainWindow()
    original = window.sinumerik840dSl
    output = tmp_path / "native.mpf"
    try:
        window.optionsDlg.show()
        qt_app.processEvents()
        window.optionsDlg.ui.fileTypeCombo.setCurrentIndex(1)
        window.optionsDlg.ui.sinumerik840dSlCheck.setChecked(enabled)
        window.optionsDlg.accept()
        window.latheMode = False
        window.exportMode = EXPANDED_EXECUTION_MODE
        window.exportTargetCnc = 3
        window.ui.editor.setText(source)
        result = execute(source, language="fanuc_mill", sinumerik_840d_sl=enabled)
        request, request_source, _encoding = main_window_file_ops._export_request(window)
        assert request.sinumerik_840d_sl == enabled
        main_window_file_ops._write_export(
            window,
            path=str(output),
            result=result,
            request=request,
            source=request_source,
            render_points=(),
            cancellation=Event(),
        )
        text = output.read_text(encoding="utf-8")
        call = next(line for line in text.splitlines() if "MCALL CYCLE81(" in line)
        assert len(call.split("(")[1].removesuffix(")").split(",")) == parameter_count
        replay = execute(text, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=enabled)
        assert replay.ok, replay.diagnostics
        assert [event.drilling.position for event in replay.events if event.drilling is not None] == [
            (-25, 10, -17),
            (25, 10, -17),
        ]
    finally:
        window.sinumerik840dSl = original
        window.saveSettings()
        window.deleteLater()
