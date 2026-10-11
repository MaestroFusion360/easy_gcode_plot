"""Four physical settings for the detached stock STL export."""

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

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
        self.linear = self._spin(0.001, 1.0, self.settings.value("STOCK_STL/LINEAR", 0.1, type=float), 8)
        self.angular = self._spin(1.0, 90.0, self.settings.value("STOCK_STL/ANGULAR", 15.0, type=float), 1)
        self.angular.setSuffix("°")
        self.edge = self._spin(0.05, 100.0, self.settings.value("STOCK_STL/EDGE", 5.0, type=float), 8)
        form.addRow(self.tr("Maximum linear deviation"), self.linear)
        form.addRow(self.tr("Maximum angular deviation"), self.angular)
        form.addRow(self.tr("Maximum edge length"), self.edge)
        register_length_spinboxes((self.linear, self.edge))
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

    def options(self):
        return StockStlOptions(
            self.units.currentData(),
            round(metric_value(self.linear), 6),
            self.angular.value(),
            round(metric_value(self.edge), 6),
        ).validate()

    @staticmethod
    def get_options(window):
        dialog = StockStlExportDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        options = dialog.options()
        window.settings.setValue("STOCK_STL/UNITS", options.units)
        window.settings.setValue("STOCK_STL/LINEAR", options.linear_deviation)
        window.settings.setValue("STOCK_STL/ANGULAR", options.angular_deviation)
        window.settings.setValue("STOCK_STL/EDGE", options.edge_length)
        return options

    def tr(self, text):
        return QCoreApplication.translate("StockStlExportDialog", text)
