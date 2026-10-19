"""Four physical settings for the detached stock STL export."""

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

from app.gcode.stock.milling_stock_stl import StockStlOptions
from app.ui.support.units import metric_value, register_length_spinboxes, set_length_units


class StockStlExportDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.settings = window.settings
        self.setWindowTitle(self.tr("STL export parameters"))
        form = QFormLayout(self)
        self.units = QComboBox(self)
        self.units.addItem(self.tr("Millimeters"), "mm")
        self.units.addItem(self.tr("Inches"), "in")
        form.addRow(self.tr("Length units"), self.units)
        item = getattr(window, "_milling_stock_item", None)
        surface_error = getattr(item, "surface_error", 0.1)
        edge_error = getattr(item, "edge_error", 0.25)
        self.calculated = QCheckBox(self.tr("Use calculated stock without mesh refinement"), self)
        self.calculated.setToolTip(self.tr("Large STL meshes are simplified automatically."))
        self.calculated.setChecked(True)
        form.addRow(self.calculated)
        self.linear = self._spin(0.001, 1.0, surface_error, 8)
        self.angular = self._spin(1.0, 90.0, 90.0, 1)
        self.angular.setSuffix("°")
        self.edge = self._spin(0.05, 100.0, edge_error, 8)
        form.addRow(self.tr("Maximum linear deviation"), self.linear)
        form.addRow(self.tr("Maximum angular deviation"), self.angular)
        form.addRow(self.tr("Maximum edge length"), self.edge)
        register_length_spinboxes((self.linear, self.edge))
        self.angular.setToolTip(self.tr("Stock calculation has no separate angular tolerance."))
        self.calculated.toggled.connect(self._set_refinement)
        self._set_refinement(True)
        self.units.currentIndexChanged.connect(self._set_units)
        self.units.setCurrentIndex(1 if self.settings.value("STOCK_STL/UNITS", "mm") == "in" else 0)
        self._set_units()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setMinimumWidth(420)

    def _spin(self, low, high, default, decimals):
        spin = QDoubleSpinBox(self)
        spin.setDecimals(decimals)
        spin.setRange(low, high)
        spin.setValue(default)
        return spin

    def _set_units(self):
        inches = self.units.currentData() == "in"
        set_length_units((self.linear, self.edge), inches, suffix=True)
        for spin in (self.linear, self.edge):
            spin.setDecimals(8 if inches else 6)

    def _set_refinement(self, calculated):
        for spin in (self.linear, self.angular, self.edge):
            spin.setEnabled(not calculated)

    def options(self):
        return StockStlOptions(
            self.units.currentData(),
            round(metric_value(self.linear), 6),
            self.angular.value(),
            round(metric_value(self.edge), 6),
            calculated=self.calculated.isChecked(),
        ).validate()

    @staticmethod
    def get_options(window):
        dialog = StockStlExportDialog(window)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            options = dialog.options()
            window.settings.setValue("STOCK_STL/UNITS", options.units)
            window.settings.setValue("STOCK_STL/LINEAR", options.linear_deviation)
            window.settings.setValue("STOCK_STL/ANGULAR", options.angular_deviation)
            window.settings.setValue("STOCK_STL/EDGE", options.edge_length)
            return options
        finally:
            dialog.deleteLater()

    def tr(self, text):
        return QCoreApplication.translate("StockStlExportDialog", text)
