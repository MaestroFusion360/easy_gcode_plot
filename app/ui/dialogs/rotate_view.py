"""Angle and world-axis selection for rotating a fixed milling view."""

from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QVBoxLayout


class RotateViewDialog(QDialog):
    def __init__(self, parent, axis="Z"):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Rotate view"))
        self.setWindowIcon(parent.ui.actionRotateView.icon())
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.angle = QDoubleSpinBox(self)
        self.angle.setObjectName("rotationAngleSpin")
        self.angle.setRange(-36000, 36000)
        self.angle.setDecimals(3)
        self.angle.setSingleStep(90)
        self.angle.setValue(90)
        self.axis = QComboBox(self)
        self.axis.setObjectName("rotationAxisCombo")
        self.axis.addItems(["X", "Y", "Z"])
        self.axis.setCurrentText(axis)
        form.addRow(self.tr("Angle, deg"), self.angle)
        form.addRow(self.tr("Axis"), self.axis)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.angle.selectAll()
        self.angle.setFocus()
