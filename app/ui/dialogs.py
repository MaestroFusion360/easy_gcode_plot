"""Find/replace, export, CNC configuration and block-numbering dialogs."""

import copy

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from app import get_version
from app.gcode.exporter import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
)
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

        self.loadSettings()
        self.accepted.connect(self._apply_and_renumber)

    def showEvent(self, event):
        self.loadSettings()
        super().showEvent(event)

    def loadSettings(self):
        self.ui.startSpinBox.setValue(self.parent().seqNumStart)
        self.ui.intervSpinBox.setValue(self.parent().seqNumIncr)
        self.ui.spacingCmbBox.setCurrentIndex(1 if self.parent().seqNumSpacing else 0)

    def _apply_and_renumber(self):
        self.startVal()
        self.incrVal()
        self.spaceVal(self.ui.spacingCmbBox.currentIndex())
        self.parent().renumber()

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
    """Dialog for configuring export type and output representation."""

    _MODE_LABELS = (
        "TURN FULL PROGRAM",
        "MILL FULL PROGRAM",
        "EXPANDED EXECUTION",
        "PLOT DATA",
        "DXF",
    )
    _ARC_LABELS = (
        "IJK RELATIVE",
        "IJK ABSOLUTE",
        "R RADIUS",
        "LINEARIZED",
    )

    def __init__(self, parent=None):
        """Set up export options dialog and load persisted settings."""
        super().__init__(parent)
        self.ui = Ui_ExportOptDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self._configure_export_mode_ui()
        self.loadSettings()
        self.connectActions()
        self.sync_mode_availability(bool(self.parent().latheMode))

    def _configure_export_mode_ui(self):
        """Separate export type from coordinate and arc representation options."""
        self.ui.label_Lang.setText("Export Type")
        self.ui.langCmbBox.clear()
        self.ui.langCmbBox.addItems(self._MODE_LABELS)

        self.ui.label_Incr.setText("Coordinates")
        self.ui.incrCmbBox.setItemText(0, "G90 Absolute")
        self.ui.incrCmbBox.setItemText(1, "G91 Incremental")

        grid = self.ui.gridLayout
        grid.removeWidget(self.ui.label_Incr)
        grid.removeWidget(self.ui.incrCmbBox)
        grid.addWidget(self.ui.label_Incr, 11, 0)
        grid.addWidget(self.ui.incrCmbBox, 11, 1)

        self.arcOutputLabel = QLabel("Arc Output", self)
        self.arcOutputCmbBox = QComboBox(self)
        self.arcOutputCmbBox.addItems(self._ARC_LABELS)
        grid.addWidget(self.arcOutputLabel, 12, 0)
        grid.addWidget(self.arcOutputCmbBox, 12, 1)
        self.setMinimumHeight(max(self.minimumHeight(), 430))

    def _set_parent_bool(self, combo, attr_name, true_index=1):
        """Update a boolean attribute on the parent using combo index."""
        setattr(self.parent(), attr_name, combo.currentIndex() == true_index)

    def _set_combo_from_bool(self, combo, value, true_index=1):
        """Set combo index based on a boolean value."""
        combo.setCurrentIndex(true_index if value else 0)

    def loadSettings(self):
        """Populate UI fields with current export preferences."""
        self.ui.langCmbBox.setCurrentIndex(self.parent().exportMode)
        self.arcOutputCmbBox.setCurrentIndex(self.parent().exportArcMode)
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
        self._sync_output_option_availability()

    def connectActions(self):
        """Keep edits local until OK; Cancel leaves application settings unchanged."""
        self.accepted.connect(self._apply_and_export)
        self.ui.langCmbBox.currentIndexChanged.connect(lambda _index: self._sync_output_option_availability())

    def showEvent(self, event):
        self.loadSettings()
        self.sync_mode_availability(bool(self.parent().latheMode))
        super().showEvent(event)

    def _apply_and_export(self):
        self.exportMode()
        self.arcMode()
        self.forceAdr(self.ui.forceCmbBox.currentIndex())
        self.incrMode(self.ui.incrCmbBox.currentIndex())
        self.startPgmText()
        self.endPgmText()
        self.safLine(self.ui.safLineCmbBox.currentIndex())
        self.seqNum(self.ui.seqNumCmbBox.currentIndex())
        self.seqNumStart()
        self.seqNumIncr()
        self.delim(self.ui.delimCmbBox.currentIndex())
        self.ledingZero(self.ui.leadingZeroCmbBox.currentIndex())
        self.parent().export()

    def exportMode(self):
        """Store the selected logical export type."""
        self.parent().exportMode = self.ui.langCmbBox.currentIndex()
        self._sync_output_option_availability()

    def arcMode(self):
        """Store the arc representation used by expanded execution output."""
        self.parent().exportArcMode = self.arcOutputCmbBox.currentIndex()

    def _sync_output_option_availability(self):
        """Enable only options consumed by the selected exporter."""
        dxf = self.ui.langCmbBox.currentIndex() == DXF_MODE
        gcode_only_controls = (
            (self.ui.label_StartText, self.ui.startLineEdit),
            (self.ui.label_EndText, self.ui.endLineEdit),
            (self.ui.label_SafLine, self.ui.safLineCmbBox),
            (self.ui.label_SeqNum, self.ui.seqNumCmbBox),
            (self.ui.label_seqStart, self.ui.seqStartSpinBox),
            (self.ui.label_seqInterval, self.ui.seqIntervalSpinBox),
            (self.ui.label_Delim, self.ui.delimCmbBox),
            (self.ui.labelLeadingZero, self.ui.leadingZeroCmbBox),
        )
        for label, control in gcode_only_controls:
            label.setEnabled(not dxf)
            control.setEnabled(not dxf)

        converted = self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE
        self.ui.labelForce.setEnabled(converted)
        self.ui.forceCmbBox.setEnabled(converted)
        self.ui.label_Incr.setEnabled(converted)
        self.ui.incrCmbBox.setEnabled(converted)
        self.arcOutputLabel.setEnabled(converted)
        self.arcOutputCmbBox.setEnabled(converted)

    def sync_mode_availability(self, turning: bool):
        """Enable exactly the full-program mode matching the active machine profile."""
        model = self.ui.langCmbBox.model()
        turn_item = model.item(TURN_FULL_PROGRAM_MODE) if hasattr(model, "item") else None
        mill_item = model.item(MILL_FULL_PROGRAM_MODE) if hasattr(model, "item") else None
        if turn_item is not None:
            turn_item.setEnabled(turning)
        if mill_item is not None:
            mill_item.setEnabled(not turning)

        current = self.ui.langCmbBox.currentIndex()
        invalid = (not turning and current == TURN_FULL_PROGRAM_MODE) or (turning and current == MILL_FULL_PROGRAM_MODE)
        if invalid:
            self.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
        self._sync_output_option_availability()

    def forceAdr(self, idx):
        """Toggle forced address formatting on export."""
        del idx
        self._set_parent_bool(self.ui.forceCmbBox, "forceAdr")

    def incrMode(self, idx):
        """Switch between absolute and incremental output coordinates."""
        del idx
        self._set_parent_bool(self.ui.incrCmbBox, "incrMode")

    def startPgmText(self):
        """Capture custom program start text."""
        self.parent().startPgmExp = self.ui.startLineEdit.text()

    def endPgmText(self):
        """Capture custom program end text."""
        self.parent().endPgmExp = self.ui.endLineEdit.text()

    def safLine(self, idx):
        """Toggle inserting a safety line at program start."""
        del idx
        self._set_parent_bool(self.ui.safLineCmbBox, "safLine")

    def seqNum(self, idx):
        """Enable or disable sequence numbering for export."""
        del idx
        self._set_parent_bool(self.ui.seqNumCmbBox, "seqNum")

    def seqNumStart(self):
        """Store starting sequence number for export."""
        self.parent().seqNumStart = self.ui.seqStartSpinBox.value()

    def seqNumIncr(self):
        """Store sequence number increment for export."""
        self.parent().seqNumIncr = self.ui.seqIntervalSpinBox.value()

    def delim(self, idx):
        """Switch delimiter between addresses based on selection."""
        del idx
        self._set_parent_bool(self.ui.delimCmbBox, "delim")

    def ledingZero(self, idx):
        """Toggle leading zero formatting for addresses."""
        del idx
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
        for value in range(1, 10):
            self.tipOrientation.addItem(
                QIcon(f":/resource/icons/orientation_box/P{value}.png"),
                f"P{value}",
            )
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
                item = QTableWidgetItem(value)
                if column == 0 and is_turning:
                    item.setIcon(QIcon(f":/resource/icons/orientation_box/P{int(spec.get('tipOrientation', 1))}.png"))
                table.setItem(row, column, item)
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
        """Accept only valid compact tool numbers and physical geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or digits.startswith("0") or not 1 <= int(digits) <= 99:
            QMessageBox.warning(self, "Milling Tools", "T code must be T1-T99 without leading zeros.")
            return
        if self.diameter.value() <= 0.0 or self.length.value() <= 0.0:
            QMessageBox.warning(self, "Milling Tools", "Diameter and length must be greater than zero.")
            return
        if self.currentType() == "mill_bull" and self.cornerRadius.value() > self.diameter.value() / 2.0:
            QMessageBox.warning(self, "Milling Tools", "Bull corner radius cannot exceed half the diameter.")
            return
        self.accept()

    def value(self):
        """Return compact T1-T99 tool code and milling geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits)}"
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
        """Store milling tool data and rebuild the trace with the new cutter geometry."""
        self.parent().millingTools = copy.deepcopy(self.pendingTools)
        self.parent().updateData()
