"""Export dialog behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from app.gcode.exporter import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
)
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_export_dialog_has_four_logical_modes_and_separate_representation_options(qt_app):
    window = MainWindow()
    dialog = window.exportDlg

    assert dialog.ui.langCmbBox.count() == 4
    assert [dialog.ui.langCmbBox.itemText(index) for index in range(4)] == [
        "TURN FULL PROGRAM",
        "MILL FULL PROGRAM",
        "EXPANDED EXECUTION",
        "DXF",
    ]
    assert dialog.ui.arcOutputCmbBox.count() == 4
    assert dialog.ui.incrCmbBox.itemText(0) == "G90 Absolute"
    assert dialog.ui.incrCmbBox.itemText(1) == "G91 Incremental"
    assert dialog.targetCncCombo.count() == 6
    assert dialog.targetCncCombo.itemText(0) == "Auto (source controller)"
    assert dialog.targetCncCombo.itemText(1) == "FANUC milling"
    assert dialog.targetCncCombo.itemText(2) == "SINUMERIK 840D ISO-M (G291)"
    assert dialog.targetCncCombo.itemText(3) == "SINUMERIK 840D native"
    assert dialog.targetCncCombo.itemText(4) == "FANUC milling (multi-axis)"
    assert dialog.targetCncCombo.itemText(5) == "SINUMERIK 840D native (multi-axis)"

    dialog.ui.langCmbBox.setCurrentIndex(MILL_FULL_PROGRAM_MODE)
    assert not dialog.targetCncCombo.isEnabled()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    assert dialog.targetCncCombo.isEnabled()
    assert dialog.targetCncCombo.model().item(3).isEnabled()
    assert dialog.targetCncCombo.model().item(4).isEnabled()
    assert dialog.targetCncCombo.model().item(5).isEnabled()

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    model = dialog.ui.langCmbBox.model()
    assert model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert not model.item(MILL_FULL_PROGRAM_MODE).isEnabled()

    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    assert dialog.ui.arcOutputCmbBox.isEnabled()
    assert dialog.ui.incrCmbBox.isEnabled()
    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    dialog.sync_mode_availability(False)
    assert dialog.ui.arcOutputCmbBox.isEnabled()
    dialog.ui.langCmbBox.setCurrentIndex(DXF_MODE)
    assert all(
        not widget.isEnabled()
        for widget in (
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

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert not model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert model.item(MILL_FULL_PROGRAM_MODE).isEnabled()
    window.deleteLater()


@pytest.mark.parametrize("target", [0, 1, 2, 3, 4, 5])
def test_expanded_keeps_all_output_options_for_every_target(qt_app, target):
    """Selecting a concrete target controller must not disable formatting options."""
    window = MainWindow()
    dialog = window.exportDlg
    dialog.sync_mode_availability(False)
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.targetCncCombo.setCurrentIndex(target)

    always_available = (
        dialog.ui.incrCmbBox,
        dialog.ui.startLineEdit,
        dialog.ui.endLineEdit,
        dialog.ui.safLineCmbBox,
        dialog.ui.seqNumCmbBox,
        dialog.ui.seqStartSpinBox,
        dialog.ui.seqIntervalSpinBox,
        dialog.ui.delimCmbBox,
        dialog.ui.leadingZeroCmbBox,
        dialog.modalFeedCombo,
        dialog.decimalPlacesSpin,
        dialog.forceDecimalCombo,
        dialog.plusSignCombo,
    )
    assert all(control.isEnabled() for control in always_available), target
    assert dialog.ui.arcOutputCmbBox.isEnabled()
    window.deleteLater()


def test_expanded_controls_disabled_for_full_and_dxf(qt_app):
    window = MainWindow()
    dialog = window.exportDlg
    dialog.sync_mode_availability(False)

    def _representations():
        return (
            dialog.ui.arcOutputCmbBox,
            dialog.ui.incrCmbBox,
            dialog.modalFeedCombo,
            dialog.decimalPlacesSpin,
            dialog.forceDecimalCombo,
            dialog.plusSignCombo,
        )

    dialog.ui.langCmbBox.setCurrentIndex(MILL_FULL_PROGRAM_MODE)
    dialog.sync_mode_availability(False)
    assert not any(control.isEnabled() for control in _representations())
    # FULL still formats source blocks and program wrappers.
    assert dialog.ui.seqNumCmbBox.isEnabled()
    assert dialog.ui.startLineEdit.isEnabled()
    assert dialog.ui.safLineCmbBox.isEnabled()

    dialog.ui.langCmbBox.setCurrentIndex(DXF_MODE)
    dialog.sync_mode_availability(False)
    assert not any(control.isEnabled() for control in _representations())
    window.deleteLater()


def test_export_dialog_exposes_four_expanded_output_fields(qt_app):
    window = MainWindow()
    dialog = window.exportDlg
    dialog.sync_mode_availability(False)
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.targetCncCombo.setCurrentIndex(0)
    dialog.sync_mode_availability(False)

    assert dialog.modalFeedCombo.currentIndex() == 1
    controls = (dialog.modalFeedCombo, dialog.decimalPlacesSpin, dialog.forceDecimalCombo, dialog.plusSignCombo)
    assert all(control.isEnabled() for control in controls)
    dialog.show()
    qt_app.processEvents()
    button_top = dialog.ui.buttonBox.mapTo(dialog, QPoint(0, 0)).y()
    assert all(control.isVisible() for control in controls)
    assert all(control.mapTo(dialog, QPoint(0, 0)).y() + control.height() <= button_top for control in controls)

    dialog.modalFeedCombo.setCurrentIndex(0)
    dialog.decimalPlacesSpin.setValue(3)
    dialog.forceDecimalCombo.setCurrentIndex(1)
    dialog.plusSignCombo.setCurrentIndex(1)
    dialog.apply_output_fields()
    assert window.modalFeed is False
    assert window.exportDecimalPlaces == 3
    assert window.exportForceDecimal is True
    assert window.exportPlusOutput is True

    dialog.ui.langCmbBox.setCurrentIndex(DXF_MODE)
    dialog.sync_mode_availability(False)
    assert not any(control.isEnabled() for control in controls)
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.ui.langCmbBox.setCurrentIndex(MILL_FULL_PROGRAM_MODE)
    dialog.sync_mode_availability(False)
    assert not any(control.isEnabled() for control in controls)
    window.deleteLater()


def test_export_dialog_cancel_discards_all_pending_values(qt_app):
    window = MainWindow()
    dialog = window.exportDlg
    original = (
        window.exportMode,
        window.exportArcMode,
        window.startPgmExp,
        window.seqNumStart,
        window.exportTargetCnc,
    )
    dialog.show()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.ui.arcOutputCmbBox.setCurrentIndex(3)
    dialog.ui.startLineEdit.setText("O9999")
    dialog.ui.seqStartSpinBox.setValue(900)
    dialog.targetCncCombo.setCurrentIndex(2)
    dialog.reject()

    assert (
        window.exportMode,
        window.exportArcMode,
        window.startPgmExp,
        window.seqNumStart,
        window.exportTargetCnc,
    ) == original
    window.deleteLater()
