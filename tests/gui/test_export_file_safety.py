"""GUI output contracts preserve source files and previous exports."""

from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from app.gcode.export.common import EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE
from app.gcode.export_file import ExportRequest
from app.gcode.kernel import execute
from app.main_window import MainWindow
from app.ui.windows import main_window_file_ops as ops

# These regressions exercise the actual GUI worker and file-target preflight.
# pylint: disable=protected-access


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("turning", [False, True])
@pytest.mark.parametrize("target", [1, 2, 3, 4, 5])
def test_export_dialog_target_filter_and_extension(tmp_path, monkeypatch, turning, target):
    siemens = target in (3, 5) or (target == 2 and not turning)
    suffix = ".mpf" if siemens else ".nc"
    expected_filter = ops.SINUMERIK_FILE_FILTER if siemens else ops.NC_PROGRAM_FILTER
    owner = SimpleNamespace(
        curFile=str(tmp_path / "part.mpf"),
        exportMode=EXPANDED_EXECUTION_MODE,
        exportTargetCnc=target,
        latheMode=turning,
    )

    def save_dialog(parent, title, suggested, filters, initial_filter):
        assert parent is owner
        assert Path(suggested).name == "part_export" + suffix
        assert filters == ops.SAVE_FILE_FILTER
        assert initial_filter == expected_filter
        return str(tmp_path / "output"), initial_filter

    monkeypatch.setattr(ops.QFileDialog, "getSaveFileName", save_dialog)
    assert ops._export_target(owner) == (str(tmp_path / "output") + suffix, False)


@pytest.mark.parametrize("source_suffix", [".nc", ".mpf", ".SPF"])
@pytest.mark.parametrize("mode", [EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE])
def test_auto_and_full_export_defaults_follow_source_container(tmp_path, source_suffix, mode):
    owner = SimpleNamespace(
        curFile=str(tmp_path / ("part" + source_suffix)),
        exportMode=mode,
        exportTargetCnc=0 if mode == EXPANDED_EXECUTION_MODE else 1,
        latheMode=False,
    )
    suggested, selected, suffix = ops._export_file_defaults(owner, False)
    assert suffix == source_suffix.lower()
    assert Path(suggested).name == "part_export" + suffix
    assert selected == (ops.NC_PROGRAM_FILTER if suffix == ".nc" else ops.SINUMERIK_FILE_FILTER)


@pytest.mark.parametrize("failure", ["write", "cancel"])
def test_gui_dxf_preserves_previous_file_and_never_reports_cancel_as_success(tmp_path, monkeypatch, failure):
    output = tmp_path / "part.dxf"
    output.write_text("PREVIOUS DXF")
    cancellation = Event()

    def saveas(path):
        Path(path).write_text("PARTIAL DXF", encoding="utf-8")
        if failure == "write":
            raise OSError("simulated disk failure")
        cancellation.set()

    monkeypatch.setattr("app.gcode.export.dxf.build_dxf_document", lambda *_a, **_k: SimpleNamespace(saveas=saveas))
    with pytest.raises(OSError if failure == "write" else InterruptedError):
        ops._write_export(
            None,
            path=output,
            result=execute("G1 X10 F100", language="fanuc_mill"),
            request=ExportRequest(language="fanuc_mill", format="dxf"),
            source="",
            render_points=None,
            cancellation=cancellation,
        )
    assert output.read_text() == "PREVIOUS DXF"
    assert not list(tmp_path.glob(".part.dxf.*"))


@pytest.mark.parametrize("alias", [False, True])
def test_gui_program_export_rejects_open_source_or_hardlink(tmp_path, monkeypatch, alias):
    source = tmp_path / "part.nc"
    source.write_text("G1 X10 F100\nM30")
    output = tmp_path / "alias.nc" if alias else source
    if alias:
        output.hardlink_to(source)
    notices = []
    monkeypatch.setattr(ops.QFileDialog, "getSaveFileName", lambda *_a: (str(output), "All files (*)"))
    monkeypatch.setattr(ops, "_show_export_error", lambda *_a: notices.append(_a))
    owner = SimpleNamespace(curFile=str(source), exportMode=1, execution_result=None)
    assert ops._export_target(owner) is None
    assert source.read_text() == "G1 X10 F100\nM30"
    assert len(notices) == 1


def test_gui_tool_list_cannot_overwrite_open_source(qt_app, tmp_path, monkeypatch):
    source = tmp_path / "part.nc"
    original = "T1 M6\nG1 X10 F100\nM30"
    source.write_text(original)
    window = MainWindow()
    notices = []
    monkeypatch.setattr(ops, "_ensure_current_export_trace", lambda *_a: True)
    monkeypatch.setattr(ops.QFileDialog, "getSaveFileName", lambda *_a: (str(source), "All files (*)"))
    monkeypatch.setattr(ops.QMessageBox, "critical", lambda *_a: notices.append(_a))
    try:
        window.curFile = str(source)
        window.execution_result = execute(original, language="fanuc_mill")
        assert window.exportToolList() is False
        assert source.read_text() == original
        assert len(notices) == 1
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_invalid_legacy_snippet_does_not_prevent_main_window_startup(qt_app, tmp_path):
    directory = tmp_path / "snippets"
    directory.mkdir()
    (directory / "bad.txt").write_bytes(b"\xff")
    (directory / "valid.txt").write_text("G1 X10", encoding="utf-8")
    window = MainWindow()
    try:
        assert [(record.name, record.body) for record in window.snippetsDlg.library.list_snippets()] == [
            ("valid", "G1 X10")
        ]
        assert (directory / "bad.txt").read_bytes() == b"\xff"
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()
