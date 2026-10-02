"""General application dialogs unrelated to tool-library editing."""

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QLabel

from app import get_version
from app.gcode.export import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
)
from app.gcode.source_mode import SOURCE_DIALECT_FANUC, SOURCE_DIALECT_SINUMERIK, source_dialect_for_path
from app.ui.generated.dialogs.about import Ui_AboutDlg
from app.ui.generated.dialogs.block_num import Ui_BlockNumberDlg
from app.ui.generated.dialogs.export import Ui_ExportOptDlg
from app.ui.generated.dialogs.find_replace import Ui_Find
from app.ui.generated.dialogs.wcs import Ui_WcsDlg
from app.ui.support.units import metric_value, register_length_spinboxes, set_length_units, set_metric_value

__all__ = (
    "About",
    "BlockNum",
    "Export",
    "Find",
    "Wcs",
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
        self.ui.versionLabel.setText(
            QCoreApplication.translate("AboutDlg", "Version: {version}").format(version=version)
        )
        self.ui.descriptionLabel.setText(
            QCoreApplication.translate(
                "AboutDlg",
                "Easy G-code Plot is a G-code viewer, editor and analyzer for turning and milling. "
                "Supports FANUC, Macro B, turning and milling cycles, and SINUMERIK 840D three-axis CAM trajectories. "
                "Includes toolpath playback, stock removal simulation and program export.",
            )
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
        """Populate export choices while Designer owns the complete dialog structure."""
        self.ui.langCmbBox.clear()
        self.ui.langCmbBox.addItems(self._MODE_LABELS)
        self.ui.incrCmbBox.clear()
        self.ui.incrCmbBox.addItems(("G90 Absolute", "G91 Incremental"))
        self.ui.arcOutputCmbBox.clear()
        self.ui.arcOutputCmbBox.addItems(self._ARC_LABELS)
        self.targetCncLabel = QLabel(QCoreApplication.translate("ExportOptDlg", "Target CNC"), self)
        self.targetCncCombo = QComboBox(self)
        self.targetCncLabel.setObjectName("targetCncLabel")
        self.targetCncCombo.setObjectName("targetCncCombo")
        self.targetCncCombo.addItems(
            (
                QCoreApplication.translate("ExportOptDlg", "As source (no conversion)"),
                QCoreApplication.translate("ExportOptDlg", "FANUC milling"),
                QCoreApplication.translate("ExportOptDlg", "SINUMERIK 840D ISO-M (G291)"),
                QCoreApplication.translate("ExportOptDlg", "SINUMERIK 840D native"),
            )
        )
        grid = self.ui.gridLayout
        existing_widgets = []
        for index in range(grid.count() - 1, -1, -1):
            row, column, row_span, column_span = grid.getItemPosition(index)
            widget = grid.itemAt(index).widget()
            if widget is not None:
                existing_widgets.append((widget, row + 1, column, row_span, column_span))
                grid.removeWidget(widget)
        for widget, row, column, row_span, column_span in existing_widgets:
            grid.addWidget(widget, row, column, row_span, column_span)
        grid.addWidget(self.targetCncLabel, 0, 0, 1, 1)
        grid.addWidget(self.targetCncCombo, 0, 1, 1, 1)
        self.resize(self.width(), self.height() + 35)

    def _set_parent_bool(self, combo, attr_name, true_index=1):
        """Update a boolean attribute on the parent using combo index."""
        setattr(self.parent(), attr_name, combo.currentIndex() == true_index)

    def _set_combo_from_bool(self, combo, value, true_index=1):
        """Set combo index based on a boolean value."""
        combo.setCurrentIndex(true_index if value else 0)

    def loadSettings(self):
        """Populate UI fields with current export preferences."""
        self.ui.langCmbBox.setCurrentIndex(self.parent().exportMode)
        self.targetCncCombo.setCurrentIndex(self.parent().exportTargetCnc)
        self.ui.arcOutputCmbBox.setCurrentIndex(self.parent().exportArcMode)
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
        self._sync_target_cnc_choices()
        self._sync_output_option_availability()

    def connectActions(self):
        """Keep edits local until OK; Cancel leaves application settings unchanged."""
        self.accepted.connect(self._apply_and_export)
        self.ui.langCmbBox.currentIndexChanged.connect(lambda _index: self._sync_output_option_availability())
        self.targetCncCombo.currentIndexChanged.connect(lambda _index: self._sync_output_option_availability())

    def showEvent(self, event):
        self.loadSettings()
        self.sync_mode_availability(bool(self.parent().latheMode))
        super().showEvent(event)

    def _apply_and_export(self):
        self.exportMode()
        self.parent().exportTargetCnc = (
            self.targetCncCombo.currentIndex()
            if self.ui.langCmbBox.currentIndex() in (MILL_FULL_PROGRAM_MODE, EXPANDED_EXECUTION_MODE)
            and not self.parent().latheMode
            else 0
        )
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
        self.parent().exportArcMode = self.ui.arcOutputCmbBox.currentIndex()

    def _sync_output_option_availability(self):
        """Enable only options consumed by the selected exporter."""
        dxf = self.ui.langCmbBox.currentIndex() == DXF_MODE
        full_mill = self.ui.langCmbBox.currentIndex() == MILL_FULL_PROGRAM_MODE
        resolved_mill = self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE and not self.parent().latheMode
        resolved_conversion = resolved_mill and self.targetCncCombo.currentIndex() != 0
        self.targetCncLabel.setEnabled(full_mill or resolved_mill)
        self.targetCncCombo.setEnabled(full_mill or resolved_mill)
        self._sync_target_cnc_choices()
        source_editing_controls = (
            (self.ui.label_StartText, self.ui.startLineEdit),
            (self.ui.label_EndText, self.ui.endLineEdit),
            (self.ui.label_SafLine, self.ui.safLineCmbBox),
        )
        formatting_controls = (
            (self.ui.label_SeqNum, self.ui.seqNumCmbBox),
            (self.ui.label_seqStart, self.ui.seqStartSpinBox),
            (self.ui.label_seqInterval, self.ui.seqIntervalSpinBox),
            (self.ui.label_Delim, self.ui.delimCmbBox),
            (self.ui.labelLeadingZero, self.ui.leadingZeroCmbBox),
        )
        for label, control in source_editing_controls:
            label.setEnabled(not dxf and not resolved_conversion)
            control.setEnabled(not dxf and not resolved_conversion)
        for label, control in formatting_controls:
            label.setEnabled(not dxf)
            control.setEnabled(not dxf)

        converted = self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE
        turning_expanded = converted and bool(self.parent().latheMode)
        self.ui.labelForce.setEnabled(converted and not resolved_conversion)
        self.ui.forceCmbBox.setEnabled(converted and not resolved_conversion)
        self.ui.label_Incr.setEnabled(converted and not resolved_conversion)
        self.ui.incrCmbBox.setEnabled(converted and not resolved_conversion)
        self.ui.arcOutputLabel.setEnabled(converted and not turning_expanded)
        self.ui.arcOutputCmbBox.setEnabled(converted and not turning_expanded)
        self._sync_resolved_arc_choices(resolved_conversion)

    def _sync_resolved_arc_choices(self, resolved):
        model = self.ui.arcOutputCmbBox.model()
        native = self.targetCncCombo.currentIndex() == 3
        allowed = {1, 3} if native else {0, 2, 3}
        for index in range(self.ui.arcOutputCmbBox.count()):
            model.item(index).setEnabled(not resolved or index in allowed)
        if resolved and self.ui.arcOutputCmbBox.currentIndex() not in allowed:
            self.ui.arcOutputCmbBox.setCurrentIndex(1 if native else 0)

    def _sync_target_cnc_choices(self):
        """Disable conversion to the dialect already used by the open program."""
        parent = self.parent()
        source = str(parent.ui.editor.text())
        source_dialect = source_dialect_for_path(getattr(parent, "curFile", None), source)
        model = self.targetCncCombo.model()
        resolved = self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE
        fanuc_item = model.item(1) if hasattr(model, "item") else None
        sinumerik_item = model.item(2) if hasattr(model, "item") else None
        if fanuc_item is not None:
            fanuc_item.setEnabled(resolved or source_dialect != SOURCE_DIALECT_FANUC)
        if sinumerik_item is not None:
            sinumerik_item.setEnabled(resolved or source_dialect != SOURCE_DIALECT_SINUMERIK)
        native_item = model.item(3) if hasattr(model, "item") else None
        if native_item is not None:
            native_item.setEnabled(resolved)
        current_item = model.item(self.targetCncCombo.currentIndex()) if hasattr(model, "item") else None
        if current_item is not None and not current_item.isEnabled():
            self.targetCncCombo.setCurrentIndex(0)

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
        self._length_controls = tuple(
            getattr(self.ui, f"g{code}{axis}") for code in range(54, 60) for axis in ("X", "Y", "Z")
        ) + (self.ui.homeX, self.ui.homeY, self.ui.homeZ)
        register_length_spinboxes(self._length_controls)
        self.ui.inchesCheck.toggled.connect(self._set_units)
        self.accepted.connect(self.applyValues)
        self.loadValues()

    def _set_units(self, inches: bool):
        set_length_units(self._length_controls, bool(inches), suffix=False)

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
            set_metric_value(getattr(self.ui, f"g{code}X"), float(x) * x_ui_scale)
            y_input = getattr(self.ui, f"g{code}Y")
            set_metric_value(y_input, float(y))
            y_input.setEnabled(not lathe)
            set_metric_value(getattr(self.ui, f"g{code}Z"), float(z))
        for axis, attr in (("X", "xPosMach"), ("Y", "yPosMach"), ("Z", "zPosMach")):
            scale = x_ui_scale if axis == "X" else 1.0
            control = getattr(self.ui, f"home{axis}")
            set_metric_value(control, float(getattr(self.parent(), attr, 0.0)) * scale)
            if axis == "Y":
                control.setEnabled(not lathe)
        self.ui.yHeader.setEnabled(not lathe)
        self.ui.homeConfiguredCheck.setChecked(bool(getattr(self.parent(), "homeConfigured", True)))

    def applyValues(self):
        """Store XYZ WCS and G28 values on the main window and refresh the trace."""
        x_ui_scale = 2.0 if bool(getattr(self.parent(), "latheMode", False)) else 1.0
        self.parent().wcsOffsets = {
            code: (
                metric_value(getattr(self.ui, f"g{code}X")) / x_ui_scale,
                metric_value(getattr(self.ui, f"g{code}Y")),
                metric_value(getattr(self.ui, f"g{code}Z")),
            )
            for code in range(54, 60)
        }
        for axis, attr in (("X", "xPosMach"), ("Y", "yPosMach"), ("Z", "zPosMach")):
            scale = x_ui_scale if axis == "X" else 1.0
            setattr(self.parent(), attr, metric_value(getattr(self.ui, f"home{axis}")) / scale)
        self.parent().homeConfigured = self.ui.homeConfiguredCheck.isChecked()
        self.parent().updateData()
