"""Export dialog behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.gcode.exporter import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    PLOT_DATA_MODE,
    TURN_FULL_PROGRAM_MODE,
)
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_export_dialog_has_five_logical_modes_and_separate_representation_options(qt_app):
    window = MainWindow()
    dialog = window.exportDlg

    assert dialog.ui.langCmbBox.count() == 5
    assert [dialog.ui.langCmbBox.itemText(index) for index in range(5)] == [
        "TURN FULL PROGRAM",
        "MILL FULL PROGRAM",
        "EXPANDED EXECUTION",
        "PLOT DATA",
        "DXF",
    ]
    assert dialog.ui.arcOutputCmbBox.count() == 4
    assert dialog.ui.incrCmbBox.itemText(0) == "G90 Absolute"
    assert dialog.ui.incrCmbBox.itemText(1) == "G91 Incremental"
    assert dialog.targetCncCombo.count() == 4
    assert dialog.targetCncCombo.itemText(0) == "As source (no conversion)"
    assert dialog.targetCncCombo.itemText(1) == "FANUC milling"
    assert dialog.targetCncCombo.itemText(2) == "SINUMERIK 840D ISO-M (G291)"
    assert dialog.targetCncCombo.itemText(3) == "SINUMERIK 840D native"
    target_row = dialog.ui.gridLayout.getItemPosition(
        next(
            index
            for index in range(dialog.ui.gridLayout.count())
            if dialog.ui.gridLayout.itemAt(index).widget() is dialog.targetCncCombo
        )
    )[0]
    export_type_row = dialog.ui.gridLayout.getItemPosition(
        next(
            index
            for index in range(dialog.ui.gridLayout.count())
            if dialog.ui.gridLayout.itemAt(index).widget() is dialog.ui.langCmbBox
        )
    )[0]
    assert target_row < export_type_row
    dialog.ui.langCmbBox.setCurrentIndex(MILL_FULL_PROGRAM_MODE)
    assert dialog.targetCncCombo.isEnabled()
    assert not dialog.targetCncCombo.model().item(1).isEnabled()
    assert dialog.targetCncCombo.model().item(2).isEnabled()

    dialog.targetCncCombo.setCurrentIndex(2)
    assert dialog.ui.seqNumCmbBox.isEnabled()
    assert dialog.ui.seqStartSpinBox.isEnabled()
    assert dialog.ui.delimCmbBox.isEnabled()
    assert dialog.ui.leadingZeroCmbBox.isEnabled()
    assert dialog.ui.safLineCmbBox.isEnabled()
    assert dialog.ui.startLineEdit.isEnabled()
    assert dialog.ui.endLineEdit.isEnabled()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    assert dialog.targetCncCombo.isEnabled()
    assert dialog.targetCncCombo.model().item(3).isEnabled()
    dialog.ui.langCmbBox.setCurrentIndex(MILL_FULL_PROGRAM_MODE)
    assert not dialog.targetCncCombo.model().item(3).isEnabled()

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    model = dialog.ui.langCmbBox.model()
    assert model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert not model.item(MILL_FULL_PROGRAM_MODE).isEnabled()

    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    assert not dialog.ui.arcOutputCmbBox.isEnabled()
    assert dialog.ui.incrCmbBox.isEnabled()
    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    dialog.sync_mode_availability(False)
    assert dialog.ui.arcOutputCmbBox.isEnabled()
    dialog.ui.langCmbBox.setCurrentIndex(PLOT_DATA_MODE)
    assert not dialog.ui.arcOutputCmbBox.isEnabled()
    assert not dialog.ui.incrCmbBox.isEnabled()

    dialog.ui.langCmbBox.setCurrentIndex(DXF_MODE)
    assert all(
        not widget.isEnabled()
        for widget in (
            dialog.ui.labelForce,
            dialog.ui.forceCmbBox,
            dialog.ui.label_StartText,
            dialog.ui.startLineEdit,
            dialog.ui.label_EndText,
            dialog.ui.endLineEdit,
            dialog.ui.label_SafLine,
            dialog.ui.safLineCmbBox,
            dialog.ui.label_SeqNum,
            dialog.ui.seqNumCmbBox,
            dialog.ui.label_seqStart,
            dialog.ui.seqStartSpinBox,
            dialog.ui.label_seqInterval,
            dialog.ui.seqIntervalSpinBox,
            dialog.ui.label_Delim,
            dialog.ui.delimCmbBox,
            dialog.ui.labelLeadingZero,
            dialog.ui.leadingZeroCmbBox,
            dialog.ui.label_Incr,
            dialog.ui.incrCmbBox,
            dialog.ui.arcOutputLabel,
            dialog.ui.arcOutputCmbBox,
        )
    )

    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.targetCncCombo.setCurrentIndex(0)
    assert dialog.ui.startLineEdit.isEnabled()
    assert dialog.ui.seqNumCmbBox.isEnabled()
    assert dialog.ui.forceCmbBox.isEnabled()
    assert dialog.ui.arcOutputCmbBox.isEnabled()

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert not model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert model.item(MILL_FULL_PROGRAM_MODE).isEnabled()
    window.deleteLater()


def test_export_dialog_disables_conversion_to_detected_sinumerik_source(qt_app, tmp_path):
    window = MainWindow()
    dialog = window.exportDlg
    window.curFile = str(tmp_path / "part.mpf")
    window.ui.editor.setText("G291\nG21 G17 G90\nG0 X0 Y0\nM30\n")
    window.exportTargetCnc = 2
    window.exportMode = MILL_FULL_PROGRAM_MODE

    dialog.loadSettings()

    assert dialog.targetCncCombo.model().item(1).isEnabled()
    assert not dialog.targetCncCombo.model().item(2).isEnabled()
    assert dialog.targetCncCombo.currentIndex() == 0
    window.deleteLater()


def test_export_dialog_allows_native_source_formatting_in_full_mode(qt_app, tmp_path):
    window = MainWindow()
    window.curFile = str(tmp_path / "part.mpf")
    window.ui.editor.setText("G710 G17 G90\nG0 X0 Y0\nM30\n")
    window.exportMode = MILL_FULL_PROGRAM_MODE
    window.exportTargetCnc = 3
    window.exportDlg.loadSettings()
    assert window.exportDlg.targetCncCombo.model().item(3).isEnabled()
    assert window.exportDlg.targetCncCombo.currentIndex() == 3
    window.deleteLater()


def test_export_dialog_cancel_discards_all_pending_values(qt_app):
    window = MainWindow()
    dialog = window.exportDlg
    original = (
        window.exportMode,
        window.exportArcMode,
        window.forceAdr,
        window.startPgmExp,
        window.seqNumStart,
        window.exportTargetCnc,
    )
    dialog.show()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.ui.arcOutputCmbBox.setCurrentIndex(3)
    dialog.ui.forceCmbBox.setCurrentIndex(1)
    dialog.ui.startLineEdit.setText("O9999")
    dialog.ui.seqStartSpinBox.setValue(900)
    dialog.targetCncCombo.setCurrentIndex(2)
    dialog.reject()

    assert (
        window.exportMode,
        window.exportArcMode,
        window.forceAdr,
        window.startPgmExp,
        window.seqNumStart,
        window.exportTargetCnc,
    ) == original
    window.deleteLater()
