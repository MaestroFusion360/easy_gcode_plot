"""Find/replace, export and block-numbering dialogs."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from app.gcode.exporter import EXPANDED_MILL_PROGRAM_MODE, EXPANDED_TURN_PROGRAM_MODE
from app.ui.generated.block_num import Ui_BlockNumberDlg
from app.ui.generated.export import Ui_ExportOptDlg
from app.ui.generated.find_replace import Ui_Find


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
