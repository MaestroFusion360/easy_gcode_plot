"""Milling and turning stock configuration dialog."""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.generated.dialogs.stock import Ui_StockDialog
from app.ui.support.units import metric_value, register_length_spinboxes, set_length_units, set_metric_value

_ACCURACY_RESOLUTIONS = (2.0, 1.0, 0.5, 0.25, 0.1)
_DEFAULT_ACCURACY_INDEX = _ACCURACY_RESOLUTIONS.index(0.5)


class StockDialog(QDialog):
    """Edit milling and turning stock without mutating settings on Cancel."""

    def __init__(self, window):
        super().__init__(window)
        self.ui = Ui_StockDialog()
        self.ui.setupUi(self)
        self.window = window
        self.enabled = self.ui.enabledCheck
        self.outer = self.ui.outerSpin
        self.inner = self.ui.innerSpin
        self.length = self.ui.lengthSpin
        self.front_z = self.ui.frontAllowanceSpin
        self.accuracy = self.ui.accuracySlider
        self.inches = self.ui.inchesCheck
        self.reset_auto_button = self.ui.resetAutoButton
        self._length_controls = (self.outer, self.inner, self.length, self.front_z)
        register_length_spinboxes(self._length_controls)
        self._front_base_z = 0.0
        self._reset_turning_pending = False
        self._initial_values = {}
        for control in self._length_controls:
            control.valueChanged.connect(self._turning_value_changed)
        self.inches.toggled.connect(self._set_units)
        self.reset_auto_button.clicked.connect(self._reset_to_auto)
        self.ui.buttonBox.accepted.connect(self._apply)
        self.ui.buttonBox.rejected.connect(self.reject)
        self._setup_milling_tab()
        self.resize(465, self.sizeHint().height())

    def _setup_milling_tab(self):
        """Keep the existing turning form and add one independent milling form."""
        root, tabs = self._create_stock_tabs()
        self._create_milling_form(root, tabs)

    def _create_stock_tabs(self):
        root = self.layout()
        elements = []
        while root.count():
            elements.append(root.takeAt(0))
        tabs = QTabWidget(self)
        tabs.setObjectName("stockTabs")
        turning = QWidget(tabs)
        turning_layout = QVBoxLayout(turning)
        for element in elements:
            layout = element.layout()
            if layout is not None:
                turning_layout.addLayout(layout)
            elif element.widget() is not None:
                turning_layout.addWidget(element.widget())
        # The Ok/Cancel buttons must remain available on both tabs.
        button_layout = self.ui.buttonLayout
        button_layout.removeWidget(self.ui.buttonBox)
        self.ui.buttonBox.setParent(self)
        tabs.addTab(turning, QCoreApplication.translate("StockDialog", "Turning"))
        return root, tabs

    def _create_milling_form(self, root, tabs):
        milling = QWidget(tabs)
        form = QFormLayout(milling)
        self.milling_manual = QCheckBox(QCoreApplication.translate("StockDialog", "Manual stock box"), milling)
        self.milling_manual.toggled.connect(self._set_milling_manual)
        form.addRow(self.milling_manual)
        self.milling_fields = {}
        for key, label in (
            ("x_minus", QCoreApplication.translate("StockDialog", "X- from WCS")),
            ("x_plus", QCoreApplication.translate("StockDialog", "X+ from WCS")),
            ("y_minus", QCoreApplication.translate("StockDialog", "Y- from WCS")),
            ("y_plus", QCoreApplication.translate("StockDialog", "Y+ from WCS")),
            ("z_minus", QCoreApplication.translate("StockDialog", "Z- from WCS")),
            ("z_plus", QCoreApplication.translate("StockDialog", "Z+ from WCS")),
        ):
            spin = QDoubleSpinBox(milling)
            spin.setObjectName("millingStock" + key.title().replace("_", "") + "Spin")
            spin.setDecimals(3)
            spin.setRange(-100000.0, 100000.0)
            spin.setSuffix(" mm")
            form.addRow(label, spin)
            self.milling_fields[key] = spin
        self.milling_allowance = QDoubleSpinBox(milling)
        self.milling_allowance.setObjectName("millingStockAllowanceSpin")
        self.milling_allowance.setRange(0.0, 10000.0)
        self.milling_allowance.setDecimals(3)
        self.milling_allowance.setSuffix(" mm")
        form.addRow(QCoreApplication.translate("StockDialog", "Automatic stock allowance"), self.milling_allowance)
        self._create_milling_accuracy(milling, form)
        self._milling_length_controls = (*self.milling_fields.values(), self.milling_allowance)
        register_length_spinboxes(self._milling_length_controls)
        self.milling_inches = QCheckBox(QCoreApplication.translate("StockDialog", "Inches"), milling)
        self.milling_inches.setObjectName("millingStockInchesCheck")
        self.milling_inches.toggled.connect(self._set_milling_units)
        form.addRow(self.milling_inches)
        self.milling_reset = QPushButton(QCoreApplication.translate("StockDialog", "Use automatic bounds"), milling)
        self.milling_reset.clicked.connect(self._milling_reset_to_auto)
        form.addRow(self.milling_reset)
        tabs.addTab(milling, QCoreApplication.translate("StockDialog", "Milling"))
        root.addWidget(tabs)
        root.addWidget(self.ui.buttonBox)
        self.stock_tabs = tabs
        self._set_milling_manual(self.milling_manual.isChecked())

    def _create_milling_accuracy(self, milling, form):
        self.milling_accuracy = QSlider(Qt.Orientation.Horizontal, milling)
        self.milling_accuracy.setObjectName("millingStockAccuracySlider")
        self.milling_accuracy.setRange(0, 4)
        self.milling_accuracy.setPageStep(1)
        self.milling_accuracy.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.milling_accuracy.setTickInterval(1)
        self.milling_accuracy.setToolTip(
            QCoreApplication.translate(
                "StockDialog", "Higher accuracy gives a finer stock model and uses more processing time."
            )
        )
        form.addRow(QCoreApplication.translate("StockDialog", "Accuracy"), self.milling_accuracy)

    def _set_milling_manual(self, enabled):
        for spin in self.milling_fields.values():
            spin.setEnabled(enabled)

    def _milling_reset_to_auto(self):
        self.milling_manual.setChecked(False)
        self._load_milling_values(force_auto=True)

    def _load_milling_values(self, *, force_auto=False):
        spec = self.window.millingStockDialogSpec(force_auto=force_auto)
        if spec is not None:
            ox, oy, oz = self.window.millingStockOrigin()
            values = {
                "x_minus": spec.x_min - ox,
                "x_plus": spec.x_max - ox,
                "y_minus": spec.y_min - oy,
                "y_plus": spec.y_max - oy,
                "z_minus": spec.z_min - oz,
                "z_plus": spec.z_max - oz,
            }
            for key, spin in self.milling_fields.items():
                set_metric_value(spin, values[key])
        self.milling_manual.setChecked(False if force_auto else bool(getattr(self.window, "millingStockManual", False)))
        self._set_milling_manual(self.milling_manual.isChecked())
        set_metric_value(self.milling_allowance, float(getattr(self.window, "millingStockAllowance", 3.0)))
        self.milling_accuracy.setValue(int(getattr(self.window, "millingStockAccuracy", 2)))

    @staticmethod
    def _accuracy_index_for_resolution(resolution: float) -> int:
        return min(
            range(len(_ACCURACY_RESOLUTIONS)),
            key=lambda index: abs(_ACCURACY_RESOLUTIONS[index] - float(resolution)),
        )

    def resolution(self) -> float:
        return _ACCURACY_RESOLUTIONS[self.accuracy.value()]

    def _set_units(self, inches: bool):
        reset_pending = self._reset_turning_pending
        set_length_units(self._length_controls, bool(inches), suffix=True, context="StockDialog")
        self._reset_turning_pending = reset_pending

    def _set_milling_units(self, inches: bool):
        set_length_units(self._milling_length_controls, bool(inches), suffix=True, context="StockDialog")

    def showEvent(self, event):
        self._load_turning_values()
        self._reset_turning_pending = False
        self._load_milling_values()
        self._initial_values = {0: self._turning_values(), 1: self._milling_values()}
        self.stock_tabs.setCurrentIndex(0 if self.window.latheMode else 1)
        super().showEvent(event)

    def _load_turning_values(self, *, force_auto=False):
        self.enabled.setChecked(getattr(self.window, "stockEnabled", False))
        front_allowance = max(0.0, float(getattr(self.window, "turnStockFrontAllowance", 2.0)))
        suggestion = getattr(self.window, "_stock_auto_suggestion", None)
        use_auto = force_auto or not getattr(self.window, "_stock_manual_override", False)
        if use_auto and suggestion is not None:
            self._front_base_z = float(suggestion.front_z)
            set_metric_value(self.outer, max(0.01, float(suggestion.outer_diameter)))
            set_metric_value(self.inner, float(suggestion.inner_diameter))
            set_metric_value(self.length, max(0.01, float(suggestion.length) + front_allowance))
            set_metric_value(self.front_z, self._front_base_z + front_allowance)
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
            set_metric_value(self.front_z, manual_front)
        resolution = float(getattr(self.window, "turnStockResolution", 0.5))
        self.accuracy.setValue(self._accuracy_index_for_resolution(resolution))

    def _turning_value_changed(self, _value):
        self._reset_turning_pending = False

    def _reset_to_auto(self):
        self._load_turning_values(force_auto=True)
        self._reset_turning_pending = True

    def _milling_values(self):
        values = {key: metric_value(spin) for key, spin in self.milling_fields.items()}
        values.update(
            manual=self.milling_manual.isChecked(),
            allowance=metric_value(self.milling_allowance),
            resolution=self.window.millingStockResolution,
            accuracy=self.milling_accuracy.value(),
        )
        return values

    def _turning_values(self):
        front_z = metric_value(self.front_z)
        return {
            "enabled": self.enabled.isChecked(),
            "outer_diameter": metric_value(self.outer),
            "inner_diameter": metric_value(self.inner),
            "length": metric_value(self.length),
            "front_allowance": max(0.0, front_z - self._front_base_z),
            "front_z": front_z,
            "resolution": self.resolution(),
        }

    def _apply(self):
        tab = self.stock_tabs.currentIndex()
        values = self._milling_values() if tab == 1 else self._turning_values()
        try:
            if tab == 0 and self._reset_turning_pending:
                values["manual"] = False
                self.window.applyStockSettings(values)
            elif values != self._initial_values.get(tab):
                apply = self.window.applyMillingStockSettings if tab == 1 else self.window.applyStockSettings
                apply(values)
        except ValueError as exc:
            QMessageBox.warning(self, "Stock", str(exc))
            return
        self.accept()
