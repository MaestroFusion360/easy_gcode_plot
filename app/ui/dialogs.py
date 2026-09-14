"""General application dialogs unrelated to tool-library editing."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QLabel

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
from app.ui.generated.wcs import Ui_WcsDlg
from app.ui.tool_dialogs import MillingTools, TurningTools, _export_tool_file, _TurningToolEditor

__all__ = (
    "About",
    "BlockNum",
    "Export",
    "Find",
    "Wcs",
    "TurningTools",
    "MillingTools",
    "_TurningToolEditor",
    "_export_tool_file",
)


class About(QDialog):
    """Application information dialog."""

    def __init__(self, parent=None):
        """Initialize static application metadata and the runtime version."""
        super().__init__(parent)
        self.ui = Ui_AboutDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        version = get_version()
        self.ui.versionLabel.setText(f"Version: {version}")
        self.ui.descriptionLabel.setText(
            "Easy G-code Plot is a FANUC/ISO G-code viewer, editor, analyzer and verifier "
            f"for turning and milling. Version {version} includes a shared native Python CNC "
            "kernel, authoritative logical Motion Trace, Macro B/control flow, turning cycles, "
            "native XYZ milling, trajectory playback/picking and source-aware expanded program "
            "export for both machine modes."
        )


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
        turning_expanded = converted and bool(self.parent().latheMode)
        self.ui.labelForce.setEnabled(converted)
        self.ui.forceCmbBox.setEnabled(converted)
        self.ui.label_Incr.setEnabled(converted)
        self.ui.incrCmbBox.setEnabled(converted)
        self.arcOutputLabel.setEnabled(converted and not turning_expanded)
        self.arcOutputCmbBox.setEnabled(converted and not turning_expanded)

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
        lathe = bool(getattr(self.parent(), "latheMode", False))
        x_ui_scale = 2.0 if lathe else 1.0
        offsets = getattr(self.parent(), "wcsOffsets", {})
        for code in range(54, 60):
            values = offsets.get(code, (0.0, 0.0, 0.0))
            if len(values) == 2:
                x, z = values
                y = 0.0
            else:
                x, y, z = values
            getattr(self.ui, f"g{code}X").setValue(float(x) * x_ui_scale)
            y_input = getattr(self.ui, f"g{code}Y")
            y_input.setValue(float(y))
            y_input.setEnabled(not lathe)
            getattr(self.ui, f"g{code}Z").setValue(float(z))
        for axis, attr in (("X", "xPosMach"), ("Y", "yPosMach"), ("Z", "zPosMach")):
            scale = x_ui_scale if axis == "X" else 1.0
            control = getattr(self.ui, f"home{axis}")
            control.setValue(float(getattr(self.parent(), attr, 0.0)) * scale)
            if axis == "Y":
                control.setEnabled(not lathe)
        self.ui.yHeader.setEnabled(not lathe)
        self.ui.homeConfiguredCheck.setChecked(bool(getattr(self.parent(), "homeConfigured", True)))

    def applyValues(self):
        """Store XYZ WCS and G28 values on the main window and refresh the trace."""
        x_ui_scale = 2.0 if bool(getattr(self.parent(), "latheMode", False)) else 1.0
        self.parent().wcsOffsets = {
            code: (
                getattr(self.ui, f"g{code}X").value() / x_ui_scale,
                getattr(self.ui, f"g{code}Y").value(),
                getattr(self.ui, f"g{code}Z").value(),
            )
            for code in range(54, 60)
        }
        for axis, attr in (("X", "xPosMach"), ("Y", "yPosMach"), ("Z", "zPosMach")):
            scale = x_ui_scale if axis == "X" else 1.0
            setattr(self.parent(), attr, getattr(self.ui, f"home{axis}").value() / scale)
        self.parent().homeConfigured = self.ui.homeConfiguredCheck.isChecked()
        self.parent().updateData()
