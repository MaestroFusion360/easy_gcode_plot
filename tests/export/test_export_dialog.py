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
    assert dialog.ui.startLineEdit.isEnabled()
    assert dialog.ui.seqNumCmbBox.isEnabled()
    assert dialog.ui.forceCmbBox.isEnabled()
    assert dialog.ui.arcOutputCmbBox.isEnabled()

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert not model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert model.item(MILL_FULL_PROGRAM_MODE).isEnabled()
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
    )
    dialog.show()
    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    dialog.ui.arcOutputCmbBox.setCurrentIndex(3)
    dialog.ui.forceCmbBox.setCurrentIndex(1)
    dialog.ui.startLineEdit.setText("O9999")
    dialog.ui.seqStartSpinBox.setValue(900)
    dialog.reject()

    assert (
        window.exportMode,
        window.exportArcMode,
        window.forceAdr,
        window.startPgmExp,
        window.seqNumStart,
    ) == original
    window.deleteLater()
