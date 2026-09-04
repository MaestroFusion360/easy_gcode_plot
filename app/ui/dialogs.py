"""Find/replace, export, CNC configuration and block-numbering dialogs."""

import copy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from app import get_version
from app.gcode.exporter import EXPANDED_MILL_PROGRAM_MODE, EXPANDED_TURN_PROGRAM_MODE
from app.ui.generated.about import Ui_AboutDlg
from app.ui.generated.block_num import Ui_BlockNumberDlg
from app.ui.generated.export import Ui_ExportOptDlg
from app.ui.generated.find_replace import Ui_Find
from app.ui.generated.milling_tools import Ui_MillingToolsDlg
from app.ui.generated.turning_tools import Ui_TurningToolsDlg
from app.ui.generated.wcs import Ui_WcsDlg


class About(QDialog):
    """Application information dialog."""

    def __init__(self, parent=None):
        """Initialize static application metadata and the runtime version."""
        super().__init__(parent)
        self.ui = Ui_AboutDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.ui.versionLabel.setText(f"Version: {get_version()}")


class BlockNum(QDialog):
    """Dialog for configuring block numbering parameters."""

    def __init__(self, parent=None):
        """Initialize the dialog with parent defaults and hook signals."""
        super().__init__(parent)
        self.ui = Ui_BlockNumberDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        self.ui.startSpinBox.setValue(self.parent().seqNumStart)
        self.ui.intervSpinBox.setValue(self.parent().seqNumIncr)

        if self.parent().seqNumSpacing == False:
            self.ui.spacingCmbBox.setCurrentIndex(0)
        else:
            self.ui.spacingCmbBox.setCurrentIndex(1)

        self.ui.startSpinBox.valueChanged.connect(self.startVal)
        self.ui.intervSpinBox.valueChanged.connect(self.incrVal)
        self.ui.spacingCmbBox.currentIndexChanged.connect(self.spaceVal)
        self.accepted.connect(lambda: self.parent().renumber())

    def startVal(self):
        """Store the starting sequence number chosen by the user."""
        self.parent().seqNumStart = self.ui.startSpinBox.value()

    def incrVal(self):
        """Store the increment size for subsequent sequence numbers."""
        self.parent().seqNumIncr = self.ui.intervSpinBox.value()

    def spaceVal(self, idx):
        """Update spacing preference between sequence number and code."""
        idx = self.ui.spacingCmbBox.currentIndex()
        if idx == 0:
            self.parent().seqNumSpacing = False
        else:
            self.parent().seqNumSpacing = True


class Export(QDialog):
    """Dialog for configuring export options before saving G-code."""

    def __init__(self, parent=None):
        """Set up export options dialog and load persisted settings."""
        super().__init__(parent)
        self.ui = Ui_ExportOptDlg()
        self.ui.setupUi(self)
        self._last_standard_lang = (
            self.parent().lang
            if self.parent().lang not in {EXPANDED_TURN_PROGRAM_MODE, EXPANDED_MILL_PROGRAM_MODE}
            else 0
        )
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        self.loadSettings()
        self.connectActions()
        self.set_expanded_turn_available(bool(self.parent().latheMode))

    def _set_parent_bool(self, combo, attr_name, true_index=1):
        """Update a boolean attribute on the parent using combo index."""
        setattr(self.parent(), attr_name, combo.currentIndex() == true_index)

    def _set_combo_from_bool(self, combo, value, true_index=1):
        """Set combo index based on a boolean value."""
        combo.setCurrentIndex(true_index if value else 0)

    def loadSettings(self):
        """Populate UI fields with current export preferences."""
        self.ui.langCmbBox.setCurrentIndex(self.parent().lang)

        self._set_combo_from_bool(self.ui.forceCmbBox, self.parent().forceAdr)

        self._set_combo_from_bool(self.ui.incrCmbBox, self.parent().incrMode)

        self.ui.startLineEdit.setText(self.parent().startPgmExp)
        self.ui.endLineEdit.setText(self.parent().endPgmExp)

        self._set_combo_from_bool(self.ui.safLineCmbBox, self.parent().safLine)
        self._set_combo_from_bool(self.ui.seqNumCmbBox, self.parent().seqNum)

        self.ui.seqStartSpinBox.setValue(self.parent().seqNumStart)
        self.ui.seqIntervalSpinBox.setValue(self.parent().seqNumIncr)

        self._set_combo_from_bool(self.ui.delimCmbBox, self.parent().delim)
        self._set_combo_from_bool(self.ui.leadingZeroCmbBox, self.parent().leadingZero)

    def connectActions(self):
        """Wire up dialog controls to parent setters."""
        self.accepted.connect(lambda: self.parent().export())
        self.ui.langCmbBox.currentIndexChanged.connect(self.lang)
        self.ui.forceCmbBox.currentIndexChanged.connect(self.forceAdr)
        self.ui.incrCmbBox.currentIndexChanged.connect(self.incrMode)
        self.ui.startLineEdit.textChanged.connect(self.startPgmText)
        self.ui.endLineEdit.textChanged.connect(self.endPgmText)
        self.ui.safLineCmbBox.currentIndexChanged.connect(self.safLine)
        self.ui.seqNumCmbBox.currentIndexChanged.connect(self.seqNum)
        self.ui.seqStartSpinBox.valueChanged.connect(self.seqNumStart)
        self.ui.seqIntervalSpinBox.valueChanged.connect(self.seqNumIncr)
        self.ui.delimCmbBox.currentIndexChanged.connect(self.delim)
        self.ui.leadingZeroCmbBox.currentIndexChanged.connect(self.ledingZero)

    def lang(self):
        """Update selected language and toggle related fields."""
        index = self.ui.langCmbBox.currentIndex()
        self.parent().lang = index
        if index not in {EXPANDED_TURN_PROGRAM_MODE, EXPANDED_MILL_PROGRAM_MODE}:
            self._last_standard_lang = index

        trace_shape_locked = index in {4, EXPANDED_TURN_PROGRAM_MODE, EXPANDED_MILL_PROGRAM_MODE}
        self.ui.forceCmbBox.setEnabled(not trace_shape_locked)
        self.ui.incrCmbBox.setEnabled(not trace_shape_locked)

    def set_expanded_turn_available(self, enabled: bool):
        """Enable exactly the expanded-program mode matching the current machine mode."""
        model = self.ui.langCmbBox.model()
        turn_item = model.item(EXPANDED_TURN_PROGRAM_MODE) if hasattr(model, "item") else None
        mill_item = model.item(EXPANDED_MILL_PROGRAM_MODE) if hasattr(model, "item") else None
        if turn_item is not None:
            turn_item.setEnabled(enabled)
        if mill_item is not None:
            mill_item.setEnabled(not enabled)

        current = self.ui.langCmbBox.currentIndex()
        invalid_expanded = (not enabled and current == EXPANDED_TURN_PROGRAM_MODE) or (
            enabled and current == EXPANDED_MILL_PROGRAM_MODE
        )
        if invalid_expanded:
            fallback = self._last_standard_lang
            if fallback in {EXPANDED_TURN_PROGRAM_MODE, EXPANDED_MILL_PROGRAM_MODE} or fallback < 0:
                fallback = 0
            self.ui.langCmbBox.setCurrentIndex(fallback)

    def forceAdr(self, idx):
        """Toggle forced address formatting on export."""
        self._set_parent_bool(self.ui.forceCmbBox, "forceAdr")

    def incrMode(self, idx):
        """Switch between absolute and incremental address modes."""
        self._set_parent_bool(self.ui.incrCmbBox, "incrMode")

    def startPgmText(self):
        """Capture custom program start text."""
        self.parent().startPgmExp = self.ui.startLineEdit.text()

    def endPgmText(self):
        """Capture custom program end text."""
        self.parent().endPgmExp = self.ui.endLineEdit.text()

    def safLine(self, idx):
        """Toggle inserting a safety line at program start."""
        self._set_parent_bool(self.ui.safLineCmbBox, "safLine")

    def seqNum(self, idx):
        """Enable or disable sequence numbering for export."""
        self._set_parent_bool(self.ui.seqNumCmbBox, "seqNum")

    def seqNumStart(self):
        """Store starting sequence number for export."""
        self.parent().seqNumStart = self.ui.seqStartSpinBox.value()

    def seqNumIncr(self):
        """Store sequence number increment for export."""
        self.parent().seqNumIncr = self.ui.seqIntervalSpinBox.value()

    def delim(self, idx):
        """Switch delimiter between addresses based on selection."""
        self._set_parent_bool(self.ui.delimCmbBox, "delim")

    def ledingZero(self, idx):
        """Toggle leading zero formatting for addresses."""
        self._set_parent_bool(self.ui.leadingZeroCmbBox, "leadingZero")


class Find(QDialog):
    """Dialog providing find/replace utilities for the editor."""

    def __init__(self, parent=None):
        """Configure dialog and connect buttons to parent handlers."""
        super().__init__(parent)
        self.ui = Ui_Find()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.findReplaceActions()

    def findReplaceActions(self):
        """Attach UI actions to parent find/replace callbacks."""

        self.ui.btnFind.clicked.connect(
            lambda: self.parent().find(
                self.ui.lineEditFind.text(),
                self.ui.checkCase.isChecked(),
                self.ui.checkWholeWord.isChecked(),
                self.ui.checkWrapAround.isChecked(),
            )
        )
        self.ui.btnReplace.clicked.connect(
            lambda: self.parent().replace(
                self.ui.lineEditFind.text(),
                self.ui.lineEditReplace.text(),
                self.ui.checkCase.isChecked(),
                self.ui.checkWholeWord.isChecked(),
                self.ui.checkWrapAround.isChecked(),
            )
        )
        self.ui.btnReplaceAll.clicked.connect(
            lambda: self.parent().replaceAll(
                self.ui.lineEditFind.text(),
                self.ui.lineEditReplace.text(),
                self.ui.checkCase.isChecked(),
                self.ui.checkWholeWord.isChecked(),
            )
        )


class Wcs(QDialog):
    """Dialog for configuring G54-G59 XYZ offsets and the G28 home position."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_WcsDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.accepted.connect(self.applyValues)
        self.loadValues()

    def showEvent(self, event):
        """Reload current values whenever the dialog is opened."""
        self.loadValues()
        super().showEvent(event)

    def loadValues(self):
        """Populate controls from the parent CNC configuration."""
        offsets = getattr(self.parent(), "wcsOffsets", {})
        for code in range(54, 60):
            values = offsets.get(code, (0.0, 0.0, 0.0))
            if len(values) == 2:
                x, z = values
                y = 0.0
            else:
                x, y, z = values
            getattr(self.ui, f"g{code}X").setValue(float(x))
            getattr(self.ui, f"g{code}Y").setValue(float(y))
            getattr(self.ui, f"g{code}Z").setValue(float(z))
        for axis, attr in (("X", "xPosMach"), ("Y", "yPosMach"), ("Z", "zPosMach")):
            getattr(self.ui, f"home{axis}").setValue(float(getattr(self.parent(), attr, 0.0)))
        self.ui.homeConfiguredCheck.setChecked(bool(getattr(self.parent(), "homeConfigured", True)))

    def applyValues(self):
        """Store XYZ WCS and G28 values on the main window and refresh the trace."""
        self.parent().wcsOffsets = {
            code: (
                getattr(self.ui, f"g{code}X").value(),
                getattr(self.ui, f"g{code}Y").value(),
                getattr(self.ui, f"g{code}Z").value(),
            )
            for code in range(54, 60)
        }
        for axis, attr in (("X", "xPosMach"), ("Y", "yPosMach"), ("Z", "zPosMach")):
            setattr(self.parent(), attr, getattr(self.ui, f"home{axis}").value())
        self.parent().homeConfigured = self.ui.homeConfiguredCheck.isChecked()
        self.parent().updateData()


class _TurningToolEditor(QDialog):
    """Small Add/Edit dialog for FANUC turning tool definitions."""

    def __init__(self, parent=None, tool_code=None, spec=None):
        super().__init__(parent)
        spec = spec or {}
        self.setWindowTitle("Edit Tool" if tool_code else "Add Tool")
        self.setModal(True)
        self.setMinimumWidth(400)

        form = QFormLayout()
        self.toolCode = QLineEdit(tool_code or "T0101", self)
        self.toolType = QComboBox(self)
        self.toolType.addItems(["turning", "drill"])
        self.toolType.setCurrentText(str(spec.get("type", "turning")))
        self.noseRadius = QDoubleSpinBox(self)
        self.noseRadius.setDecimals(3)
        self.noseRadius.setRange(0.001, 999999.999)
        self.noseRadius.setValue(float(spec.get("noseRadius", 0.4)))
        self.tipOrientation = QComboBox(self)
        self.tipOrientation.addItems([f"P{value}" for value in range(1, 10)])
        self.tipOrientation.setCurrentText(f"P{int(spec.get('tipOrientation', 1))}")
        self.description = QLineEdit(str(spec.get("description", "")), self)

        form.addRow("T code", self.toolCode)
        form.addRow("Type", self.toolType)
        form.addRow("Nose radius, mm", self.noseRadius)
        form.addRow("Tip orientation", self.tipOrientation)
        form.addRow("Description", self.description)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttonBox.accepted.connect(self.validateAndAccept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttonBox)
        self.toolType.currentTextChanged.connect(self.updateTurningFields)
        self.updateTurningFields(self.toolType.currentText())
        self.toolCode.selectAll()
        self.toolCode.setFocus()

    def updateTurningFields(self, tool_type):
        """Enable nose data only for turning tools."""
        enabled = tool_type == "turning"
        self.noseRadius.setEnabled(enabled)
        self.tipOrientation.setEnabled(enabled)

    def validateAndAccept(self):
        """Validate the FANUC T word before accepting the editor."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or not 1 <= len(digits) <= 4:
            QMessageBox.warning(self, "Turning Tools", "T code must contain 1 to 4 digits.")
            return
        self.accept()

    def value(self):
        """Return normalized tool code and specification."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits):04d}"
        tool_type = self.toolType.currentText()
        spec = {"type": tool_type}
        description = " ".join(self.description.text().split())
        if description:
            spec["description"] = description
        if tool_type == "turning":
            spec["noseRadius"] = self.noseRadius.value()
            spec["tipOrientation"] = self.tipOrientation.currentIndex() + 1
        return key, spec


class TurningTools(QDialog):
    """Dialog for editing turning tool-nose compensation definitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_TurningToolsDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.pendingTools = {}
        self.ui.addButton.clicked.connect(self.addTool)
        self.ui.editButton.clicked.connect(self.editTool)
        self.ui.removeButton.clicked.connect(self.removeTool)
        self.ui.toolTable.doubleClicked.connect(self.editTool)
        self.accepted.connect(self.applyValues)
        self.loadValues()

    def showEvent(self, event):
        """Discard stale pending edits and reload the current tool table."""
        self.loadValues()
        super().showEvent(event)

    def loadValues(self):
        """Copy the current tool map into the dialog editing buffer."""
        self.pendingTools = copy.deepcopy(getattr(self.parent(), "tools", {}))
        self.refreshTable()

    def refreshTable(self, selected_key=None):
        """Rebuild the visible table from the pending tool map."""
        table = self.ui.toolTable
        table.setRowCount(0)
        selected_row = -1
        for row, key in enumerate(sorted(self.pendingTools)):
            spec = self.pendingTools[key]
            is_turning = spec.get("type") == "turning"
            orientation = f"P{int(spec.get('tipOrientation', 1))}" if is_turning else "—"
            radius = f"{float(spec.get('noseRadius', 0.0)):g}" if is_turning else "—"
            values = (
                orientation,
                key,
                "Turning tool" if is_turning else "Drill",
                radius,
                str(spec.get("description", "")),
            )
            table.insertRow(row)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
            if key == selected_key:
                selected_row = row
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            table.selectRow(selected_row)

    def selectedTool(self):
        """Return the T code from the selected table row."""
        row = self.ui.toolTable.currentRow()
        if row < 0:
            return None
        item = self.ui.toolTable.item(row, 1)
        return item.text() if item is not None else None

    def addTool(self):
        """Open the tool editor for a new definition."""
        editor = _TurningToolEditor(self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        key, spec = editor.value()
        self.pendingTools[key] = spec
        self.refreshTable(key)

    def editTool(self, *_args):
        """Edit the currently selected tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        editor = _TurningToolEditor(self, key, self.pendingTools[key])
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        new_key, spec = editor.value()
        if new_key != key:
            self.pendingTools.pop(key, None)
        self.pendingTools[new_key] = spec
        self.refreshTable(new_key)

    def removeTool(self):
        """Remove the selected pending tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        self.pendingTools.pop(key, None)
        self.refreshTable()

    def applyValues(self):
        """Commit the tool table to the main window and refresh the trace."""
        self.parent().tools = copy.deepcopy(self.pendingTools)
        self.parent().updateData()


_MILLING_TOOL_TYPES = {
    "mill_flat": "Mill Flat",
    "mill_bull": "Mill Bull",
    "mill_ball": "Mill Ball",
    "drill": "Drill",
}


class _MillingToolEditor(QDialog):
    """Add/Edit dialog for milling tool geometry."""

    def __init__(self, parent=None, tool_code=None, spec=None):
        super().__init__(parent)
        spec = spec or {}
        self.setWindowTitle("Edit Milling Tool" if tool_code else "Add Milling Tool")
        self.setModal(True)
        self.setMinimumWidth(420)

        form = QFormLayout()
        self.toolCode = QLineEdit(tool_code or "T1", self)
        self.toolType = QComboBox(self)
        for key, label in _MILLING_TOOL_TYPES.items():
            self.toolType.addItem(label, key)
        type_index = self.toolType.findData(str(spec.get("type", "mill_flat")))
        self.toolType.setCurrentIndex(max(0, type_index))

        self.diameter = QDoubleSpinBox(self)
        self.diameter.setDecimals(3)
        self.diameter.setRange(0.0, 10000.0)
        self.diameter.setValue(float(spec.get("diameter", 0.0)))

        self.cornerRadius = QDoubleSpinBox(self)
        self.cornerRadius.setDecimals(3)
        self.cornerRadius.setRange(0.0, 10000.0)
        self.cornerRadius.setValue(float(spec.get("cornerRadius", 0.0)))

        self.length = QDoubleSpinBox(self)
        self.length.setDecimals(3)
        self.length.setRange(0.0, 10000.0)
        self.length.setValue(float(spec.get("length", 0.0)))

        self.description = QLineEdit(str(spec.get("description", "")), self)

        form.addRow("T code", self.toolCode)
        form.addRow("Type", self.toolType)
        form.addRow("Diameter, mm", self.diameter)
        form.addRow("Corner radius, mm", self.cornerRadius)
        form.addRow("Length, mm", self.length)
        form.addRow("Description", self.description)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttonBox.accepted.connect(self.validateAndAccept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttonBox)

        self.toolType.currentIndexChanged.connect(self.updateRadiusField)
        self.diameter.valueChanged.connect(self.updateBallRadius)
        self.updateRadiusField()
        self.toolCode.selectAll()
        self.toolCode.setFocus()

    def currentType(self):
        """Return the stable milling tool type key."""
        return str(self.toolType.currentData())

    def updateRadiusField(self, *_args):
        """Match CNCEditor radius rules for flat, bull, ball and drill tools."""
        tool_type = self.currentType()
        self.cornerRadius.setEnabled(tool_type == "mill_bull")
        if tool_type == "mill_ball":
            self.cornerRadius.setValue(self.diameter.value() / 2.0)
        elif tool_type != "mill_bull":
            self.cornerRadius.setValue(0.0)

    def updateBallRadius(self, *_args):
        """Keep ball radius equal to half of tool diameter."""
        if self.currentType() == "mill_ball":
            self.cornerRadius.setValue(self.diameter.value() / 2.0)

    def validateAndAccept(self):
        """Validate a compact FANUC T word before accepting the editor."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or not 1 <= len(digits) <= 4 or int(digits) <= 0:
            QMessageBox.warning(self, "Milling Tools", "T code must contain 1 to 4 non-zero digits.")
            return
        self.accept()

    def value(self):
        """Return normalized tool code and milling geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits):04d}"
        tool_type = self.currentType()
        diameter = self.diameter.value()
        radius = self.cornerRadius.value()
        if tool_type == "mill_ball":
            radius = diameter / 2.0
        elif tool_type != "mill_bull":
            radius = 0.0
        spec = {
            "type": tool_type,
            "diameter": diameter,
            "cornerRadius": radius,
            "length": self.length.value(),
        }
        description = " ".join(self.description.text().split())
        if description:
            spec["description"] = description
        return key, spec


class MillingTools(QDialog):
    """Dialog for milling tool geometry stored independently from turning tools."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MillingToolsDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.pendingTools = {}
        self.ui.addButton.clicked.connect(self.addTool)
        self.ui.editButton.clicked.connect(self.editTool)
        self.ui.removeButton.clicked.connect(self.removeTool)
        self.ui.toolTable.doubleClicked.connect(self.editTool)
        self.accepted.connect(self.applyValues)
        self.loadValues()

    def showEvent(self, event):
        """Reload saved milling data whenever the dialog is opened."""
        self.loadValues()
        super().showEvent(event)

    def loadValues(self):
        """Copy current milling tool data into the dialog editing buffer."""
        self.pendingTools = copy.deepcopy(getattr(self.parent(), "millingTools", {}))
        self.refreshTable()

    def refreshTable(self, selected_key=None):
        """Rebuild the visible milling tool table."""
        table = self.ui.toolTable
        table.setRowCount(0)
        selected_row = -1
        for row, key in enumerate(sorted(self.pendingTools)):
            spec = self.pendingTools[key]
            tool_type = str(spec.get("type", "mill_flat"))
            values = (
                key,
                _MILLING_TOOL_TYPES.get(tool_type, "Mill Flat"),
                f"{float(spec.get('diameter', 0.0)):g}",
                f"{float(spec.get('cornerRadius', 0.0)):g}",
                f"{float(spec.get('length', 0.0)):g}",
                str(spec.get("description", "")),
            )
            table.insertRow(row)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
            if key == selected_key:
                selected_row = row
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            table.selectRow(selected_row)

    def selectedTool(self):
        """Return the selected normalized T code."""
        row = self.ui.toolTable.currentRow()
        if row < 0:
            return None
        item = self.ui.toolTable.item(row, 0)
        return item.text() if item is not None else None

    def addTool(self):
        """Add a milling tool definition."""
        editor = _MillingToolEditor(self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        key, spec = editor.value()
        self.pendingTools[key] = spec
        self.refreshTable(key)

    def editTool(self, *_args):
        """Edit the selected milling tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        editor = _MillingToolEditor(self, key, self.pendingTools[key])
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        new_key, spec = editor.value()
        if new_key != key:
            self.pendingTools.pop(key, None)
        self.pendingTools[new_key] = spec
        self.refreshTable(new_key)

    def removeTool(self):
        """Remove the selected milling tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        self.pendingTools.pop(key, None)
        self.refreshTable()

    def applyValues(self):
        """Store milling tool data without changing or rebuilding the trace."""
        self.parent().millingTools = copy.deepcopy(self.pendingTools)
