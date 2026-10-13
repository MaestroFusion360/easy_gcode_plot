"""User post lifecycle and GUI exports through the shared CLI contract."""

# pylint: disable=import-outside-toplevel,protected-access  # White-box Dialog and export plumbing checks.

import json
from pathlib import Path
from threading import Event

import pytest
from PyQt6.QtWidgets import QApplication

from app.gcode.export import DXF_MODE, EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE
from app.gcode.export.service import validate_export_request
from app.gcode.kernel import execute
from app.gcode.post_profiles import load_post_profile
from app.main_window import MainWindow
from app.post_profile_library import PostProfileLibrary
from app.ui.windows import main_window_file_ops as ops


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    owner = MainWindow()
    owner.autoUpdateEnabled = False
    owner.ui.actionLatheMode.setChecked(False)
    owner.exportMode = EXPANDED_EXECUTION_MODE
    owner.exportDlg.loadSettings()
    yield owner
    owner.ui.editor.setModified(False)
    owner.close()
    owner.deleteLater()
    qt_app.processEvents()


def test_import_copies_and_validates_original_without_rewriting_it(tmp_path):
    original = tmp_path / "external.json"
    profile = load_post_profile("fanuc_mill")
    original.write_text(json.dumps(profile), encoding="utf-8-sig")
    before = original.read_bytes()
    library = PostProfileLibrary(tmp_path / "managed")
    path = library.import_profile(original, machine="mill")
    assert Path(path).parent == library.directory
    assert original.read_bytes() == before
    assert library.load(path) == profile


@pytest.mark.parametrize("content", ["{broken", "[]", '{"machine":"mill"}'])
def test_invalid_import_leaves_managed_directory_empty(tmp_path, content):
    original = tmp_path / "bad.json"
    original.write_text(content)
    library = PostProfileLibrary(tmp_path / "managed")
    with pytest.raises(ValueError):
        library.import_profile(original)
    assert not list(library.directory.glob("*.json"))
    assert original.read_text(encoding="utf-8") == content


def test_duplicate_rename_and_remove_preserve_controller_id_and_stable_path(tmp_path):
    library = PostProfileLibrary(tmp_path / "managed")
    source = load_post_profile("fanuc_mill_multiaxis")
    path = library.duplicate("fanuc_mill_multiaxis", "Shop mill")
    duplicated = library.load(path)
    assert duplicated == dict(source, name="Shop mill")
    assert library.rename(path, "New name") == path
    assert library.list_profiles()[0].name == "New name"
    assert library.load(path)["id"] == source["id"]
    assert load_post_profile("fanuc_mill_multiaxis") == source
    library.remove(path)
    assert not library.list_profiles()


@pytest.mark.parametrize("operation", ["rename", "remove", "save"])
def test_bundled_posts_cannot_be_changed(tmp_path, operation):
    library = PostProfileLibrary(tmp_path / "managed")
    bundled = Path(ops.__file__).parents[2] / "gcode/export/posts/fanuc_mill.json"
    before = bundled.read_bytes()
    with pytest.raises(ValueError):
        if operation == "rename":
            library.rename(bundled, "No")
        elif operation == "remove":
            library.remove(bundled)
        else:
            library.save(load_post_profile("fanuc_mill"), bundled)
    assert bundled.read_bytes() == before


def test_invalid_save_is_atomic_and_preserves_previous_profile(tmp_path):
    library = PostProfileLibrary(tmp_path)
    path = library.duplicate("fanuc_mill", "Shop")
    before = Path(path).read_bytes()
    invalid = library.load(path)
    invalid["motion"]["linearMove"] = "G1 {unsupported}"
    with pytest.raises(ValueError):
        library.save(invalid, path)
    assert Path(path).read_bytes() == before
    assert not list(tmp_path.glob(f".{Path(path).name}.*"))


@pytest.mark.parametrize("target", ["fanuc_mill", "fanuc_lathe_a", "invalid", "cancel"])
def test_export_add_ready_imports_only_matching_valid_profiles(window, tmp_path, monkeypatch, target):
    dialog = window.exportDlg
    dialog.postLibrary = PostProfileLibrary(tmp_path / "managed")
    dialog.reload_post_profiles("auto")
    source = tmp_path / "incoming.json"
    source.write_text(
        "{broken"
        if target == "invalid"
        else json.dumps(load_post_profile("fanuc_mill" if target == "cancel" else target))
    )
    before = source.read_bytes()
    monkeypatch.setattr(
        "app.ui.dialogs.post_profile_manager.QFileDialog.getOpenFileName",
        lambda *_: ("" if target == "cancel" else str(source), ""),
    )
    warnings = []
    monkeypatch.setattr("app.ui.dialogs.post_profile_manager.QMessageBox.warning", lambda *args: warnings.append(args))
    dialog.ui.postProfileButton.click()
    assert source.read_bytes() == before
    if target == "fanuc_mill":
        assert dialog.postLibrary.load(dialog.targetCncCombo.currentData())["id"] == target
        assert len(dialog.postLibrary.list_profiles()) == 1
    else:
        assert dialog.targetCncCombo.currentData() == "auto"
        assert not dialog.postLibrary.list_profiles()
        assert bool(warnings) == (target != "cancel")


def test_machine_filtering_and_selected_profile_survive_reload(window):
    dialog = window.exportDlg
    mill = dialog.postLibrary.duplicate("fanuc_mill", "Mill")
    lathe = dialog.postLibrary.duplicate("fanuc_lathe_a", "Lathe")
    dialog.reload_post_profiles(mill)
    assert dialog.targetCncCombo.currentData() == mill
    assert dialog.targetCncCombo.findData(lathe) == -1
    assert dialog.targetCncCombo.findData("fanuc_lathe_a") == -1
    dialog.reload_post_profiles()
    assert dialog.targetCncCombo.currentData() == mill
    window.ui.actionLatheMode.setChecked(True)
    dialog.reload_post_profiles("auto")
    assert dialog.targetCncCombo.findData(lathe) >= 0
    assert dialog.targetCncCombo.findData(mill) == -1
    assert dialog.targetCncCombo.findData("fanuc_mill") == -1


def test_selection_is_persisted_by_path_and_restored_after_restart(window, qt_app, monkeypatch):
    dialog = window.exportDlg
    path = dialog.postLibrary.duplicate("fanuc_mill", "Shop")
    dialog.reload_post_profiles(path)
    monkeypatch.setattr(window, "export", lambda: None)
    dialog.accept()
    window.saveSettings()
    second = MainWindow()
    try:
        assert second.exportPostProfile == path
        assert second.exportDlg.targetCncCombo.currentData() == path
        second.exportDlg.postLibrary.rename(path, "Different display name")
        second.exportDlg.reload_post_profiles()
        assert second.exportDlg.targetCncCombo.currentData() == path
    finally:
        second.close()
        second.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("broken", ["missing", "corrupt"])
def test_unavailable_saved_profile_never_silently_exports_with_auto(window, monkeypatch, broken):
    dialog = window.exportDlg
    path = dialog.postLibrary.duplicate("fanuc_mill", "Shop")
    if broken == "missing":
        Path(path).unlink()
    else:
        Path(path).write_text("{bad")
    window.exportPostProfile = path
    dialog.loadSettings()
    assert dialog.targetCncCombo.currentData() == path
    assert "Auto" in dialog.ui.postProfileWarning.text()
    notices = []
    monkeypatch.setattr("app.ui.dialogs.general.QMessageBox.warning", lambda *_: notices.append(1))
    monkeypatch.setattr(window, "export", lambda: pytest.fail("Unavailable profile was exported"))
    dialog.accept()
    assert notices
    assert window.exportPostProfile == path
    with pytest.raises(ValueError):
        ops._target_dialect(window)
    dialog.targetCncCombo.setCurrentIndex(0)
    assert dialog._validate_selected_post() == "auto"


@pytest.mark.parametrize("mode", [MILL_FULL_PROGRAM_MODE, DXF_MODE])
def test_profile_management_is_expanded_only_and_other_modes_ignore_missing_post(window, mode):
    dialog = window.exportDlg
    window.exportPostProfile = "missing.json"
    dialog.ui.langCmbBox.setCurrentIndex(mode)
    assert not dialog.ui.postProfileButton.isEnabled()
    window.exportMode = mode
    request, _source, _encoding = ops._export_request(window)
    assert request.target_dialect is None
    ops._export_file_defaults(window, mode == DXF_MODE)


def test_real_custom_gui_export_uses_same_writer_and_custom_extension(window, monkeypatch, tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["extension"] = "tap"
    profile["motion"]["linearMove"] = "G01"
    profile["program"]["preamble"].append("(CUSTOM SHOP POST)")
    path = window.exportDlg.postLibrary.save(profile)
    window.exportDlg.reload_post_profiles(path)
    window.exportDlg._apply_post_selection()
    window.curFile = str(tmp_path / "source.nc")
    source = "G21 G90\nT1 M6\nG0 X0 Y0 Z5\nG1 X10 F100\nM30"
    window.ui.editor.setText(source)
    assert ops._target_dialect(window) == path
    request, source_text, _encoding = ops._export_request(window)
    assert request.target_dialect == path
    validate_export_request(request)
    output = tmp_path / "result"

    def choose(_owner, _title, suggested, filters, initial):
        assert suggested.endswith(".tap")
        assert "*.tap" in initial and initial in filters
        return str(output), initial

    monkeypatch.setattr(ops.QFileDialog, "getSaveFileName", choose)
    selected, dxf = ops._export_target(window)
    assert selected == str(output) + ".tap" and not dxf
    assert ops._write_export(
        window,
        path=selected,
        result=execute(source, "fanuc_mill"),
        request=request,
        source=source_text,
        render_points=None,
        cancellation=Event(),
    )
    text = Path(selected).read_text(encoding="utf-8")
    assert "CUSTOM SHOP POST" in text
    assert "G01X10" in text


def test_profile_disappearing_after_save_dialog_reports_error(window, monkeypatch):
    path = window.exportDlg.postLibrary.duplicate("fanuc_mill", "Shop")
    window.exportPostProfile = path
    Path(path).unlink()
    errors = []
    monkeypatch.setattr(ops, "_show_export_error", lambda _owner, error, _result: errors.append(str(error)))
    assert ops._export_inputs(window, None) is None
    assert errors


@pytest.mark.parametrize("direction", [2, 3])
def test_heidenhain_full_circles_use_center_and_polar_angle(tmp_path, direction):
    from app.gcode.export.expanded import convert_resolved_program

    library = PostProfileLibrary(tmp_path)
    profile = load_post_profile("heidanhain_itnc530")
    path = library.save(profile)
    result = execute(f"G21 G90\nG0 X10 Y0\nG{direction} X10 Y0 I-10 J0 F100", "fanuc_mill")
    text = convert_resolved_program(result, path)
    lines = text.splitlines()
    assert any(line.startswith("CC ") for line in lines)
    assert any(
        line.startswith("CP IPA-360" if direction == 2 else "CP IPA+360")
        and ("DR-" if direction == 2 else "DR+") in line
        for line in lines
    )


@pytest.mark.parametrize("units,coordinates", [("mm", False), ("inch", False), ("mm", True)])
def test_heidenhain_output_units_coordinates_and_numbering(tmp_path, units, coordinates):
    from app.gcode.export.common import ExportOptions
    from app.gcode.export.expanded import convert_resolved_program

    library = PostProfileLibrary(tmp_path)
    profile = load_post_profile("heidanhain_itnc530")
    profile["options"].update(units=units, incrementalMode=coordinates)
    path = library.save(profile)
    result = execute("G21 G90\nG0 X25.4 Y0 Z5\nG1 X50.8 F254", "fanuc_mill")
    options = None if coordinates else ExportOptions(sequence_numbers=True, sequence_start=0)
    text = convert_resolved_program(result, path, options)
    if units == "inch":
        assert "BEGIN PGM PART INCH" in text and "L X+2 R0 F+10" in text
    elif coordinates:
        assert "L IX+25.4" in text
    else:
        assert text.startswith("0 BEGIN PGM") and "N0" not in text


def test_heidenhain_helix_uses_cp_with_final_depth(tmp_path):
    from app.gcode.export.expanded import convert_resolved_program

    library = PostProfileLibrary(tmp_path)
    profile = load_post_profile("heidanhain_itnc530")
    path = library.save(profile)
    result = execute("G21 G90\nG0 X10 Y0 Z0\nG3 X0 Y10 Z-2 I-10 J0 F100", "fanuc_mill")
    text = convert_resolved_program(result, path)
    assert any(line.startswith("CC ") for line in text.splitlines())
    assert any(line.startswith("CP IPA+") and "Z-2" in line and "DR+" in line for line in text.splitlines())


def test_heidenhain_emits_resolved_machine_return(tmp_path):
    from app.gcode.export.expanded import convert_resolved_program

    library = PostProfileLibrary(tmp_path)
    profile = load_post_profile("heidanhain_itnc530")
    path = library.save(profile)
    result = execute("G21 G90\nG0 X0 Y0 Z5\nG28 Z0", "fanuc_mill")
    text = convert_resolved_program(result, path)
    assert "L Z+0 R0 FMAX M91" in text


def test_heidenhain_shared_writer_outputs_radius_and_preserves_file_on_failure(tmp_path):
    from app.gcode.export.service import ExportRequest, write_export

    library = PostProfileLibrary(tmp_path / "posts")
    profile = load_post_profile("heidanhain_itnc530")
    path = library.save(profile)
    request = ExportRequest(language="fanuc_mill", target_dialect=path, arc_type="radius")
    source = "G21 G90\nG0 X10 Y0\nG3 X0 Y10 I-10 J0 F100"
    output = tmp_path / "part.h"
    exported = write_export(execute(source, "fanuc_mill"), source, output, request)
    assert exported.execution.ok
    assert exported.effective_arc_type == "radius"
    assert "CR X+0 Y+10 R10 DR+ F+100" in output.read_text()
    before = output.read_bytes()
    unsupported = "G21 G90\nG0 X0 Y0 Z5\nG95 G1 X10 F0.1"
    failed = write_export(execute(unsupported, "fanuc_mill"), unsupported, output, request)
    assert not failed.execution.ok
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    ("cycle", "definition"),
    [("G82 X10 Z-5 R2 P100 F100", "CYCL DEF 200"), ("G84 X10 Z-5 R2 F100", "CYCL DEF 207")],
)
def test_heidenhain_emits_supported_drilling_cycles(tmp_path, cycle, definition):
    from app.gcode.export.expanded import convert_resolved_program

    library = PostProfileLibrary(tmp_path)
    profile = load_post_profile("heidanhain_itnc530")
    path = library.save(profile)
    source = f"G21 G90\nT1 M6\nS1000 M3\nG0 X0 Y0 Z5\n{cycle}\nG80\nM30"
    result = execute(source, "fanuc_mill")
    assert result.ok
    text = convert_resolved_program(result, path)
    assert definition in text
    assert "CYCL CALL" in text
