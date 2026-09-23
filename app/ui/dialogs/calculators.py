"""Hole-pattern and pocket G-code calculator dialogs."""

from __future__ import annotations

import math

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QButtonGroup, QDialog, QMessageBox

from app.gcode.generators import (
    PocketParameters,
    hole_circle,
    hole_circle_points,
    hole_grid,
    hole_grid_points,
    pocket_preview_geometry,
    pocket_program,
)
from app.ui.generated.dialogs.hole_calculator import Ui_HoleCalculatorDialog
from app.ui.generated.dialogs.pocket_calculator import Ui_PocketCalculatorDialog
from app.ui.plot.calculator_preview import CalculatorPreview


def _insert_at_caret(owner, text: str) -> None:
    if not text:
        return
    editor = owner.ui.editor
    prefix = "" if not editor.text() or editor.text().endswith(("\n", "\r")) else "\n"
    editor.replaceSelectedText(prefix + text + "\n")


class HoleCalculatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_HoleCalculatorDialog()
        self.ui.setupUi(self)
        self.ui.insertButton.setText(QCoreApplication.translate("SnippetsDialog", "Insert"))
        self.setMinimumWidth(600)
        self.preview = CalculatorPreview(self.ui.previewHost)
        self.ui.previewLayout.addWidget(self.preview)
        self.ui.insertButton.clicked.connect(self.calculate_and_insert)
        self.ui.clearButton.clicked.connect(self.restore_defaults)
        self._connect_preview()
        self.update_preview()

    def _connect_preview(self):
        for widget in (
            self.ui.diameterSpin,
            self.ui.startAngleSpin,
            self.ui.centerXSpin,
            self.ui.centerYSpin,
            self.ui.holeCountSpin,
            self.ui.startXSpin,
            self.ui.startYSpin,
            self.ui.stepXSpin,
            self.ui.stepYSpin,
            self.ui.countXSpin,
            self.ui.countYSpin,
        ):
            widget.valueChanged.connect(self.update_preview)
        self.ui.ccwCheck.toggled.connect(self.update_preview)
        self.ui.patternTabs.currentChanged.connect(self.update_preview)

    def restore_defaults(self):
        self.ui.diameterSpin.setValue(100.0)
        self.ui.startAngleSpin.setValue(0.0)
        self.ui.centerXSpin.setValue(0.0)
        self.ui.centerYSpin.setValue(0.0)
        self.ui.holeCountSpin.setValue(10)
        self.ui.ccwCheck.setChecked(True)
        self.ui.startXSpin.setValue(0.0)
        self.ui.startYSpin.setValue(0.0)
        self.ui.stepXSpin.setValue(10.0)
        self.ui.stepYSpin.setValue(10.0)
        self.ui.countXSpin.setValue(1)
        self.ui.countYSpin.setValue(1)
        self.update_preview()

    def calculate(self) -> str:
        if self.ui.patternTabs.currentWidget() is self.ui.gridTab:
            return hole_grid(
                start_x=self.ui.startXSpin.value(),
                start_y=self.ui.startYSpin.value(),
                step_x=self.ui.stepXSpin.value(),
                step_y=self.ui.stepYSpin.value(),
                count_x=self.ui.countXSpin.value(),
                count_y=self.ui.countYSpin.value(),
            )
        if self.ui.diameterSpin.value() <= 0:
            raise ValueError(QCoreApplication.translate("HoleCalculatorDialog", "Diameter must be greater than zero."))
        return hole_circle(
            diameter=self.ui.diameterSpin.value(),
            start_angle=self.ui.startAngleSpin.value(),
            center_x=self.ui.centerXSpin.value(),
            center_y=self.ui.centerYSpin.value(),
            count=self.ui.holeCountSpin.value(),
            ccw=self.ui.ccwCheck.isChecked(),
        )

    def update_preview(self):
        if self.ui.patternTabs.currentWidget() is self.ui.gridTab:
            points = hole_grid_points(
                start_x=self.ui.startXSpin.value(),
                start_y=self.ui.startYSpin.value(),
                step_x=self.ui.stepXSpin.value(),
                step_y=self.ui.stepYSpin.value(),
                count_x=self.ui.countXSpin.value(),
                count_y=self.ui.countYSpin.value(),
            )
            self.preview.set_geometry(paths=(points,), points=points)
            return
        diameter = self.ui.diameterSpin.value()
        if diameter <= 0:
            self.preview.clear()
            return
        points = hole_circle_points(
            diameter=diameter,
            start_angle=self.ui.startAngleSpin.value(),
            center_x=self.ui.centerXSpin.value(),
            center_y=self.ui.centerYSpin.value(),
            count=self.ui.holeCountSpin.value(),
            ccw=self.ui.ccwCheck.isChecked(),
        )
        center_x = self.ui.centerXSpin.value()
        center_y = self.ui.centerYSpin.value()
        radius = diameter / 2.0
        boundary = [
            (center_x + radius * math.cos(math.tau * index / 96), center_y + radius * math.sin(math.tau * index / 96))
            for index in range(97)
        ]
        traversal = [*points, points[0]] if points else []
        self.preview.set_geometry(boundary=boundary, paths=(traversal,), points=points)

    def set_insertion_enabled(self, enabled: bool):
        self.ui.insertButton.setEnabled(enabled)

    def calculate_and_insert(self):
        try:
            _insert_at_caret(self.parent(), self.calculate())
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))


class PocketCalculatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_PocketCalculatorDialog()
        self.ui.setupUi(self)
        self.ui.insertButton.setText(QCoreApplication.translate("SnippetsDialog", "Insert"))
        self.ui.cuttingHeaderSpacer.setMinimumHeight(self.ui.circularRadio.sizeHint().height())
        self.setMinimumWidth(760)
        self.preview = CalculatorPreview(self.ui.previewHost)
        self.ui.previewLayout.addWidget(self.preview)
        self.type_group = QButtonGroup(self)
        self._insertion_allowed = True
        self.type_group.addButton(self.ui.circularRadio)
        self.type_group.addButton(self.ui.rectangularRadio)
        self.direction_group = QButtonGroup(self)
        self.direction_group.addButton(self.ui.ccwRadio)
        self.direction_group.addButton(self.ui.cwRadio)
        self._configure_spins()
        self.ui.circularRadio.toggled.connect(self._update_type)
        self.ui.insertButton.clicked.connect(self.calculate_and_insert)
        self.ui.clearButton.clicked.connect(self.restore_defaults)
        self._connect_preview()
        self.restore_defaults()

    def _configure_spins(self):
        for spin in self.findChildren(type(self.ui.toolDiameterSpin)):
            spin.setDecimals(3)
            spin.setRange(-1_000_000.0, 1_000_000.0)
            spin.setSingleStep(1.0)

    def _connect_preview(self):
        for widget in (
            self.ui.toolDiameterSpin,
            self.ui.pocketDiameterSpin,
            self.ui.pocketWidthSpin,
            self.ui.pocketHeightSpin,
            self.ui.cornerRadiusSpin,
            self.ui.stepoverSpin,
            self.ui.centerXSpin,
            self.ui.centerYSpin,
            self.ui.zReferenceSpin,
            self.ui.zStartSpin,
            self.ui.zEndSpin,
            self.ui.zStepSpin,
            self.ui.stockXYSpin,
            self.ui.stockZSpin,
            self.ui.feedSpin,
        ):
            widget.valueChanged.connect(self.update_preview)
        for widget in (
            self.ui.circularRadio,
            self.ui.rectangularRadio,
            self.ui.ccwRadio,
            self.ui.cwRadio,
            self.ui.spiralCheck,
            self.ui.helixCheck,
            self.ui.correctionCheck,
        ):
            widget.toggled.connect(self.update_preview)

    def restore_defaults(self):
        values = {
            self.ui.toolDiameterSpin: 10.0,
            self.ui.pocketDiameterSpin: 100.0,
            self.ui.pocketWidthSpin: 100.0,
            self.ui.pocketHeightSpin: 100.0,
            self.ui.cornerRadiusSpin: 0.0,
            self.ui.stepoverSpin: 5.0,
            self.ui.centerXSpin: 0.0,
            self.ui.centerYSpin: 0.0,
            self.ui.zReferenceSpin: 10.0,
            self.ui.zStartSpin: 0.0,
            self.ui.zEndSpin: -2.0,
            self.ui.zStepSpin: 1.0,
            self.ui.stockXYSpin: 0.0,
            self.ui.stockZSpin: 0.0,
            self.ui.feedSpin: 1000.0,
        }
        for spin, value in values.items():
            spin.setValue(value)
        self.ui.circularRadio.setChecked(True)
        self.ui.ccwRadio.setChecked(True)
        self.ui.spiralCheck.setChecked(False)
        self.ui.helixCheck.setChecked(False)
        self.ui.correctionCheck.setChecked(False)
        self._update_type()
        self.update_preview()

    def _update_type(self):
        circular = self.ui.circularRadio.isChecked()
        self.ui.pocketDiameterLabel.setVisible(circular)
        self.ui.pocketDiameterSpin.setVisible(circular)
        for widget in (
            self.ui.pocketWidthLabel,
            self.ui.pocketWidthSpin,
            self.ui.pocketHeightLabel,
            self.ui.pocketHeightSpin,
            self.ui.cornerRadiusLabel,
            self.ui.cornerRadiusSpin,
        ):
            widget.setVisible(not circular)
        self.update_preview()

    def parameters(self) -> PocketParameters:
        return PocketParameters(
            tool_diameter=self.ui.toolDiameterSpin.value(),
            pocket_diameter=self.ui.pocketDiameterSpin.value(),
            pocket_width=self.ui.pocketWidthSpin.value(),
            pocket_height=self.ui.pocketHeightSpin.value(),
            corner_radius=self.ui.cornerRadiusSpin.value(),
            stepover=self.ui.stepoverSpin.value(),
            center_x=self.ui.centerXSpin.value(),
            center_y=self.ui.centerYSpin.value(),
            z_reference=self.ui.zReferenceSpin.value(),
            z_start=self.ui.zStartSpin.value(),
            z_end=self.ui.zEndSpin.value(),
            z_step=self.ui.zStepSpin.value(),
            stock_xy=self.ui.stockXYSpin.value(),
            stock_z=self.ui.stockZSpin.value(),
            feed=self.ui.feedSpin.value(),
            circular=self.ui.circularRadio.isChecked(),
            ccw=self.ui.ccwRadio.isChecked(),
            spiral=self.ui.spiralCheck.isChecked(),
            correction=self.ui.correctionCheck.isChecked(),
            helix=self.ui.helixCheck.isChecked(),
        )

    def update_preview(self):
        try:
            geometry = pocket_preview_geometry(self.parameters())
        except ValueError as exc:
            self.preview.clear()
            self.ui.insertButton.setEnabled(False)
            self.ui.insertButton.setToolTip(str(exc))
            return
        self.preview.set_geometry(boundary=geometry.boundary, paths=geometry.paths)
        self.ui.insertButton.setEnabled(self._insertion_allowed)
        self.ui.insertButton.setToolTip("")

    def set_insertion_enabled(self, enabled: bool):
        self._insertion_allowed = enabled
        self.update_preview()

    def calculate_and_insert(self):
        try:
            _insert_at_caret(self.parent(), pocket_program(self.parameters()))
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
