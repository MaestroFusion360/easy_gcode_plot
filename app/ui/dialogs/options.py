"""Application options dialog backed by the existing MainWindow settings."""

import logging

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QCoreApplication, QRegularExpression
from PyQt6.QtGui import QColor, QFont, QRegularExpressionValidator
from PyQt6.QtWidgets import QColorDialog, QDialog, QDialogButtonBox, QMessageBox

from app import theme
from app.gcode.comments import DEFAULT_COMMENT_STYLE, SEMICOLON, comment_markers, normalize_comment_style
from app.settings import (
    ARC_SAMPLING_PRESET_DEFAULT,
    ARC_SAMPLING_PRESETS,
    ARC_TOLERANCE_DEFAULT,
    GENERATED_MOTIONS_DEFAULT,
    MAXIMUM_CIRCULAR_RADIUS_DEFAULT,
    MINIMUM_CHORD_LENGTH_DEFAULT,
    MINIMUM_CIRCULAR_RADIUS_DEFAULT,
    configure_logging,
)
from app.ui.generated.dialogs.options import Ui_OptionsDlg
from app.ui.windows.main_window_execution import playback_interval_ms

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
        "generated_motions_limit": getattr(window, "maxGeneratedMotions", GENERATED_MOTIONS_DEFAULT),
        "correction": getattr(window, "correctionEnabled", True),
        "autodetect_arc_type": getattr(window, "autodetectArcType", True),
        "ignore_block_skip": getattr(window, "ignoreBlockSkip", False),
        "comment_style": getattr(window, "commentStyle", DEFAULT_COMMENT_STYLE),
        "arc_sampling_preset": getattr(window, "arcSamplingPreset", ARC_SAMPLING_PRESET_DEFAULT),
        "arc_tolerance": getattr(window, "arcTolerance", ARC_TOLERANCE_DEFAULT),
        "maximum_circular_radius": getattr(window, "maximumCircularRadius", MAXIMUM_CIRCULAR_RADIUS_DEFAULT),
        "minimum_circular_radius": getattr(window, "minimumCircularRadius", MINIMUM_CIRCULAR_RADIUS_DEFAULT),
        "minimum_chord_length": getattr(window, "minimumChordLength", MINIMUM_CHORD_LENGTH_DEFAULT),
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


def _execution_semantics_changed(
    window,
    *,
    previous_units,
    correction_needs_update,
    previous_tolerance,
    previous_autodetect_arc_type,
    previous_ignore_block_skip,
    previous_generated_motions,
):
    return any(
        (
            previous_units != window.defaultUnits,
            correction_needs_update,
            previous_tolerance != window.arcTolerance,
            previous_autodetect_arc_type != window.autodetectArcType,
            previous_ignore_block_skip != window.ignoreBlockSkip,
            previous_generated_motions != window.maxGeneratedMotions,
        )
    )


def _apply_cnc_options(window, ui):
    window.correctionEnabled = ui.correctionCheck.isChecked()
    window.arcTolerance = ui.arcToleranceSpin.value()
    window.arcSamplingPreset = ARC_SAMPLING_PRESETS[ui.arcSamplingPresetCombo.currentIndex()][0]
    window.maximumCircularRadius = ui.maximumCircularRadiusSpin.value()
    window.minimumCircularRadius = min(ui.minimumCircularRadiusSpin.value(), window.maximumCircularRadius)
    window.minimumChordLength = ui.minimumChordLengthSpin.value()
    window.autodetectArcType = ui.autodetectArcTypeCheck.isChecked()
    window.ignoreBlockSkip = ui.ignoreBlockSkipCheck.isChecked()
    window.commentStyle = SEMICOLON if ui.commentStyleCombo.currentIndex() else DEFAULT_COMMENT_STYLE
    window.co, window.ci = comment_markers(window.commentStyle)
    window.lexer.set_comment_style(window.commentStyle)


def _apply_editor_display_options(window):
    window.ui.editor.setCaretLineVisible(window.caretLine)
    window.ui.editor.setEolVisibility(window.eolVisible)
    whitespace = (
        QsciScintilla.WhitespaceVisibility.WsVisible
        if window.spaceVisible
        else QsciScintilla.WhitespaceVisibility.WsInvisible
    )
    window.ui.editor.setWhitespaceVisibility(whitespace)
    window.ui.editor.setMarginLineNumbers(1, window.marginArea)


def _arc_sampling_snapshot(window):
    return (
        getattr(window, "maximumCircularRadius", MAXIMUM_CIRCULAR_RADIUS_DEFAULT),
        getattr(window, "minimumCircularRadius", MINIMUM_CIRCULAR_RADIUS_DEFAULT),
        getattr(window, "minimumChordLength", MINIMUM_CHORD_LENGTH_DEFAULT),
    )


def _refresh_after_option_changes(window, *, execution_changed, sampling_changed, correction_preview_applied):
    if execution_changed and getattr(window, "execution_result", None) is not None:
        window.updateData()
    elif sampling_changed and getattr(window, "execution_result", None) is not None:
        window.rerenderCurrentResult()
    elif not correction_preview_applied:
        window.refreshPlotView()


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
        self.ui.arcSamplingPresetCombo.currentIndexChanged.connect(self._apply_arc_sampling_preset)
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
        self.ui.themeCombo.setCurrentIndex(1 if getattr(window, "uiTheme", "light") == "dark" else 0)
        self.ui.loggingCheck.setChecked(getattr(window, "loggingEnabled", False))
        self.ui.autoUpdateCheck.setChecked(getattr(window, "autoUpdateEnabled", True))
        self.ui.autoUpdateMaxSegmentsSpin.setValue(getattr(window, "autoUpdateMaxSegments", 20000))
        self.ui.maxGeneratedMotionsSpin.setValue(getattr(window, "maxGeneratedMotions", GENERATED_MOTIONS_DEFAULT))
        self._loading_values = True
        try:
            self.ui.correctionCheck.setChecked(getattr(window, "correctionEnabled", True))
            self.ui.showStockCheck.setChecked(getattr(window, "showStock", True))
        finally:
            self._loading_values = False
        self._load_arc_sampling_values(window)
        self.ui.autodetectArcTypeCheck.setChecked(getattr(window, "autodetectArcType", True))
        self.ui.ignoreBlockSkipCheck.setChecked(getattr(window, "ignoreBlockSkip", False))
        self.ui.commentStyleCombo.setCurrentIndex(
            1 if normalize_comment_style(getattr(window, "commentStyle", DEFAULT_COMMENT_STYLE)) == SEMICOLON else 0
        )
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

    def _load_arc_sampling_values(self, window):
        preset_ids = [preset[0] for preset in ARC_SAMPLING_PRESETS]
        preset_id = getattr(window, "arcSamplingPreset", ARC_SAMPLING_PRESET_DEFAULT)
        self._loading_values = True
        try:
            index = (
                preset_ids.index(preset_id)
                if preset_id in preset_ids
                else preset_ids.index(ARC_SAMPLING_PRESET_DEFAULT)
            )
            self.ui.arcSamplingPresetCombo.setCurrentIndex(index)
        finally:
            self._loading_values = False
        self.ui.arcToleranceSpin.setValue(getattr(window, "arcTolerance", ARC_TOLERANCE_DEFAULT))
        self.ui.maximumCircularRadiusSpin.setValue(
            getattr(window, "maximumCircularRadius", MAXIMUM_CIRCULAR_RADIUS_DEFAULT)
        )
        self.ui.minimumCircularRadiusSpin.setValue(
            getattr(window, "minimumCircularRadius", MINIMUM_CIRCULAR_RADIUS_DEFAULT)
        )
        self.ui.minimumChordLengthSpin.setValue(getattr(window, "minimumChordLength", MINIMUM_CHORD_LENGTH_DEFAULT))

    def _log_option_changes(self, window, previous_options):
        """Apply logging configuration and log the changed option values."""
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

    def _apply_language_and_theme(self, window, previous_language, previous_theme):
        """Persist language/theme choices and apply a live theme change."""
        window.uiLanguage = "ru" if self.ui.languageCombo.currentIndex() else "en"
        window.uiTheme = "dark" if self.ui.themeCombo.currentIndex() else "light"
        if previous_theme != window.uiTheme:
            window.applyUiTheme()
        if previous_language != window.uiLanguage:
            QMessageBox.information(
                self,
                QCoreApplication.translate("OptionsDlg", "Options"),
                QCoreApplication.translate(
                    "OptionsDlg", "The language change will be applied after restarting Easy G-Code Plot."
                ),
            )

    def accept(self):
        window = self.parent()
        previous_options = _option_snapshot(window)
        previous_units = getattr(window, "defaultUnits", "mm")
        previous_language = getattr(window, "uiLanguage", "en")
        previous_theme = getattr(window, "uiTheme", "light")
        previous_correction = (
            getattr(window, "correctionEnabled", True)
            if self._correction_before_show is None
            else self._correction_before_show
        )
        previous_tolerance = getattr(window, "arcTolerance", ARC_TOLERANCE_DEFAULT)
        previous_sampling = _arc_sampling_snapshot(window)
        previous_autodetect_arc_type = getattr(window, "autodetectArcType", True)
        previous_ignore_block_skip = getattr(window, "ignoreBlockSkip", False)
        previous_generated_motions = getattr(window, "maxGeneratedMotions", GENERATED_MOTIONS_DEFAULT)
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
            QMessageBox.warning(
                self,
                QCoreApplication.translate("OptionsDlg", "Options"),
                QCoreApplication.translate(
                    "OptionsDlg", "Plot colors must be valid Qt color names, for example #008000."
                ),
            )
            return
        window.fileEncoding = "cp1251" if self.ui.encodingCombo.currentIndex() else "utf-8"
        window.defaultFileType = self.ui.fileTypeCombo.currentIndex()
        window.defaultUnits = "inch" if self.ui.unitsCombo.currentIndex() else "mm"
        self._apply_language_and_theme(window, previous_language, previous_theme)
        window.loggingEnabled = self.ui.loggingCheck.isChecked()
        window.autoUpdateEnabled = self.ui.autoUpdateCheck.isChecked()
        window.autoUpdateMaxSegments = self.ui.autoUpdateMaxSegmentsSpin.value()
        window.maxGeneratedMotions = self.ui.maxGeneratedMotionsSpin.value()
        _apply_cnc_options(window, self.ui)
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
        if previous_theme != window.uiTheme:
            # The colour edits above still hold the previous theme's values, so the
            # standard colours are moved onto the new theme after they are applied.
            for key, attribute in theme.PLOT_COLOR_ATTRIBUTES.items():
                setattr(window, attribute, theme.themed_plot_value(getattr(window, attribute), key, window.uiTheme))
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
        _apply_editor_display_options(window)
        window.changeFileType(target_file_type)
        self._log_option_changes(window, previous_options)
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
        execution_changed = _execution_semantics_changed(
            window,
            previous_units=previous_units,
            correction_needs_update=correction_needs_update,
            previous_tolerance=previous_tolerance,
            previous_autodetect_arc_type=previous_autodetect_arc_type,
            previous_ignore_block_skip=previous_ignore_block_skip,
            previous_generated_motions=previous_generated_motions,
        )
        _refresh_after_option_changes(
            window,
            execution_changed=execution_changed,
            sampling_changed=previous_sampling != _arc_sampling_snapshot(window),
            correction_preview_applied=self._correction_preview_applied,
        )
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
        self.ui.languageCombo.setCurrentIndex(0)
        self.ui.themeCombo.setCurrentIndex(0)
        self.ui.loggingCheck.setChecked(False)
        self.ui.autoUpdateCheck.setChecked(True)
        self.ui.autoUpdateMaxSegmentsSpin.setValue(20000)
        self.ui.maxGeneratedMotionsSpin.setValue(GENERATED_MOTIONS_DEFAULT)
        self.ui.correctionCheck.setChecked(True)
        self.ui.autodetectArcTypeCheck.setChecked(True)
        self.ui.ignoreBlockSkipCheck.setChecked(False)
        self.ui.commentStyleCombo.setCurrentIndex(0)
        self.ui.arcSamplingPresetCombo.setCurrentIndex(1)
        self._set_arc_sampling_values(ARC_SAMPLING_PRESETS[1])
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

    def _set_arc_sampling_values(self, preset):
        _preset_id, tolerance, maximum_radius, minimum_radius, minimum_chord = preset
        self.ui.arcToleranceSpin.setValue(tolerance)
        self.ui.maximumCircularRadiusSpin.setValue(maximum_radius)
        self.ui.minimumCircularRadiusSpin.setValue(minimum_radius)
        self.ui.minimumChordLengthSpin.setValue(minimum_chord)

    def _apply_arc_sampling_preset(self, index):
        if self._loading_values or not 0 <= index < len(ARC_SAMPLING_PRESETS):
            return
        self._set_arc_sampling_values(ARC_SAMPLING_PRESETS[index])

    def _update_playback_speed_label(self, value):
        interval = playback_interval_ms(value)
        self.ui.playbackSpeedValueLabel.setText(f"{value} — {interval} ms/step")
