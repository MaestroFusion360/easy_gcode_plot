"""Choose FANUC table slots for the current program's named tools."""

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QMessageBox, QSpinBox

from app.gcode.export.common import ExportLimitation
from app.gcode.export.tool_numbers import target_tool_numbers
from app.gcode.post_profiles import load_post_profile


class ExportToolNumbersDialog(QDialog):
    """Keep source names visible while choosing target numeric addresses."""

    def __init__(self, parent, result, profile, current):
        super().__init__(parent)
        self.setWindowTitle("FANUC Tool Numbers")
        self._result = result
        self._profile = profile
        defaults = target_tool_numbers(result, profile)
        layout = QFormLayout(self)
        layout.addRow(QLabel("Assign a FANUC tool-table number to each named tool.", self))
        self.fields = {}
        for name, default in defaults.items():
            field = QSpinBox(self)
            field.setRange(1, 99)
            field.setPrefix("T")
            field.setValue(current.get(name, int(default[1:])))
            self.fields[name] = field
            layout.addRow(name, field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def value(self):
        """Return source identity to target slot assignments."""
        return {name: field.value() for name, field in self.fields.items()}

    def accept(self):
        try:
            target_tool_numbers(self._result, self._profile, self.value())
        except ExportLimitation as error:
            QMessageBox.warning(self, "FANUC Tool Numbers", str(error))
            return
        super().accept()


def select_tool_numbers(parent, result, target, current):
    """Ask only when this target needs numbers for actual named tool changes."""
    if target is None:
        return {}
    profile = load_post_profile(target)
    if not target_tool_numbers(result, profile):
        return {}
    dialog = ExportToolNumbersDialog(parent, result, profile, current)
    return dialog.value() if dialog.exec() == QDialog.DialogCode.Accepted else None
