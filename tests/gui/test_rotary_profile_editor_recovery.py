"""Designer tab recovers damaged data through user copies, without activation."""

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox
from rotary_ui_helpers import profile_id as _profile_id
from rotary_ui_helpers import profile_row as _profile_row

from app.gcode.kernel.milling.kinematics import CATALOG_PATH, load_catalog, profile_document, user_catalog_path
from app.main_window import MainWindow
from app.settings import get_settings


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def test_rotary_tab_opens_and_saves_copy_after_corrupt_override():
    application = QApplication.instance() or QApplication([])
    path = user_catalog_path()
    path.write_text("{broken", encoding="utf-8")
    window = MainWindow()
    try:
        dialog = window.optionsDlg
        dialog.load_values()
        ui = dialog.ui
        assert ui.tabs.indexOf(ui.rotaryTab) >= 0
        assert ui.rotaryTab.isAncestorOf(ui.rotaryAxis1Group)
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, "4ax_table_b"))
        ui.rotaryCopyButton.click()
        copied_id = _profile_id(ui.rotaryProfileList)
        ui.rotaryY1Edit.setText("-1")
        ui.rotarySaveButton.click()
        assert path.read_bytes() == b"{broken"
        dialog.accept()
        assert load_catalog()[copied_id].table_rotary_axes[0].axis == (0, -1, 0)
        assert window.rotaryKinematics is None
        assert next(path.parent.glob("*.bak")).read_bytes() == b"{broken"
        window.rotary_kinematics_actions[copied_id].trigger()
        assert window.rotaryKinematics == copied_id
        window.saveSettings()
    finally:
        window.deleteLater()
        application.processEvents()
    restored = MainWindow()
    try:
        assert restored.rotaryKinematics == copied_id
    finally:
        restored.deleteLater()
        application.processEvents()


def test_active_copy_edits_refresh_once_and_deletion_clears_selection(monkeypatch):
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        dialog, ui = window.optionsDlg, window.optionsDlg.ui
        dialog.load_values()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, "4ax_table_b"))
        ui.rotaryCopyButton.click()
        copied = _profile_id(ui.rotaryProfileList)
        dialog.accept()
        window.rotary_kinematics_actions[copied].trigger()
        window.ui.editor.setText("G90 G0 B90\nG0 Z10\nM30")
        assert window.updateData()
        assert window.execution_result.motions[-1].end_x > 9.9
        calls = []
        update = window.updateData

        def count_update():
            calls.append(True)
            return update()

        monkeypatch.setattr(window, "updateData", count_update)
        dialog.show()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, copied))
        ui.rotaryY1Edit.setText("-1")
        dialog.accept()
        assert calls == [True]
        assert window.execution_result.motions[-1].end_x < -9.9
        assert window.rotaryKinematics == copied
        dialog.show()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, copied))
        ui.rotaryDeleteButton.click()
        dialog.reject()
        assert copied in load_catalog()
        dialog.show()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, copied))
        ui.rotaryDeleteButton.click()
        dialog.accept()
        assert copied not in load_catalog()
        assert window.rotaryKinematics is None
        assert calls == [True, True]
    finally:
        window.deleteLater()
        application.processEvents()


def test_disabled_copy_edit_stays_disabled_in_menu():
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        dialog, ui = window.optionsDlg, window.optionsDlg.ui
        dialog.load_values()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, "4ax_head_b"))
        ui.rotaryCopyButton.click()
        copied = _profile_id(ui.rotaryProfileList)
        ui.rotaryNameEdit.setText("Disabled head copy")
        dialog.accept()
        assert not profile_document(copied)["enabled"]
        assert copied not in window.rotary_kinematics_actions
        assert "4ax_head_b" in window.rotary_kinematics_actions
    finally:
        window.deleteLater()
        application.processEvents()


def test_builtin_enabled_is_next_to_combo_and_persists_without_editing_catalog(qt_app):
    original = CATALOG_PATH.read_bytes()
    window = MainWindow()
    try:
        dialog, ui = window.optionsDlg, window.optionsDlg.ui
        dialog.show()
        ui.tabs.setCurrentWidget(ui.rotaryTab)
        combo = ui.rotaryProfileList
        combo.setCurrentRow(_profile_row(combo, "5ax_table_bc_angled"))
        assert ui.rotaryProfileSidebar.isAncestorOf(combo)
        assert ui.rotaryProfileEditor.isAncestorOf(ui.rotaryEnabledCheck)
        assert ui.rotaryEnabledCheck.isVisible() and ui.rotaryEnabledCheck.isEnabled()
        assert ui.rotaryNameEdit.isReadOnly() and not ui.rotaryAxis1Group.isEnabled()
        ui.rotaryEnabledCheck.setChecked(False)
        dialog.reject()
        assert "5ax_table_bc_angled" in window.rotary_kinematics_actions
        dialog.show()
        combo.setCurrentRow(_profile_row(combo, "5ax_table_bc_angled"))
        assert ui.rotaryEnabledCheck.isChecked()
        ui.rotaryEnabledCheck.setChecked(False)
        # Switching the browser retains the pending visibility change.
        combo.setCurrentRow(_profile_row(combo, "4ax_table_b"))
        dialog.accept()
        assert "5ax_table_bc_angled" not in window.rotary_kinematics_actions
        assert _profile_row(combo, "5ax_table_bc_angled") >= 0
        assert CATALOG_PATH.read_bytes() == original
        assert not user_catalog_path().exists()
    finally:
        window.deleteLater()
        qt_app.processEvents()
    restored = MainWindow()
    try:
        assert "5ax_table_bc_angled" not in restored.rotary_kinematics_actions
        dialog, ui = restored.optionsDlg, restored.optionsDlg.ui
        dialog.show()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, "5ax_table_bc_angled"))
        assert not ui.rotaryEnabledCheck.isChecked()
        ui.rotaryEnabledCheck.setChecked(True)
        dialog.accept()
        assert "5ax_table_bc_angled" in restored.rotary_kinematics_actions
        assert CATALOG_PATH.read_bytes() == original
    finally:
        restored.deleteLater()
        qt_app.processEvents()


def test_disabling_active_builtin_clears_selection_and_refreshes_once(qt_app, monkeypatch):
    window = MainWindow()
    try:
        window.rotary_kinematics_actions["4ax_table_b"].trigger()
        window.ui.editor.setText("G0 B90\nG0 Z10\nM30")
        assert window.updateData()
        calls = []
        monkeypatch.setattr(window, "updateData", lambda: calls.append(True))
        dialog, ui = window.optionsDlg, window.optionsDlg.ui
        dialog.show()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, "4ax_table_b"))
        ui.rotaryEnabledCheck.setChecked(False)
        assert window.rotaryKinematics == "4ax_table_b" and calls == []
        dialog.accept()
        assert window.rotaryKinematics is None and calls == [True]
        assert window.settings.value("CNC/ROTARY_KINEMATICS", type=str) == ""
    finally:
        window.deleteLater()
        qt_app.processEvents()


def test_profile_names_are_generic_and_duplicate_bc45_presets_are_removed():
    catalog = load_catalog()
    assert "tablebc45_ac" not in catalog
    assert "tablebc45" not in catalog
    assert all("DMU" not in profile.name.upper() for profile in catalog.values())


def test_saved_duplicate_bc45_selection_follows_existing_bc_profile(qt_app):
    settings = get_settings()
    settings.setValue("CNC/ROTARY_KINEMATICS", "tablebc45")
    window = MainWindow()
    try:
        assert window.rotaryKinematics == "5ax_table_bc_angled"
        window.saveSettings()
        assert settings.value("CNC/ROTARY_KINEMATICS", type=str) == "5ax_table_bc_angled"
    finally:
        window.deleteLater()
        qt_app.processEvents()


@pytest.fixture(autouse=True)
def rotary_copy_name_dialog(monkeypatch):
    monkeypatch.setattr(
        "app.ui.dialogs.rotary_kinematics_settings.RotaryKinematicsSettings._ask_name",
        lambda self, _title, default: default,
    )


@pytest.mark.parametrize("profile_id", ["4ax_table_b", "5ax_table_bc"])
def test_rotary_limits_editor_round_trip_and_validation(qt_app, monkeypatch, profile_id):
    window = MainWindow()
    try:
        dialog, ui = window.optionsDlg, window.optionsDlg.ui
        dialog.load_values()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, profile_id))
        assert ui.rotaryMin1Edit.text() == ui.rotaryMax1Edit.text() == ""
        assert not ui.rotaryMin1Edit.isEnabled() and not ui.rotaryMax1Edit.isEnabled()
        assert ui.rotaryMin2Edit.text() == ui.rotaryMax2Edit.text() == ""
        assert not ui.rotaryMin2Edit.isEnabled() and not ui.rotaryMax2Edit.isEnabled()
        ui.rotaryCopyButton.click()
        copied = _profile_id(ui.rotaryProfileList)
        assert ui.rotaryMin1Edit.isEnabled() and ui.rotaryMax1Edit.isEnabled()
        ui.rotaryMin1Edit.setText("-20")
        ui.rotaryMax1Edit.setText("40")
        ui.rotaryMin2Edit.setText("-180")
        ui.rotaryMax2Edit.setText("180")
        ui.rotarySaveButton.click()
        dialog.accept()
        joint = load_catalog()[copied].table_rotary_axes[0]
        assert (joint.minimum, joint.maximum) == (-20, 40)
        if profile_id == "5ax_table_bc":
            second_joint = load_catalog()[copied].table_rotary_axes[1]
            assert (second_joint.minimum, second_joint.maximum) == (-180, 180)
        dialog.load_values()
        ui.rotaryProfileList.setCurrentRow(_profile_row(ui.rotaryProfileList, copied))
        assert (ui.rotaryMin1Edit.text(), ui.rotaryMax1Edit.text()) == ("-20.0", "40.0")
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
        for minimum, maximum in (("50", "40"), ("abc", "40"), ("", "40")):
            ui.rotaryMin1Edit.setText(minimum)
            ui.rotaryMax1Edit.setText(maximum)
            ui.rotarySaveButton.click()
        assert len(warnings) == 3
        assert load_catalog()[copied].table_rotary_axes[0] == joint
        ui.rotaryMin1Edit.clear()
        ui.rotaryMax1Edit.clear()
        dialog.accept()
        assert load_catalog()[copied].table_rotary_axes[0].minimum is None
    finally:
        window.deleteLater()
        qt_app.processEvents()
