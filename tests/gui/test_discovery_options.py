"""The single Default discovery editor uses generated Options UI and local drafts."""

import json

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QComboBox, QGroupBox, QMessageBox

from app.main_window import MainWindow
from app.tools.discovery_rules import SETTINGS_KEY, default_settings


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    owner = MainWindow()
    owner.autoUpdateEnabled = False
    owner.millingToolLibrary = {}
    yield owner
    owner.ui.editor.setModified(False)
    owner.close()
    owner.deleteLater()
    qt_app.processEvents()


def _edit(dialog, diameter="SIZE"):
    page = dialog.discoverySettings
    page.regexCheck.setChecked(True)
    for row in range(page.parameterTable.rowCount()):
        if page.parameterTable.item(row, 0).data(Qt.ItemDataRole.UserRole) == "milling_diameter":
            page.parameterTable.item(row, 1).setText(diameter)
            break


def test_edit_save_restore_and_cancel(window):
    dialog = window.optionsDlg
    dialog.load_values()
    _edit(dialog)
    dialog.reject()
    assert window.toolDiscovery == default_settings()
    dialog.load_values()
    _edit(dialog)
    dialog.accept()
    saved = json.loads(window.settings.value(SETTINGS_KEY))
    assert saved == window.toolDiscovery
    assert set(saved) == {"types", "dimensions"}
    assert saved["dimensions"]["milling_diameter"] == "SIZE"
    window.settings.sync()
    restored = MainWindow()
    try:
        assert restored.toolDiscovery == saved
    finally:
        restored.deleteLater()
    dialog.load_values()
    dialog.discoverySettings.restore_defaults()
    dialog.reject()
    assert window.toolDiscovery == saved
    dialog.load_values()
    dialog.discoverySettings.restore_defaults()
    dialog.accept()
    assert window.toolDiscovery == default_settings()


@pytest.mark.parametrize("invalid", ["[", "(SIZE)"])
def test_invalid_rule_prevents_other_option_commits(window, monkeypatch, invalid):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    dialog = window.optionsDlg
    dialog.load_values()
    _edit(dialog, invalid)
    dialog.ui.unitsCombo.setCurrentIndex(1)
    dialog.accept()
    assert warnings
    assert window.defaultUnits == "mm" and window.toolDiscovery == default_settings()


def test_rule_changes_reuse_ast_and_refresh_geometry_without_losing_manual_tools(window, monkeypatch):
    source = "G21 G90 G17\nT1 M6 (BALL MILL SIZE8)\nG0 Z5\nG1 X10 F100\nM30"
    window.ui.editor.setText(source)
    assert window.updateData()
    original = window.execution_result
    assert window.millingTools["T1"]["diameter"] == 10

    def unexpected_parse(*_args):
        pytest.fail("Changing recognition rules must reuse the existing AST")

    monkeypatch.setattr("app.gcode.kernel.milling.executor.parse_program", unexpected_parse)
    monkeypatch.setattr("app.tools.discovery.parse_program", unexpected_parse)
    dialog = window.optionsDlg
    dialog.load_values()
    _edit(dialog)
    dialog.accept()
    assert window.execution_result.program is original.program
    assert window.execution_result.motions == original.motions
    assert window.millingTools["T1"]["diameter"] == 8
    window.millingTools["T1"]["diameter"] = 6
    dialog.load_values()
    dialog.discoverySettings.restore_defaults()
    dialog.accept()
    assert window.millingTools["T1"]["diameter"] == 6


def test_cached_ast_is_invalidated_when_editor_changes(window, monkeypatch):
    window.ui.editor.setText("G21 G90 G17\nT1 M6\nG1 X1 F100\nM30")
    assert window.updateData()
    original = window.execution_result.program
    window.ui.editor.setText("G21 G90 G17\nT2 M6\nG1 X20 F100\nM30")
    assert window.updateData()
    assert window.execution_result.program is not original
    assert window.execution_result.motions[-1].end_x == 20
    assert set(window.millingTools) == {"T2"}


def test_generated_ui_has_one_mode_combo_and_no_presets(window):
    dialog = window.optionsDlg
    dialog.load_values()
    page = dialog.discoverySettings
    assert dialog.ui.toolDiscoveryTab.isAncestorOf(page.typesList)
    assert not dialog.ui.toolDiscoveryTab.findChildren(QGroupBox)
    assert len(dialog.ui.toolDiscoveryTab.findChildren(QComboBox)) == 1
    assert not hasattr(page, "profileCombo") and not hasattr(page, "toolCombo")
    assert page.typesList.count() == 9
    page.typesList.setCurrentRow(2)
    page.namesEdit.setPlainText("CUSTOM\nSPECIAL")
    page.sample.setText("SPECIAL D8")
    page.testButton.click()
    assert "Ball Mill" in page.preview.text() and "8 mm" in page.preview.text()
    assert window.toolDiscovery == default_settings()
    milling = {
        page.parameterTable.item(i, 0).data(Qt.ItemDataRole.UserRole) for i in range(page.parameterTable.rowCount())
    }
    assert "milling_diameter" in milling and not {"nose_radius", "groove_width", "turning_diameter"} & milling
    page.modeCombo.setCurrentIndex(1)
    assert page.typesList.count() == 9
    assert page.parameterTable.item(0, 0).data(Qt.ItemDataRole.UserRole) == "nose_radius"
    page.typesList.setCurrentRow(5)
    assert page.parameterTable.rowCount() == 2
    assert page.testButton.maximumWidth() <= 80


@pytest.mark.parametrize("rule", [r"\bCUSTOM(?:[ ]+LONG)?[ ]+BALL\b", r"\b(?:CUSTOM.LONG.BALL)\b"])
def test_regex_switch_preserves_raw_rules_and_selection(window, rule):
    dialog = window.optionsDlg
    dialog.load_values()
    page = dialog.discoverySettings
    page.typesList.setCurrentRow(2)
    page.regexCheck.setChecked(True)
    page.namesEdit.setPlainText(rule)
    page.parameterTable.item(0, 1).setText(r"SIZE(?:MM)?")
    draft = page.current_profile()
    for enabled in (False, True, False):
        page.regexCheck.setChecked(enabled)
        assert page.typesList.currentRow() == 2
        assert page.namesEdit.toPlainText() == rule
        assert page.parameterTable.item(0, 1).text() == r"SIZE(?:MM)?"
        assert page.current_profile() == draft
    page.namesEdit.setPlainText(rule.replace("CUSTOM", "SPECIAL"))
    assert page.current_profile()["types"] != draft["types"]
    assert page.validate()
    assert "Custom rule" not in json.dumps(page.document)
    page.sample.setText("SPECIAL LONG BALL SIZEMM8")
    page.testButton.click()
    assert "Ball Mill" in page.preview.text() and "8 mm" in page.preview.text()
    page.modeCombo.setCurrentIndex(1)
    assert "GROOVE" in page.sample.placeholderText()
    page.modeCombo.setCurrentIndex(0)
    assert "END MILL" in page.sample.placeholderText()
    page.typesList.setCurrentRow(2)
    assert "SPECIAL" in page.namesEdit.toPlainText()
    dialog.reject()
    assert window.toolDiscovery == default_settings()


def test_multiline_long_names_remain_editable(window):
    dialog = window.optionsDlg
    dialog.load_values()
    page = dialog.discoverySettings
    names = [f"SPECIAL LONG TOOL NAME {index}" for index in range(30)]
    page.namesEdit.setPlainText("\n".join(names))
    draft = page.current_profile()
    page.regexCheck.setChecked(True)
    page.regexCheck.setChecked(False)
    assert page.namesEdit.toPlainText().splitlines() == names
    assert page.current_profile() == draft
    page.restore_defaults()
    assert page.current_profile() == default_settings()
