"""Turning stock configuration dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox

from app.ui.generated.dialogs.stock import Ui_StockDialog
from app.ui.support.units import metric_value, register_length_spinboxes, set_length_units, set_metric_value

_ACCURACY_RESOLUTIONS = (2.0, 1.0, 0.5, 0.25, 0.1)
_DEFAULT_ACCURACY_INDEX = _ACCURACY_RESOLUTIONS.index(0.5)


class StockDialog(QDialog):
    """Edit axisymmetric turning stock without mutating settings on Cancel."""

    def __init__(self, window):
        super().__init__(window)
        self.ui = Ui_StockDialog()
        self.ui.setupUi(self)
        self.window = window
        self.enabled = self.ui.enabledCheck
        self.outer = self.ui.outerSpin
        self.inner = self.ui.innerSpin
        self.length = self.ui.lengthSpin
        self.front_allowance = self.ui.frontAllowanceSpin
        self.accuracy = self.ui.accuracySlider
        self.inches = self.ui.inchesCheck
        self.reset_auto_button = self.ui.resetAutoButton
        self._length_controls = (self.outer, self.inner, self.length, self.front_allowance)
        register_length_spinboxes(self._length_controls)
        self._front_base_z = 0.0
        self.inches.toggled.connect(self._set_units)
        self.reset_auto_button.clicked.connect(self._reset_to_auto)
        self.ui.buttonBox.accepted.connect(self._apply)
        self.ui.buttonBox.rejected.connect(self.reject)
        self.resize(430, self.sizeHint().height())

    @staticmethod
    def _accuracy_index_for_resolution(resolution: float) -> int:
        return min(
            range(len(_ACCURACY_RESOLUTIONS)),
            key=lambda index: abs(_ACCURACY_RESOLUTIONS[index] - float(resolution)),
        )

    def resolution(self) -> float:
        return _ACCURACY_RESOLUTIONS[self.accuracy.value()]

    def _set_units(self, inches: bool):
        set_length_units(self._length_controls, bool(inches), suffix=True)

    def showEvent(self, event):
        self.enabled.setChecked(getattr(self.window, "stockEnabled", False))
        front_allowance = max(0.0, float(getattr(self.window, "turnStockFrontAllowance", 2.0)))
        set_metric_value(self.front_allowance, front_allowance)
        suggestion = getattr(self.window, "_stock_auto_suggestion", None)
        use_auto = not getattr(self.window, "_stock_manual_override", False)
        if use_auto and suggestion is not None:
            self._front_base_z = float(suggestion.front_z)
            set_metric_value(self.outer, max(0.01, float(suggestion.outer_diameter)))
            set_metric_value(self.inner, float(suggestion.inner_diameter))
            set_metric_value(self.length, max(0.01, float(suggestion.length) + front_allowance))
        else:
            manual_front = float(
                getattr(
                    self.window,
                    "turnStockFrontZ",
                    getattr(self.window, "turnStockFrontAllowance", 2.0),
                )
            )
            self._front_base_z = manual_front - front_allowance
            set_metric_value(self.outer, getattr(self.window, "turnStockDiameter", 50.0))
            set_metric_value(self.inner, getattr(self.window, "turnStockInnerDiameter", 0.0))
            set_metric_value(self.length, getattr(self.window, "turnStockLength", 100.0))
        resolution = float(getattr(self.window, "turnStockResolution", 0.5))
        self.accuracy.setValue(self._accuracy_index_for_resolution(resolution))
        super().showEvent(event)

    def _reset_to_auto(self):
        self.window.resetStockToAuto()
        self.accept()

    def _apply(self):
        front_allowance = metric_value(self.front_allowance)
        values = {
            "enabled": self.enabled.isChecked(),
            "outer_diameter": metric_value(self.outer),
            "inner_diameter": metric_value(self.inner),
            "length": metric_value(self.length),
            "front_allowance": front_allowance,
            "front_z": self._front_base_z + front_allowance,
            "resolution": self.resolution(),
        }
        try:
            self.window.applyStockSettings(values)
        except ValueError as exc:
            QMessageBox.warning(self, "Stock", str(exc))
            return
        self.accept()
