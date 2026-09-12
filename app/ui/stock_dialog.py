"""Turning stock configuration dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QSlider,
    QVBoxLayout,
)

_ACCURACY_RESOLUTIONS = (2.0, 1.0, 0.5, 0.25, 0.1)
_DEFAULT_ACCURACY_INDEX = _ACCURACY_RESOLUTIONS.index(0.5)


class StockDialog(QDialog):
    """Edit axisymmetric turning stock without mutating settings on Cancel."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Stock")
        self.enabled = QCheckBox("Run Stock Removal when Play is pressed", self)
        self.outer = self._spin(0.01, 100000.0, 50.0)
        self.inner = self._spin(0.0, 100000.0, 0.0)
        self.length = self._spin(0.01, 100000.0, 100.0)
        self.front_allowance = self._spin(0.0, 100000.0, 2.0)
        self.accuracy = QSlider(Qt.Orientation.Horizontal, self)
        self.accuracy.setRange(0, len(_ACCURACY_RESOLUTIONS) - 1)
        self.accuracy.setSingleStep(1)
        self.accuracy.setPageStep(1)
        self.accuracy.setTickInterval(1)
        self.accuracy.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.accuracy.setValue(_DEFAULT_ACCURACY_INDEX)
        self.accuracy.setToolTip("Higher accuracy gives a finer stock model and uses more processing time.")

        form = QFormLayout()
        form.addRow("Outside diameter", self.outer)
        form.addRow("Inside diameter", self.inner)
        form.addRow("Length", self.length)
        form.addRow("Z stock allowance", self.front_allowance)
        form.addRow("Accuracy", self.accuracy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.enabled)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(430, self.sizeHint().height())

    @staticmethod
    def _spin(minimum, maximum, value):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(3)
        spin.setValue(value)
        spin.setSuffix(" mm")
        return spin

    @staticmethod
    def _accuracy_index_for_resolution(resolution: float) -> int:
        return min(
            range(len(_ACCURACY_RESOLUTIONS)),
            key=lambda index: abs(_ACCURACY_RESOLUTIONS[index] - float(resolution)),
        )

    def resolution(self) -> float:
        return _ACCURACY_RESOLUTIONS[self.accuracy.value()]

    def showEvent(self, event):
        self.enabled.setChecked(getattr(self.window, "stockEnabled", False))
        front_allowance = max(0.0, float(getattr(self.window, "turnStockFrontAllowance", 2.0)))
        self.front_allowance.setValue(front_allowance)
        suggestion = getattr(self.window, "_stock_auto_suggestion", None)
        if suggestion is not None:
            self.outer.setValue(max(self.outer.minimum(), float(suggestion.outer_diameter)))
            self.inner.setValue(float(suggestion.inner_diameter))
            self.length.setValue(max(self.length.minimum(), float(suggestion.length) + front_allowance))
        else:
            self.outer.setValue(getattr(self.window, "turnStockDiameter", 50.0))
            self.inner.setValue(getattr(self.window, "turnStockInnerDiameter", 0.0))
            self.length.setValue(getattr(self.window, "turnStockLength", 100.0))
        resolution = float(getattr(self.window, "turnStockResolution", 0.5))
        self.accuracy.setValue(self._accuracy_index_for_resolution(resolution))
        super().showEvent(event)

    def _apply(self):
        values = {
            "enabled": self.enabled.isChecked(),
            "outer_diameter": self.outer.value(),
            "inner_diameter": self.inner.value(),
            "length": self.length.value(),
            "front_allowance": self.front_allowance.value(),
            "resolution": self.resolution(),
        }
        try:
            self.window.applyStockSettings(values)
        except ValueError as exc:
            QMessageBox.warning(self, "Stock", str(exc))
            return
        self.accept()
