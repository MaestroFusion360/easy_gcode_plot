"""General application dialogs unrelated to tool-library editing."""

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QDialog

from app import get_version
from app.gcode.export import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
)
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
        self.targetCncLabel = self.ui.label_TargetCnc
        self.targetCncCombo = self.ui.targetCncCombo
        self.modalFeedLabel = self.ui.modalFeedLabel
        self.modalFeedCombo = self.ui.modalFeedCombo
        self.decimalPlacesLabel = self.ui.decimalPlacesLabel
        self.decimalPlacesSpin = self.ui.decimalPlacesSpin
        self.forceDecimalLabel = self.ui.forceDecimalLabel
        self.forceDecimalCombo = self.ui.forceDecimalCombo
        self.plusSignLabel = self.ui.plusSignLabel
        self.plusSignCombo = self.ui.plusSignCombo
        self._configure_export_mode_ui()
        self.loadSettings()
        self.connectActions()
        self.sync_mode_availability(bool(self.parent().latheMode))

    def _configure_export_mode_ui(self):
        """Populate export choices; Designer owns the complete dialog structure."""
        self.ui.langCmbBox.clear()
        self.ui.langCmbBox.addItems(self._MODE_LABELS)
        self.ui.incrCmbBox.clear()
        self.ui.incrCmbBox.addItems(("G90 Absolute", "G91 Incremental"))
        self.ui.arcOutputCmbBox.clear()
        self.ui.arcOutputCmbBox.addItems(self._ARC_LABELS)
        translate = QCoreApplication.translate
        self.targetCncCombo.clear()
        self.targetCncCombo.addItems(
            (
                translate("ExportOptDlg", "Auto (source controller)"),
                translate("ExportOptDlg", "FANUC milling"),
                translate("ExportOptDlg", "SINUMERIK 840D ISO-M (G291)"),
                translate("ExportOptDlg", "SINUMERIK 840D native"),
                translate("ExportOptDlg", "FANUC milling (multi-axis)"),
                translate("ExportOptDlg", "SINUMERIK 840D native (multi-axis)"),
            )
        )
        self._set_tooltips()
        required = self.sizeHint().expandedTo(self.minimumSize())
        self.setMinimumSize(required)
        self.resize(required)

    def _set_tooltips(self):
        """Explain options without disabling them by target controller."""
        translate = QCoreApplication.translate
        self.targetCncCombo.setToolTip(
            translate(
                "ExportOptDlg",
                "Auto selects the post profile matching the source controller/dialect. "
                "Other entries choose a target controller; user output options stay available.",
            )
        )
        self.modalFeedCombo.setToolTip(
            translate(
                "ExportOptDlg",
                "Yes suppresses repeated F when feed and mode are unchanged; No restates F on every motion.",
            )
        )
        self.ui.safLineCmbBox.setToolTip(
            translate(
                "ExportOptDlg",
                "Insert the post profile's declared safe restart block after the program start text.",
            )
        )
        self.ui.startLineEdit.setToolTip(
            translate(
                "ExportOptDlg",
                "Inserted before the post preamble. A mandatory controller mode (G290/G291) always stays first.",
            )
        )
        self.ui.endLineEdit.setToolTip(translate("ExportOptDlg", "Replaces the post profile's program end text."))

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
        self._set_combo_from_bool(self.ui.incrCmbBox, self.parent().incrMode)
        self.ui.startLineEdit.setText(self.parent().startPgmExp)
        self.ui.endLineEdit.setText(self.parent().endPgmExp)
        self._set_combo_from_bool(self.ui.safLineCmbBox, self.parent().safLine)
        self._set_combo_from_bool(self.ui.seqNumCmbBox, self.parent().seqNum)
        self.ui.seqStartSpinBox.setValue(self.parent().seqNumStart)
        self.ui.seqIntervalSpinBox.setValue(self.parent().seqNumIncr)
        self._set_combo_from_bool(self.ui.delimCmbBox, self.parent().delim)
        self._set_combo_from_bool(self.ui.leadingZeroCmbBox, self.parent().leadingZero)
        self._set_combo_from_bool(self.modalFeedCombo, getattr(self.parent(), "modalFeed", True))
        self.decimalPlacesSpin.setValue(int(getattr(self.parent(), "exportDecimalPlaces", 6)))
        self._set_combo_from_bool(self.forceDecimalCombo, getattr(self.parent(), "exportForceDecimal", False))
        self._set_combo_from_bool(self.plusSignCombo, getattr(self.parent(), "exportPlusOutput", False))
        self._sync_target_cnc_choices()
        self._sync_output_option_availability()

    def connectActions(self):
        """Keep edits local until OK; Cancel leaves application settings unchanged."""
        self.accepted.connect(self._apply_and_export)
        self.ui.langCmbBox.currentIndexChanged.connect(lambda _index: self._sync_output_option_availability())
        self.targetCncCombo.currentIndexChanged.connect(lambda _index: self._sync_target_cnc_choices())

    def showEvent(self, event):
        self.loadSettings()
        self.sync_mode_availability(bool(self.parent().latheMode))
        super().showEvent(event)

    def _apply_and_export(self):
        self.exportMode()
        self.parent().exportTargetCnc = (
            self.targetCncCombo.currentIndex() if self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE else 0
        )
        self.arcMode()
        self.incrMode(self.ui.incrCmbBox.currentIndex())
        self.startPgmText()
        self.endPgmText()
        self.safLine(self.ui.safLineCmbBox.currentIndex())
        self.seqNum(self.ui.seqNumCmbBox.currentIndex())
        self.seqNumStart()
        self.seqNumIncr()
        self.delim(self.ui.delimCmbBox.currentIndex())
        self.ledingZero(self.ui.leadingZeroCmbBox.currentIndex())
        self.apply_output_fields()
        self.parent().export()

    def apply_output_fields(self):
        """Persist the four EXPANDED output fields on the parent window."""
        self._set_parent_bool(self.modalFeedCombo, "modalFeed")
        self.parent().exportDecimalPlaces = self.decimalPlacesSpin.value()
        self._set_parent_bool(self.forceDecimalCombo, "exportForceDecimal")
        self._set_parent_bool(self.plusSignCombo, "exportPlusOutput")

    def exportMode(self):
        """Store the selected logical export type."""
        self.parent().exportMode = self.ui.langCmbBox.currentIndex()
        self._sync_output_option_availability()

    def arcMode(self):
        """Store the arc representation used by expanded execution output."""
        self.parent().exportArcMode = self.ui.arcOutputCmbBox.currentIndex()

    def _sync_output_option_availability(self):
        """Enable options by export mode only; the target controller never disables formatting."""
        mode = self.ui.langCmbBox.currentIndex()
        dxf = mode == DXF_MODE
        expanded = mode == EXPANDED_EXECUTION_MODE
        self.targetCncLabel.setEnabled(expanded)
        self.targetCncCombo.setEnabled(expanded)
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
        expanded_only_controls = (
            (self.ui.label_Incr, self.ui.incrCmbBox),
            (self.ui.arcOutputLabel, self.ui.arcOutputCmbBox),
            (self.modalFeedLabel, self.modalFeedCombo),
            (self.decimalPlacesLabel, self.decimalPlacesSpin),
            (self.forceDecimalLabel, self.forceDecimalCombo),
            (self.plusSignLabel, self.plusSignCombo),
        )
        for label, control in (*source_editing_controls, *formatting_controls):
            label.setEnabled(not dxf)
            control.setEnabled(not dxf)
        for label, control in expanded_only_controls:
            label.setEnabled(expanded)
            control.setEnabled(expanded)

    def _sync_target_cnc_choices(self):
        expanded = self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE
        turning = bool(self.parent().latheMode)
        labels = ("FANUC lathe A", "FANUC lathe B") if turning else ("FANUC milling", "SINUMERIK 840D ISO-M (G291)")
        for index, label in enumerate(labels, 1):
            self.targetCncCombo.setItemText(index, label)
        for index in range(1, self.targetCncCombo.count()):
            self.targetCncCombo.model().item(index).setEnabled(expanded and not (turning and index >= 3))
        if not expanded or (turning and self.targetCncCombo.currentIndex() >= 3):
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
