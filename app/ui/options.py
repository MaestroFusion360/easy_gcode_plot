"""Application options dialog backed by the existing MainWindow settings."""

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QColorDialog, QDialog, QDialogButtonBox, QMessageBox

from app.settings import configure_logging
from app.ui.generated.options import Ui_OptionsDlg


class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_OptionsDlg()
        self.ui.setupUi(self)
        for button, edit in (
            (self.ui.rapidColorButton, self.ui.rapidColorEdit),
            (self.ui.linearColorButton, self.ui.linearColorEdit),
            (self.ui.arcColorButton, self.ui.arcColorEdit),
            (self.ui.currentColorButton, self.ui.currentColorEdit),
            (self.ui.backgroundColorButton, self.ui.backgroundColorEdit),
        ):
            button.clicked.connect(lambda _checked=False, target=edit: self.pick_color(target))
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)

    def showEvent(self, event):
        self.load_values()
        super().showEvent(event)

    def load_values(self):
        window = self.parent()
        self.ui.encodingCombo.setCurrentIndex(1 if getattr(window, "fileEncoding", "utf-8") == "cp1251" else 0)
        self.ui.fileTypeCombo.setCurrentIndex(getattr(window, "defaultFileType", window.ui.langCombo.currentIndex()))
        self.ui.unitsCombo.setCurrentIndex(1 if getattr(window, "defaultUnits", "mm") == "inch" else 0)
        self.ui.languageCombo.setCurrentIndex(1 if getattr(window, "uiLanguage", "en") == "ru" else 0)
        self.ui.loggingCheck.setChecked(getattr(window, "loggingEnabled", False))
        self.ui.correctionCheck.setChecked(getattr(window, "correctionEnabled", True))
        self.ui.arcToleranceSpin.setValue(getattr(window, "arcTolerance", 0.001))
        self.ui.fontCombo.setCurrentFont(QFont(window.fontFamily))
        self.ui.fontSizeSpin.setValue(window.sizeTxt)
        self.ui.caretLineCheck.setChecked(window.caretLine)
        self.ui.eolCheck.setChecked(window.eolVisible)
        self.ui.whitespaceCheck.setChecked(window.spaceVisible)
        self.ui.marginCheck.setChecked(window.marginArea)
        self.ui.rapidColorEdit.setText(getattr(window, "plotRapidColor", "#d02020"))
        self.ui.linearColorEdit.setText(window.plotLineColor)
        self.ui.arcColorEdit.setText(getattr(window, "plotArcColor", "#008000"))
        self.ui.currentColorEdit.setText(getattr(window, "plotCurrentColor", "#00b7ff"))
        self.ui.backgroundColorEdit.setText(window.plotBackground)
        self.ui.lineWidthSpin.setValue(getattr(window, "plotLineWidth", 1.5))
        self.ui.gridStepSpin.setValue(getattr(window, "plotGridStep", 0.0))
        self.ui.axesCheck.setChecked(getattr(window, "plotAxes", True))
        self.ui.gridCheck.setChecked(window.plotGrid)

    def accept(self):
        window = self.parent()
        previous_units = getattr(window, "defaultUnits", "mm")
        previous_correction = getattr(window, "correctionEnabled", True)
        previous_tolerance = getattr(window, "arcTolerance", 0.001)
        color_edits = (
            self.ui.rapidColorEdit,
            self.ui.linearColorEdit,
            self.ui.arcColorEdit,
            self.ui.currentColorEdit,
            self.ui.backgroundColorEdit,
        )
        if any(not QColor(edit.text()).isValid() for edit in color_edits):
            QMessageBox.warning(self, "Options", "Plot colors must be valid Qt color names, for example #008000.")
            return
        window.fileEncoding = "cp1251" if self.ui.encodingCombo.currentIndex() else "utf-8"
        window.defaultFileType = self.ui.fileTypeCombo.currentIndex()
        window.defaultUnits = "inch" if self.ui.unitsCombo.currentIndex() else "mm"
        window.loggingEnabled = self.ui.loggingCheck.isChecked()
        window.correctionEnabled = self.ui.correctionCheck.isChecked()
        window.arcTolerance = self.ui.arcToleranceSpin.value()
        window.fontFamily = self.ui.fontCombo.currentFont().family()
        window.sizeTxt = self.ui.fontSizeSpin.value()
        window.caretLine = self.ui.caretLineCheck.isChecked()
        window.eolVisible = self.ui.eolCheck.isChecked()
        window.spaceVisible = self.ui.whitespaceCheck.isChecked()
        window.marginArea = self.ui.marginCheck.isChecked()
        (
            window.plotRapidColor,
            window.plotLineColor,
            window.plotArcColor,
            window.plotCurrentColor,
            window.plotBackground,
        ) = (edit.text() for edit in color_edits)
        window.plotLineWidth = self.ui.lineWidthSpin.value()
        window.plotGridStep = self.ui.gridStepSpin.value()
        window.plotAxes = self.ui.axesCheck.isChecked()
        window.plotGrid = self.ui.gridCheck.isChecked()
        target_file_type = window.defaultFileType
        signals_blocked = window.ui.langCombo.blockSignals(True)
        window.ui.langCombo.setCurrentIndex(target_file_type)
        window.ui.langCombo.blockSignals(signals_blocked)
        window.ui.actionGrid.setChecked(window.plotGrid)
        window.ui.editor.setCaretLineVisible(window.caretLine)
        window.ui.editor.setEolVisibility(window.eolVisible)
        whitespace = (
            QsciScintilla.WhitespaceVisibility.WsVisible
            if window.spaceVisible
            else QsciScintilla.WhitespaceVisibility.WsInvisible
        )
        window.ui.editor.setWhitespaceVisibility(whitespace)
        window.ui.editor.setMarginLineNumbers(1, window.marginArea)
        window.changeLang(target_file_type)
        configure_logging(window.loggingEnabled)
        window.saveSettings()
        execution_changed = (
            previous_units != window.defaultUnits
            or previous_correction != window.correctionEnabled
            or previous_tolerance != window.arcTolerance
        )
        if execution_changed and getattr(window, "execution_result", None) is not None:
            window.updateData()
        else:
            window.refreshPlotView()
        super().accept()

    def pick_color(self, target):
        color = QColorDialog.getColor(QColor(target.text()), self, "Select color")
        if color.isValid():
            target.setText(color.name())

    def restore_defaults(self):
        self.ui.encodingCombo.setCurrentIndex(0)
        self.ui.fileTypeCombo.setCurrentIndex(0)
        self.ui.unitsCombo.setCurrentIndex(0)
        self.ui.loggingCheck.setChecked(False)
        self.ui.correctionCheck.setChecked(True)
        self.ui.arcToleranceSpin.setValue(0.001)
        self.ui.fontCombo.setCurrentFont(QFont("Courier New"))
        self.ui.fontSizeSpin.setValue(12)
        self.ui.caretLineCheck.setChecked(True)
        self.ui.eolCheck.setChecked(False)
        self.ui.whitespaceCheck.setChecked(False)
        self.ui.marginCheck.setChecked(True)
        for edit, value in (
            (self.ui.rapidColorEdit, "#d02020"),
            (self.ui.linearColorEdit, "#0000ff"),
            (self.ui.arcColorEdit, "#008000"),
            (self.ui.currentColorEdit, "#00b7ff"),
            (self.ui.backgroundColorEdit, "#ffffff"),
        ):
            edit.setText(value)
        self.ui.lineWidthSpin.setValue(1.5)
        self.ui.gridStepSpin.setValue(0.0)
        self.ui.axesCheck.setChecked(True)
        self.ui.gridCheck.setChecked(False)
