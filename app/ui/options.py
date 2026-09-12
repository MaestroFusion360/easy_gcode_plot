"""Application options dialog backed by the existing MainWindow settings."""

import logging

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QRegularExpressionValidator
from PyQt6.QtWidgets import QColorDialog, QDialog, QDialogButtonBox, QMessageBox

from app.settings import configure_logging
from app.ui.generated.options import Ui_OptionsDlg
from app.ui.main_window_execution import playback_interval_ms

LOGGER = logging.getLogger(__name__)


def _option_snapshot(window):
    """Return the user-facing option state used for diagnostic change logs."""
    return {
        "encoding": getattr(window, "fileEncoding", "utf-8"),
        "file_type": getattr(window, "defaultFileType", 0),
        "units": getattr(window, "defaultUnits", "mm"),
        "logging": getattr(window, "loggingEnabled", False),
        "auto_update": getattr(window, "autoUpdateEnabled", True),
        "auto_update_limit": getattr(window, "autoUpdateMaxSegments", 20000),
        "correction": getattr(window, "correctionEnabled", True),
        "arc_tolerance": getattr(window, "arcTolerance", 0.001),
        "font_family": getattr(window, "fontFamily", "Courier New"),
        "font_size": getattr(window, "sizeTxt", 12),
        "caret_line": getattr(window, "caretLine", True),
        "eol_visible": getattr(window, "eolVisible", False),
        "whitespace_visible": getattr(window, "spaceVisible", False),
        "margin_visible": getattr(window, "marginArea", True),
        "show_stock": getattr(window, "showStock", True),
        "plot_grid": getattr(window, "plotGrid", False),
        "plot_axes": getattr(window, "plotAxes", True),
        "grid_step": getattr(window, "plotGridStep", 0.0),
        "line_width": getattr(window, "plotLineWidth", 1.5),
        "gradient": getattr(window, "plotBackgroundGradient", False),
        "rapid_color": getattr(window, "plotRapidColor", "#d02020"),
        "linear_color": getattr(window, "plotLineColor", "#0000ff"),
        "arc_color": getattr(window, "plotArcColor", "#008000"),
        "current_color": getattr(window, "plotCurrentColor", "#00b7ff"),
        "tool_color": getattr(window, "plotToolColor", "#4d99ff"),
        "background_color": getattr(window, "plotBackground", "#ffffff"),
        "stl_color": getattr(window, "stlColor", "#b0b0b0"),
        "stl_wireframe": getattr(window, "stlWireframe", False),
        "playback_speed": getattr(window, "playbackSpeed", 3),
    }


class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_OptionsDlg()
        self.ui.setupUi(self)
        self._color_controls = (
            (self.ui.rapidColorButton, self.ui.rapidColorEdit),
            (self.ui.linearColorButton, self.ui.linearColorEdit),
            (self.ui.arcColorButton, self.ui.arcColorEdit),
            (self.ui.currentColorButton, self.ui.currentColorEdit),
            (self.ui.toolColorButton, self.ui.toolColorEdit),
            (self.ui.backgroundColorButton, self.ui.backgroundColorEdit),
            (self.ui.stlColorButton, self.ui.stlColorEdit),
        )
        validator = QRegularExpressionValidator(QRegularExpression(r"^#[0-9A-Fa-f]{6}$"), self)
        for button, edit in self._color_controls:
            button.clicked.connect(lambda _checked=False, target=edit: self.pick_color(target))
            edit.setValidator(validator)
            edit.textChanged.connect(lambda _text, target=edit, swatch=button: self._update_swatch(swatch, target))
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        self.ui.playbackSpeedSlider.valueChanged.connect(self._update_playback_speed_label)
        self.ui.correctionCheck.toggled.connect(self._preview_correction)
        self.ui.showStockCheck.toggled.connect(self._preview_show_stock)
        self._loading_values = False
        self._correction_before_show = None
        self._correction_preview_applied = False
        self._show_stock_before_show = None

    @staticmethod
    def _update_swatch(button, edit):
        color = QColor(edit.text())
        button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #666;" if color.isValid() else "")

    def showEvent(self, event):
        self._correction_before_show = getattr(self.parent(), "correctionEnabled", True)
        self._correction_preview_applied = False
        self._show_stock_before_show = getattr(self.parent(), "showStock", True)
        self.load_values()
        LOGGER.debug("options_opened values=%s", _option_snapshot(self.parent()))
        super().showEvent(event)

    def load_values(self):
        window = self.parent()
        self.ui.encodingCombo.setCurrentIndex(1 if getattr(window, "fileEncoding", "utf-8") == "cp1251" else 0)
        self.ui.fileTypeCombo.setCurrentIndex(
            getattr(window, "defaultFileType", window.ui.fileTypeCombo.currentIndex())
        )
        self.ui.unitsCombo.setCurrentIndex(1 if getattr(window, "defaultUnits", "mm") == "inch" else 0)
        self.ui.languageCombo.setCurrentIndex(1 if getattr(window, "uiLanguage", "en") == "ru" else 0)
        self.ui.loggingCheck.setChecked(getattr(window, "loggingEnabled", False))
        self.ui.autoUpdateCheck.setChecked(getattr(window, "autoUpdateEnabled", True))
        self.ui.autoUpdateMaxSegmentsSpin.setValue(getattr(window, "autoUpdateMaxSegments", 20000))
        self._loading_values = True
        try:
            self.ui.correctionCheck.setChecked(getattr(window, "correctionEnabled", True))
            self.ui.showStockCheck.setChecked(getattr(window, "showStock", True))
        finally:
            self._loading_values = False
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
        self.ui.toolColorEdit.setText(getattr(window, "plotToolColor", "#4d99ff"))
        self.ui.backgroundColorEdit.setText(window.plotBackground)
        self.ui.backgroundGradientCheck.setChecked(getattr(window, "plotBackgroundGradient", False))
        self.ui.stlColorEdit.setText(getattr(window, "stlColor", "#b0b0b0"))
        self.ui.stlWireframeCheck.setChecked(getattr(window, "stlWireframe", False))
        self.ui.lineWidthSpin.setValue(getattr(window, "plotLineWidth", 1.5))
        self.ui.gridStepSpin.setValue(getattr(window, "plotGridStep", 0.0))
        self.ui.axesCheck.setChecked(getattr(window, "plotAxes", True))
        self.ui.gridCheck.setChecked(window.plotGrid)
        self.ui.playbackSpeedSlider.setValue(getattr(window, "playbackSpeed", 3))
        self._update_playback_speed_label(self.ui.playbackSpeedSlider.value())
        for button, edit in self._color_controls:
            self._update_swatch(button, edit)

    def accept(self):
        window = self.parent()
        previous_options = _option_snapshot(window)
        previous_units = getattr(window, "defaultUnits", "mm")
        previous_correction = (
            getattr(window, "correctionEnabled", True)
            if self._correction_before_show is None
            else self._correction_before_show
        )
        previous_tolerance = getattr(window, "arcTolerance", 0.001)
        previous_show_stock = (
            getattr(window, "showStock", True) if self._show_stock_before_show is None else self._show_stock_before_show
        )
        previous_stl_appearance = (
            getattr(window, "stlColor", "#b0b0b0"),
            getattr(window, "stlWireframe", False),
        )
        color_edits = (
            self.ui.rapidColorEdit,
            self.ui.linearColorEdit,
            self.ui.arcColorEdit,
            self.ui.currentColorEdit,
            self.ui.toolColorEdit,
            self.ui.backgroundColorEdit,
            self.ui.stlColorEdit,
        )
        if any(not QColor(edit.text()).isValid() for edit in color_edits):
            QMessageBox.warning(self, "Options", "Plot colors must be valid Qt color names, for example #008000.")
            return
        window.fileEncoding = "cp1251" if self.ui.encodingCombo.currentIndex() else "utf-8"
        window.defaultFileType = self.ui.fileTypeCombo.currentIndex()
        window.defaultUnits = "inch" if self.ui.unitsCombo.currentIndex() else "mm"
        window.loggingEnabled = self.ui.loggingCheck.isChecked()
        window.autoUpdateEnabled = self.ui.autoUpdateCheck.isChecked()
        window.autoUpdateMaxSegments = self.ui.autoUpdateMaxSegmentsSpin.value()
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
            window.plotToolColor,
            window.plotBackground,
            window.stlColor,
        ) = (edit.text() for edit in color_edits)
        window.plotBackgroundGradient = self.ui.backgroundGradientCheck.isChecked()
        window.stlWireframe = self.ui.stlWireframeCheck.isChecked()
        window.plotLineWidth = self.ui.lineWidthSpin.value()
        window.plotGridStep = self.ui.gridStepSpin.value()
        window.plotAxes = self.ui.axesCheck.isChecked()
        window.plotGrid = self.ui.gridCheck.isChecked()
        window.showStock = self.ui.showStockCheck.isChecked()
        window.playbackSpeed = self.ui.playbackSpeedSlider.value()
        window.speedTimer = playback_interval_ms(window.playbackSpeed)
        target_file_type = window.defaultFileType
        signals_blocked = window.ui.fileTypeCombo.blockSignals(True)
        window.ui.fileTypeCombo.setCurrentIndex(target_file_type)
        window.ui.fileTypeCombo.blockSignals(signals_blocked)
        window.ui.actionGrid.setChecked(window.plotGrid)
        if previous_show_stock != window.showStock:
            window.showStockChecked(window.showStock)
        window.ui.editor.setCaretLineVisible(window.caretLine)
        window.ui.editor.setEolVisibility(window.eolVisible)
        whitespace = (
            QsciScintilla.WhitespaceVisibility.WsVisible
            if window.spaceVisible
            else QsciScintilla.WhitespaceVisibility.WsInvisible
        )
        window.ui.editor.setWhitespaceVisibility(whitespace)
        window.ui.editor.setMarginLineNumbers(1, window.marginArea)
        window.changeFileType(target_file_type)
        current_options = _option_snapshot(window)
        changed_options = {
            key: (previous_options[key], value)
            for key, value in current_options.items()
            if previous_options[key] != value
        }
        if previous_options["logging"] and not current_options["logging"]:
            LOGGER.info("options_applied changes=%s", changed_options)
        configure_logging(window.loggingEnabled)
        if current_options["logging"]:
            LOGGER.info("options_applied changes=%s", changed_options)
        if not window.autoUpdateEnabled:
            window.autoUpdateTimer.stop()
        elif getattr(window, "_plot_source_stale", False):
            window.scheduleAutoUpdate()
        window.saveSettings()
        if window.timer.isActive():
            window.timer.start(window.speedTimer, window)
        if previous_stl_appearance != (window.stlColor, window.stlWireframe):
            window.refreshStlAppearance()
        correction_needs_update = (
            previous_correction != window.correctionEnabled and not self._correction_preview_applied
        )
        if (
            previous_units != window.defaultUnits
            or correction_needs_update
            or previous_tolerance != window.arcTolerance
        ) and getattr(window, "execution_result", None) is not None:
            window.updateData()
        elif not self._correction_preview_applied:
            window.refreshPlotView()
        self._correction_before_show = None
        self._correction_preview_applied = False
        self._show_stock_before_show = None
        super().accept()

    def reject(self):
        window = self.parent()
        previous_correction = self._correction_before_show
        if previous_correction is not None and window.correctionEnabled != previous_correction:
            window.correctionEnabled = previous_correction
            if getattr(window, "execution_result", None) is not None:
                window.updateData()
        previous_show_stock = self._show_stock_before_show
        if previous_show_stock is not None and window.showStock != previous_show_stock:
            window.showStockChecked(previous_show_stock)
        LOGGER.info(
            "options_cancelled correction_restored=%s show_stock_restored=%s",
            previous_correction,
            previous_show_stock,
        )
        self._correction_before_show = None
        self._correction_preview_applied = False
        self._show_stock_before_show = None
        super().reject()

    def _preview_correction(self, enabled):
        """Rebuild the current milling trace when G41/G42 correction is toggled."""
        if self._loading_values:
            return
        window = self.parent()
        if self._correction_before_show is None:
            self._correction_before_show = getattr(window, "correctionEnabled", True)
        if window.correctionEnabled == enabled:
            return
        window.correctionEnabled = enabled
        LOGGER.debug("option_preview correction=%s", enabled)
        if getattr(window, "execution_result", None) is not None:
            self._correction_preview_applied = bool(window.updateData())

    def _preview_show_stock(self, enabled):
        """Update the lathe stock outline while the Options dialog is open."""
        if self._loading_values:
            return
        LOGGER.debug("option_preview show_stock=%s", enabled)
        self.parent().showStockChecked(enabled)

    def pick_color(self, target):
        color = QColorDialog.getColor(QColor(target.text()), self, "Select color")
        if color.isValid():
            target.setText(color.name())

    def restore_defaults(self):
        LOGGER.debug("options_restore_defaults_requested")
        self.ui.encodingCombo.setCurrentIndex(0)
        self.ui.fileTypeCombo.setCurrentIndex(0)
        self.ui.unitsCombo.setCurrentIndex(0)
        self.ui.loggingCheck.setChecked(False)
        self.ui.autoUpdateCheck.setChecked(True)
        self.ui.autoUpdateMaxSegmentsSpin.setValue(20000)
        self.ui.correctionCheck.setChecked(True)
        self.ui.arcToleranceSpin.setValue(0.001)
        self.ui.fontCombo.setCurrentFont(QFont("Courier New"))
        self.ui.fontSizeSpin.setValue(12)
        self.ui.caretLineCheck.setChecked(True)
        self.ui.eolCheck.setChecked(False)
        self.ui.whitespaceCheck.setChecked(False)
        self.ui.marginCheck.setChecked(True)
        self.ui.showStockCheck.setChecked(True)
        for edit, value in (
            (self.ui.rapidColorEdit, "#d02020"),
            (self.ui.linearColorEdit, "#0000ff"),
            (self.ui.arcColorEdit, "#008000"),
            (self.ui.currentColorEdit, "#00b7ff"),
            (self.ui.toolColorEdit, "#4d99ff"),
            (self.ui.backgroundColorEdit, "#ffffff"),
            (self.ui.stlColorEdit, "#b0b0b0"),
        ):
            edit.setText(value)
        self.ui.backgroundGradientCheck.setChecked(False)
        self.ui.stlWireframeCheck.setChecked(False)
        self.ui.lineWidthSpin.setValue(1.5)
        self.ui.gridStepSpin.setValue(0.0)
        self.ui.axesCheck.setChecked(True)
        self.ui.gridCheck.setChecked(False)
        self.ui.playbackSpeedSlider.setValue(3)

    def _update_playback_speed_label(self, value):
        interval = playback_interval_ms(value)
        self.ui.playbackSpeedValueLabel.setText(f"{value} — {interval} ms/step")
