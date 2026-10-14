"""Simulation settings are committed once, without a live preview or rollback rebuild."""

# pylint: disable=protected-access

from copy import deepcopy

import pytest
from PyQt6.QtWidgets import QApplication
from rotary_ui_helpers import profile_id as _profile_id
from rotary_ui_helpers import profile_row as _profile_row

from app.gcode.kernel.milling.kinematics import profile_document, user_catalog_path
from app.main_window import MainWindow
from app.tools.program_io import write_program_tools


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[False, True], ids=["milling", "turning"])
def window(request, qt_app):
    view = MainWindow()
    view.autoUpdateEnabled = False
    view.ui.actionLatheMode.setChecked(request.param)
    source = (
        "G21 G18 G90 T0101\nG0 X20 Z0\nG1 Z-5 F100\nM30"
        if request.param
        else "G21 G90 T1 M6\nG0 Z1\nG1 Z-1 F100\nG1 X5\nM30"
    )
    view.ui.editor.setText(source)
    assert view.updateData()
    view.stockEnabled = True
    view.stockConfigured = True
    view.ui.actionStockPlayback.setChecked(True)
    assert view._stock_animation_active
    yield view
    view.timer.stop()
    view.deleteLater()
    qt_app.processEvents()


def test_options_cancel_keeps_active_stock_and_ok_rebuilds_once(window, monkeypatch):
    dialog = window.optionsDlg
    timeline = window._stock_timeline
    correction, stock, rotary = window.correctionEnabled, window.showStock, window.rotaryKinematics
    calls = []
    monkeypatch.setattr(window, "updateData", lambda: calls.append("execute"))
    monkeypatch.setattr(window, "refreshPlotView", lambda: calls.append("plot"))
    monkeypatch.setattr(window, "rerenderCurrentResult", lambda: calls.append("sample"))
    monkeypatch.setattr(window, "_request_milling_stock_quality", lambda: calls.append("quality"))
    dialog.show()
    dialog.ui.correctionCheck.setChecked(not correction)
    dialog.ui.showStockCheck.setChecked(not stock)
    dialog.ui.rotaryProfileList.setCurrentRow(1)
    assert (window.correctionEnabled, window.showStock, window.rotaryKinematics) == (correction, stock, rotary)
    assert calls == []
    dialog.restore_defaults()
    assert (window.correctionEnabled, window.showStock, window.rotaryKinematics) == (correction, stock, rotary)
    dialog.reject()
    assert calls == []
    assert window._stock_timeline is timeline
    assert window._stock_animation_active
    dialog.show()
    dialog.ui.correctionCheck.setChecked(not correction)
    dialog.ui.arcToleranceSpin.setValue(window.arcTolerance * 2)
    dialog.ui.playbackSpeedSlider.setValue(4)
    assert calls == []
    dialog.accept()
    assert calls == ["execute"]
    assert window.correctionEnabled is not correction


def test_unchanged_dialogs_do_not_rebuild_stock(window, monkeypatch):
    calls = []
    for name in (
        "updateData",
        "refreshPlotView",
        "rerenderCurrentResult",
        "_request_milling_stock_quality",
        "applyMillingStockSettings",
        "applyStockSettings",
    ):
        monkeypatch.setattr(window, name, lambda *args, method=name: calls.append(method))
    for dialog in (window.optionsDlg, window.wcsDlg, window.stockDlg, window.toolLibraryDlg):
        dialog.show()
        if dialog is window.stockDlg:
            dialog._apply()
        else:
            dialog.accept()
    assert calls == []
    assert window._stock_animation_active


def test_program_import_cancel_and_accept_are_transactional(window, monkeypatch, tmp_path):
    kind, attribute = ("turning", "tools") if window.latheMode else ("milling", "millingTools")
    original = deepcopy(getattr(window, attribute))
    key = next(iter(original))
    edited = deepcopy(original)
    edited[key]["metadata"] = {"nested": ["changed"]}
    path = tmp_path / "tools.json"
    write_program_tools(path, kind, edited)
    dialog = window.toolLibraryDlg
    timeline = window._stock_timeline
    calls = []
    monkeypatch.setattr(dialog, "_program_tool_changed", lambda: calls.append(True))
    dialog.show()
    assert dialog.import_program_tools(kind, str(path))
    assert getattr(window, attribute) == original
    assert calls == []
    dialog.reject()
    assert getattr(window, attribute) == original
    assert window._stock_timeline is timeline
    dialog.show()
    assert dialog.import_program_tools(kind, str(path))
    dialog.accept()
    assert getattr(window, attribute) == edited
    assert calls == [True]


def test_wcs_cancel_and_multiple_edits_commit_once(window, monkeypatch):
    dialog = window.wcsDlg
    original = deepcopy(window.wcsOffsets)
    timeline = window._stock_timeline
    calls = []
    monkeypatch.setattr(window, "updateData", lambda: calls.append(True))
    dialog.show()
    dialog.ui.g54X.setValue(12)
    dialog.ui.g55Z.setValue(-7)
    dialog.ui.homeZ.setValue(40)
    assert window.wcsOffsets == original
    dialog.reject()
    assert calls == []
    assert window._stock_timeline is timeline
    dialog.show()
    dialog.ui.g54X.setValue(12)
    dialog.ui.g55Z.setValue(-7)
    dialog.accept()
    assert calls == [True]
    assert window.wcsOffsets[54][0] == (6 if window.latheMode else 12)
    assert window.wcsOffsets[55][2] == -7


def test_stock_reset_and_accuracy_wait_for_ok(window, monkeypatch):
    dialog = window.stockDlg
    timeline = window._stock_timeline
    calls = []
    name = "applyStockSettings" if window.latheMode else "applyMillingStockSettings"
    monkeypatch.setattr(window, name, lambda values: calls.append(values))
    dialog.show()
    reset = dialog._reset_to_auto if window.latheMode else dialog._milling_reset_to_auto
    accuracy = dialog.accuracy if window.latheMode else dialog.milling_accuracy
    reset()
    accuracy.setValue(4)
    assert dialog.isVisible()
    assert calls == []
    dialog.reject()
    assert window._stock_timeline is timeline
    assert calls == []
    dialog.show()
    reset()
    accuracy.setValue(4)
    dialog._apply()
    assert len(calls) == 1
    assert calls[0]["manual"] is False
    if window.latheMode:
        assert calls[0]["resolution"] == 0.1
    else:
        assert calls[0]["accuracy"] == 4


def test_rotary_draft_is_discarded_with_options(window, monkeypatch):
    dialog = window.optionsDlg
    path = user_catalog_path()
    calls = []
    monkeypatch.setattr(window, "_select_rotary_kinematics", lambda *a, **kw: calls.append(a))
    dialog.show()
    dialog.ui.rotaryProfileList.setCurrentRow(_profile_row(dialog.ui.rotaryProfileList, "4ax_table_b"))
    dialog.ui.rotaryCopyButton.click()
    discarded = _profile_id(dialog.ui.rotaryProfileList)
    dialog.ui.rotaryNameEdit.setText("Pending table")
    dialog.ui.rotarySaveButton.click()
    assert not path.exists()
    dialog.reject()
    assert not path.exists()
    dialog.show()
    assert _profile_row(dialog.ui.rotaryProfileList, discarded) == -1
    dialog.ui.rotaryCopyButton.click()
    saved = _profile_id(dialog.ui.rotaryProfileList)
    dialog.ui.rotaryNameEdit.setText("Pending table")
    dialog.accept()
    assert calls == []  # Browsing/saving a profile never activates it.
    assert profile_document(saved)["name"] == "Pending table"


@pytest.mark.parametrize("operation", ["edit", "assign"])
def test_program_geometry_cancel_discards_draft(window, monkeypatch, operation):
    kind, attribute = ("turning", "tools") if window.latheMode else ("milling", "millingTools")
    original = deepcopy(getattr(window, attribute))
    key = next(iter(original))
    dialog = window.toolLibraryDlg
    dialog.show()
    dialog.refresh(kind, selected_program=key)
    calls = []
    monkeypatch.setattr(window, "updateData", lambda: calls.append(True))
    if operation == "edit":

        def edit_geometry(editor):
            control = editor.noseRadius if window.latheMode else editor.diameter
            control.setValue(control.value() + 1)
            editor.validateAndAccept()
            return editor.result()

        monkeypatch.setattr(dialog._editor_type(kind), "exec", edit_geometry)
        dialog.edit_program_tool(kind)
    else:
        spec = deepcopy(original[key])
        spec["description"] = "Assigned draft"
        dialog._library_working[kind]["T99"] = spec
        dialog.refresh(kind, selected_program=key, selected_library="T99")
        dialog.assign_from_library(kind)
    assert dialog._program_tools(kind)[key] != original[key]
    assert getattr(window, attribute) == original
    dialog.reject()
    assert getattr(window, attribute) == original
    assert calls == []


def test_rotary_selection_and_execution_changes_share_one_commit(window, monkeypatch):
    dialog = window.optionsDlg
    calls = []
    monkeypatch.setattr(window, "updateData", lambda: calls.append("execute"))
    monkeypatch.setattr(window, "refreshPlotView", lambda: calls.append("plot"))
    dialog.show()
    dialog.ui.rotaryProfileList.setCurrentRow(1)
    dialog.ui.correctionCheck.setChecked(not window.correctionEnabled)
    assert window.rotaryKinematics is None
    assert calls == []
    dialog.accept()
    assert window.rotaryKinematics is None
    assert calls == ["execute"]


def test_failed_tool_library_save_does_not_commit_program_geometry(window, monkeypatch):
    from app.ui.dialogs import tool_library_dialog  # pylint: disable=import-outside-toplevel

    kind, attribute = ("turning", "tools") if window.latheMode else ("milling", "millingTools")
    original = deepcopy(getattr(window, attribute))
    key = next(iter(original))
    dialog = window.toolLibraryDlg
    dialog.show()
    dialog._editable_program_tools(kind)[key]["description"] = "Pending geometry"
    monkeypatch.setattr(tool_library_dialog, "save_library_changes", lambda *args: False)
    monkeypatch.setattr(tool_library_dialog.QMessageBox, "warning", lambda *args: None)
    calls = []
    monkeypatch.setattr(window, "updateData", lambda: calls.append(True))
    dialog.accept()
    assert dialog.isVisible()
    assert getattr(window, attribute) == original
    assert calls == []
    dialog.reject()


@pytest.fixture(autouse=True)
def rotary_copy_name_dialog(monkeypatch):
    monkeypatch.setattr(
        "app.ui.dialogs.rotary_kinematics_settings.RotaryKinematicsSettings._ask_name",
        lambda self, _title, default: default,
    )
