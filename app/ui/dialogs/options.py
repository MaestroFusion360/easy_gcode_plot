"""Application options dialog backed by the existing MainWindow settings."""

# pylint: disable=protected-access  # The dialog calls its owning window's rotary selector.

import logging

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QCoreApplication, QRegularExpression
from PyQt6.QtGui import QColor, QFont, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from app import theme
from app.gcode.comments import DEFAULT_COMMENT_STYLE, SEMICOLON, comment_markers, normalize_comment_style
from app.settings import (
    ARC_SAMPLING_PRESET_DEFAULT,
    ARC_SAMPLING_PRESETS,
    ARC_TOLERANCE_DEFAULT,
    AUTO_UPDATE_SEGMENTS_DEFAULT,
    DEFAULT_TOOLBAR_ICON_SIZE,
    GENERATED_MOTIONS_DEFAULT,
    MAXIMUM_CIRCULAR_RADIUS_DEFAULT,
    MINIMUM_CHORD_LENGTH_DEFAULT,
    MINIMUM_CIRCULAR_RADIUS_DEFAULT,
    TOOLBAR_ICON_SIZES,
    configure_logging,
)
from app.tools.discovery_rules import default_settings
from app.ui.dialogs.discovery_settings import DiscoverySettings
from app.ui.dialogs.post_profile_settings import PostProfileSettings
from app.ui.dialogs.rotary_kinematics_settings import RotaryKinematicsSettings
from app.ui.generated.dialogs.options import Ui_OptionsDlg
from app.ui.support.hotkey_editor import HotkeyEditor
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
        "auto_update_limit": getattr(window, "autoUpdateMaxSegments", AUTO_UPDATE_SEGMENTS_DEFAULT),
        "generated_motions_limit": getattr(window, "maxGeneratedMotions", GENERATED_MOTIONS_DEFAULT),
        "correction": getattr(window, "correctionEnabled", True),
        "autodetect_arc_type": getattr(window, "autodetectArcType", True),
        "lathe_gcode_system": getattr(window, "latheGcodeSystem", "A"),
        "sinumerik_840d_sl": getattr(window, "sinumerik840dSl", True),
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
        "caret_line_color": getattr(window, "caretLineColor", "#e8e8ff"),
        "caret_line_dark_color": getattr(window, "caretLineDarkColor", "#2a2d2e"),
        "editor_rapid_color": getattr(window, "editorRapidColor", "#ff0000"),
        "editor_linear_color": getattr(window, "editorLinearColor", "#2ecc71"),
        "editor_circular_color": getattr(window, "editorCircularColor", "#0000ff"),
        "eol_visible": getattr(window, "eolVisible", False),
        "whitespace_visible": getattr(window, "spaceVisible", False),
        "margin_visible": getattr(window, "marginArea", True),
        "show_stock": getattr(window, "showStock", True),
        "show_rapid": getattr(window, "plotShowRapid", True),
        "dashed_rapid": getattr(window, "plotDashedRapid", True),
        "color_by_tool": getattr(window, "plotColorByTool", False),
        "plot_grid": getattr(window, "plotGrid", False),
        "plot_axes": getattr(window, "plotAxes", True),
        "grid_step": getattr(window, "plotGridStep", 0.0),
        "line_width": getattr(window, "plotLineWidth", 1.5),
        "gradient": getattr(window, "plotBackgroundGradient", False),
        "rapid_color": getattr(window, "plotRapidColor", "#d02020"),
        "linear_color": getattr(window, "plotLineColor", "#0000ff"),
        "arc_color": getattr(window, "plotArcColor", "#008000"),
        "current_color": getattr(window, "plotCurrentColor", "#00b7ff"),
        "tool_color": getattr(window, "plotToolColor", "#e3aa37"),
        "background_color": getattr(window, "plotBackground", "#ffffff"),
        "stock_color": getattr(window, "plotStockColor", "#4fa7a0"),
        "cut_color": getattr(window, "plotCutColor", "#b8a879"),
        "stl_color": getattr(window, "stlColor", "#b0b0b0"),
        "stl_wireframe": getattr(window, "stlWireframe", False),
        "rotary_kinematics": getattr(window, "rotaryKinematics", None),
        "playback_speed": getattr(window, "playbackSpeed", 3),
        "toolbar_icon_size": getattr(window, "toolbarIconSize", DEFAULT_TOOLBAR_ICON_SIZE),
        "tool_discovery": getattr(window, "toolDiscovery", default_settings()),
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
    previous_lathe_gcode_system,
    previous_sinumerik_840d_sl,
):
    return any(
        (
            previous_units != window.defaultUnits,
            correction_needs_update,
            previous_tolerance != window.arcTolerance,
            previous_autodetect_arc_type != window.autodetectArcType,
            previous_ignore_block_skip != window.ignoreBlockSkip,
            previous_generated_motions != window.maxGeneratedMotions,
            previous_lathe_gcode_system != window.latheGcodeSystem,
            previous_sinumerik_840d_sl != window.sinumerik840dSl,
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
    window.lexer.set_comment_style(getattr(window, "_document_comment_style", None) or window.commentStyle)


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


def _refresh_after_option_changes(window, *, execution_changed, sampling_changed):
    if execution_changed and getattr(window, "execution_result", None) is not None:
        window.updateData()
    elif sampling_changed and getattr(window, "execution_result", None) is not None:
        window.rerenderCurrentResult()
    else:
        window.refreshPlotView()


class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_OptionsDlg()
        self.ui.setupUi(self)
        tabs = self.ui.tabs
        ordered_pages = sorted(
            (tabs.widget(index) for index in range(tabs.count())),
            key=lambda page: (page is not self.ui.generalTab, tabs.tabText(tabs.indexOf(page)).casefold()),
        )
        for index, page in enumerate(ordered_pages):
            tabs.tabBar().moveTab(tabs.indexOf(page), index)
        self.discoverySettings = DiscoverySettings(self)
        self.postProfileSettings = PostProfileSettings(self)
        self.ui.latheGcodeSystemCombo = QComboBox(self)
        self.ui.latheGcodeSystemCombo.setObjectName("latheGcodeSystemCombo")
        self.ui.latheGcodeSystemCombo.addItem("FANUC Lathe Type A", "A")
        self.ui.latheGcodeSystemCombo.addItem("FANUC Lathe Type B", "B")
        self.ui.latheGcodeSystemCombo.setToolTip(
            "Dialect of the source program. Select the output controller in Export / Target CNC."
        )
        self.ui.generalForm.addRow(QLabel("Source lathe G-code system", self), self.ui.latheGcodeSystemCombo)
        self._configure_sinumerik_cycles_control()
        self.rotarySettings = RotaryKinematicsSettings(self)
        self._configure_caret_line_color()
        self._configure_stock_colors()
        self.hotkeyEditor = HotkeyEditor(self)
        self._color_controls = (
            (self.ui.caretLineColorButton, self.ui.caretLineColorEdit),
            (self.ui.caretLineDarkColorButton, self.ui.caretLineDarkColorEdit),
            (self.ui.editorRapidColorButton, self.ui.editorRapidColorEdit),
            (self.ui.editorLinearColorButton, self.ui.editorLinearColorEdit),
            (self.ui.editorCircularColorButton, self.ui.editorCircularColorEdit),
            (self.ui.rapidColorButton, self.ui.rapidColorEdit),
            (self.ui.linearColorButton, self.ui.linearColorEdit),
            (self.ui.arcColorButton, self.ui.arcColorEdit),
            (self.ui.currentColorButton, self.ui.currentColorEdit),
            (self.ui.toolColorButton, self.ui.toolColorEdit),
            (self.ui.backgroundColorButton, self.ui.backgroundColorEdit),
            (self.ui.stlColorButton, self.ui.stlColorEdit),
            (self.ui.stockColorButton, self.ui.stockColorEdit),
            (self.ui.cutColorButton, self.ui.cutColorEdit),
        )
        validator = QRegularExpressionValidator(QRegularExpression(r"^#[0-9A-Fa-f]{6}$"), self)
        for button, edit in self._color_controls:
            button.clicked.connect(lambda _checked=False, target=edit: self.pick_color(target))
            edit.setValidator(validator)
            edit.textChanged.connect(lambda _text, target=edit, swatch=button: self._update_swatch(swatch, target))
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        self.ui.playbackSpeedSlider.valueChanged.connect(self._update_playback_speed_label)
        self.ui.arcSamplingPresetCombo.currentIndexChanged.connect(self._apply_arc_sampling_preset)
        self.ui.showRapidCheck.toggled.connect(self.ui.dashedRapidCheck.setEnabled)
        self._loading_values = False

    def _configure_caret_line_color(self):
        self.ui.caretLineColorButton, self.ui.caretLineColorEdit = self._editor_color_row(
            "caretLineColor", QCoreApplication.translate("OptionsDlg", "Current line (light theme)")
        )
        self.ui.caretLineDarkColorButton, self.ui.caretLineDarkColorEdit = self._editor_color_row(
            "caretLineDarkColor", QCoreApplication.translate("OptionsDlg", "Current line (dark theme)")
        )
        self.ui.editorRapidColorButton, self.ui.editorRapidColorEdit = self._editor_color_row("editorRapidColor", "G0")
        self.ui.editorLinearColorButton, self.ui.editorLinearColorEdit = self._editor_color_row(
            "editorLinearColor", "G1"
        )
        self.ui.editorCircularColorButton, self.ui.editorCircularColorEdit = self._editor_color_row(
            "editorCircularColor", "G2 / G3"
        )

    def _editor_color_row(self, name, label):
        button = QPushButton(self.ui.editorColorsGroup)
        button.setObjectName(name + "Button")
        edit = QLineEdit(self.ui.editorColorsGroup)
        edit.setObjectName(name + "Edit")
        edit.setMaxLength(7)
        row = QHBoxLayout()
        row.addWidget(button)
        row.addWidget(edit)
        self.ui.editorColorsForm.addRow(label, row)
        return button, edit

    def _configure_stock_colors(self):
        self.ui.stockColorButton, self.ui.stockColorEdit = self._create_stock_color(
            "stockColor", QCoreApplication.translate("OptionsDlg", "Stock material")
        )
        self.ui.cutColorButton, self.ui.cutColorEdit = self._create_stock_color(
            "cutColor", QCoreApplication.translate("OptionsDlg", "Removed material")
        )

    def _create_stock_color(self, name, label):
        button = QPushButton(self.ui.plotColorsGroup)
        button.setObjectName(name + "Button")
        edit = QLineEdit(self.ui.plotColorsGroup)
        edit.setObjectName(name + "Edit")
        edit.setMaxLength(7)
        row = QHBoxLayout()
        row.addWidget(button)
        row.addWidget(edit)
        self.ui.colorsForm.addRow(label, row)
        return button, edit

    def _configure_sinumerik_cycles_control(self):
        self.ui.sinumerik840dSlCheck = QCheckBox(
            QCoreApplication.translate("OptionsDlg", "840D Extended cycles"), self.ui.generalTab
        )
        self.ui.sinumerik840dSlCheck.setObjectName("sinumerik840dSlCheck")
        self.ui.sinumerik840dSlCheck.setToolTip(
            QCoreApplication.translate(
                "OptionsDlg",
                "Checked: 840D Extended cycles interface (Siemens 03/2009). "
                "Unchecked: classic cycle interface (Siemens 01/2008). "
                "Applies to native source cycles and native SINUMERIK export.",
            )
        )
        self.ui.generalForm.addRow(self.ui.sinumerik840dSlCheck)

    def sync_rotary_kinematics(self, profile_id):
        # Browsing profiles does not change the active selection in Settings.
        pass

    @staticmethod
    def _update_swatch(button, edit):
        color = QColor(edit.text())
        button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #666;" if color.isValid() else "")

    def showEvent(self, event):
        self.postProfileSettings.reload()
        self.rotarySettings.reload()
        self.load_values()
        LOGGER.debug("options_opened values=%s", _option_snapshot(self.parent()))
        super().showEvent(event)

    def load_values(self):
        window = self.parent()
        self.discoverySettings.load(getattr(window, "toolDiscovery", default_settings()))
        self.hotkeyEditor.load(window)
        self.ui.encodingCombo.setCurrentIndex(1 if getattr(window, "fileEncoding", "utf-8") == "cp1251" else 0)
        self.ui.fileTypeCombo.setCurrentIndex(
            getattr(window, "defaultFileType", window.ui.fileTypeCombo.currentIndex())
        )
        self.ui.unitsCombo.setCurrentIndex(1 if getattr(window, "defaultUnits", "mm") == "inch" else 0)
        self.ui.latheGcodeSystemCombo.setCurrentIndex(1 if getattr(window, "latheGcodeSystem", "A") == "B" else 0)
        self.ui.sinumerik840dSlCheck.setChecked(getattr(window, "sinumerik840dSl", True))
        self.ui.languageCombo.setCurrentIndex(1 if getattr(window, "uiLanguage", "en") == "ru" else 0)
        self.ui.themeCombo.setCurrentIndex(1 if getattr(window, "uiTheme", "light") == "dark" else 0)
        icon_size = getattr(window, "toolbarIconSize", DEFAULT_TOOLBAR_ICON_SIZE)
        self.ui.toolpanelIconsCombo.setCurrentIndex(
            TOOLBAR_ICON_SIZES.index(icon_size) if icon_size in TOOLBAR_ICON_SIZES else 1
        )
        self.ui.loggingCheck.setChecked(getattr(window, "loggingEnabled", False))
        self.ui.autoUpdateCheck.setChecked(getattr(window, "autoUpdateEnabled", True))
        self.ui.autoUpdateMaxSegmentsSpin.setValue(
            getattr(window, "autoUpdateMaxSegments", AUTO_UPDATE_SEGMENTS_DEFAULT)
        )
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
        self.ui.caretLineColorEdit.setText(window.caretLineColor)
        self._update_swatch(self.ui.caretLineColorButton, self.ui.caretLineColorEdit)
        self.ui.caretLineDarkColorEdit.setText(window.caretLineDarkColor)
        self._update_swatch(self.ui.caretLineDarkColorButton, self.ui.caretLineDarkColorEdit)
        self.ui.eolCheck.setChecked(window.eolVisible)
        self.ui.whitespaceCheck.setChecked(window.spaceVisible)
        self.ui.marginCheck.setChecked(window.marginArea)
        self._load_plot_values(window)

    def _load_plot_values(self, window):
        """Populate plot appearance and playback controls."""
        for attribute in theme.EDITOR_MOVE_COLOR_ATTRIBUTES.values():
            getattr(self.ui, attribute + "Edit").setText(getattr(window, attribute))
        self.ui.rapidColorEdit.setText(getattr(window, "plotRapidColor", "#d02020"))
        self.ui.linearColorEdit.setText(window.plotLineColor)
        self.ui.arcColorEdit.setText(getattr(window, "plotArcColor", "#008000"))
        self.ui.currentColorEdit.setText(getattr(window, "plotCurrentColor", "#00b7ff"))
        self.ui.toolColorEdit.setText(getattr(window, "plotToolColor", "#e3aa37"))
        self.ui.backgroundColorEdit.setText(window.plotBackground)
        self.ui.backgroundGradientCheck.setChecked(getattr(window, "plotBackgroundGradient", False))
        self.ui.stlColorEdit.setText(getattr(window, "stlColor", "#b0b0b0"))
        self.ui.stockColorEdit.setText(getattr(window, "plotStockColor", "#4fa7a0"))
        self.ui.cutColorEdit.setText(getattr(window, "plotCutColor", "#b8a879"))
        self.ui.stlWireframeCheck.setChecked(getattr(window, "stlWireframe", False))
        self.ui.lineWidthSpin.setValue(getattr(window, "plotLineWidth", 1.5))
        self.ui.gridStepSpin.setValue(getattr(window, "plotGridStep", 0.0))
        self.ui.axesCheck.setChecked(getattr(window, "plotAxes", True))
        self.ui.gridCheck.setChecked(window.plotGrid)
        self.ui.showRapidCheck.setChecked(getattr(window, "plotShowRapid", True))
        self.ui.dashedRapidCheck.setChecked(getattr(window, "plotDashedRapid", True))
        self.ui.dashedRapidCheck.setEnabled(self.ui.showRapidCheck.isChecked())
        self.ui.colorByToolCheck.setChecked(getattr(window, "plotColorByTool", False))
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

    def _selected_hotkeys(self):
        hotkeys = self.hotkeyEditor.values
        assigned = [value for value in hotkeys.values() if value]
        if len(assigned) != len(set(assigned)):
            QMessageBox.warning(
                self,
                QCoreApplication.translate("OptionsDlg", "Options"),
                QCoreApplication.translate("OptionsDlg", "Hotkeys must be unique."),
            )
            return None
        return hotkeys

    def _valid_colors(self, color_edits):
        if all(QColor(edit.text()).isValid() for edit in color_edits):
            return True
        QMessageBox.warning(
            self,
            QCoreApplication.translate("OptionsDlg", "Options"),
            QCoreApplication.translate("OptionsDlg", "Colors must be valid Qt color names, for example #008000."),
        )
        return False

    def _apply_hotkeys(self, window):
        hotkeys = self._selected_hotkeys()
        if hotkeys is None:
            return False
        window.setHotkeys(hotkeys)
        return True

    @staticmethod
    def _apply_plot_colors(window, color_edits, previous_theme):
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
            # The edits hold the previous theme's colours until the new theme is applied.
            for key, attribute in theme.PLOT_COLOR_ATTRIBUTES.items():
                setattr(window, attribute, theme.themed_plot_value(getattr(window, attribute), key, window.uiTheme))

    def _apply_plot_options(self, window, color_edits, previous_theme):
        """Apply the Plot tab without changing execution semantics."""
        self._apply_plot_colors(window, color_edits, previous_theme)
        window.plotStockColor = self.ui.stockColorEdit.text()
        window.plotCutColor = self.ui.cutColorEdit.text()
        window.plotBackgroundGradient = self.ui.backgroundGradientCheck.isChecked()
        window.stlWireframe = self.ui.stlWireframeCheck.isChecked()
        window.plotLineWidth = self.ui.lineWidthSpin.value()
        window.plotGridStep = self.ui.gridStepSpin.value()
        window.plotAxes = self.ui.axesCheck.isChecked()
        window.plotGrid = self.ui.gridCheck.isChecked()
        window.showStock = self.ui.showStockCheck.isChecked()
        window.plotShowRapid = self.ui.showRapidCheck.isChecked()
        window.plotDashedRapid = self.ui.dashedRapidCheck.isChecked()
        window.plotColorByTool = self.ui.colorByToolCheck.isChecked()
        if self.ui.playbackSpeedSlider.value() != window.playbackSpeed:
            window.setPlaybackSpeed(self.ui.playbackSpeedSlider.value(), refresh_stock=False)

    def accept(self):
        window = self.parent()
        previous_options = _option_snapshot(window)
        previous_units = getattr(window, "defaultUnits", "mm")
        previous_language = getattr(window, "uiLanguage", "en")
        previous_theme = getattr(window, "uiTheme", "light")
        previous_correction = getattr(window, "correctionEnabled", True)
        selected_rotary = getattr(window, "rotaryKinematics", None)
        previous_tolerance = getattr(window, "arcTolerance", ARC_TOLERANCE_DEFAULT)
        previous_sampling = _arc_sampling_snapshot(window)
        previous_autodetect_arc_type = getattr(window, "autodetectArcType", True)
        previous_lathe_gcode_system = getattr(window, "latheGcodeSystem", "A")
        previous_sinumerik_840d_sl = getattr(window, "sinumerik840dSl", True)
        previous_ignore_block_skip = getattr(window, "ignoreBlockSkip", False)
        previous_generated_motions = getattr(window, "maxGeneratedMotions", GENERATED_MOTIONS_DEFAULT)
        previous_show_stock = getattr(window, "showStock", True)
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
        if not self._validate_pending_options(window):
            return
        selected_encoding = "cp1251" if self.ui.encodingCombo.currentIndex() else "utf-8"
        if selected_encoding != getattr(window, "fileEncoding", "utf-8") and getattr(window, "curFile", ""):
            window._document_encoding = selected_encoding
        window.fileEncoding = selected_encoding
        window.defaultFileType = self.ui.fileTypeCombo.currentIndex()
        window.defaultUnits = "inch" if self.ui.unitsCombo.currentIndex() else "mm"
        self._apply_language_and_theme(window, previous_language, previous_theme)
        window.toolbarIconSize = TOOLBAR_ICON_SIZES[self.ui.toolpanelIconsCombo.currentIndex()]
        window.applyToolbarIconSize(window.toolbarIconSize)
        window.loggingEnabled = self.ui.loggingCheck.isChecked()
        window.autoUpdateEnabled = self.ui.autoUpdateCheck.isChecked()
        window.autoUpdateMaxSegments = self.ui.autoUpdateMaxSegmentsSpin.value()
        window.maxGeneratedMotions = self.ui.maxGeneratedMotionsSpin.value()
        _apply_cnc_options(window, self.ui)
        window.toolDiscovery = self.discoverySettings.document
        window.latheGcodeSystem = self.ui.latheGcodeSystemCombo.currentData()
        window.sinumerik840dSl = self.ui.sinumerik840dSlCheck.isChecked()
        window.fontFamily = self.ui.fontCombo.currentFont().family()
        window.sizeTxt = self.ui.fontSizeSpin.value()
        window.caretLine = self.ui.caretLineCheck.isChecked()
        window.caretLineColor = self.ui.caretLineColorEdit.text()
        window.caretLineDarkColor = self.ui.caretLineDarkColorEdit.text()
        self._apply_editor_motion_colors(window)
        window.eolVisible = self.ui.eolCheck.isChecked()
        window.spaceVisible = self.ui.whitespaceCheck.isChecked()
        window.marginArea = self.ui.marginCheck.isChecked()
        self._apply_plot_options(window, color_edits, previous_theme)
        target_file_type = window.defaultFileType
        signals_blocked = window.ui.fileTypeCombo.blockSignals(True)
        window.ui.fileTypeCombo.setCurrentIndex(target_file_type)
        window.ui.fileTypeCombo.blockSignals(signals_blocked)
        window.syncFileTypeMenu(target_file_type)
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
        correction_needs_update = previous_correction != window.correctionEnabled
        execution_changed = _execution_semantics_changed(
            window,
            previous_units=previous_units,
            correction_needs_update=correction_needs_update,
            previous_tolerance=previous_tolerance,
            previous_autodetect_arc_type=previous_autodetect_arc_type,
            previous_ignore_block_skip=previous_ignore_block_skip,
            previous_generated_motions=previous_generated_motions,
            previous_lathe_gcode_system=previous_lathe_gcode_system,
            previous_sinumerik_840d_sl=previous_sinumerik_840d_sl,
        )
        self._commit_refresh(
            window,
            previous_options,
            selected_rotary,
            execution_changed,
            previous_sampling != _arc_sampling_snapshot(window),
        )
        super().accept()

    def _validate_pending_options(self, window):
        return (
            self.discoverySettings.validate()
            and self._valid_colors(tuple(edit for _, edit in self._color_controls))
            and self._apply_hotkeys(window)
            and self.postProfileSettings.apply()
            and self.rotarySettings.apply()
        )

    def _commit_refresh(self, window, previous_options, selected_rotary, execution_changed, sampling_changed):
        execution_changed |= previous_options["tool_discovery"] != window.toolDiscovery
        profiles_changed = bool(self.rotarySettings.changed_ids)
        if profiles_changed:
            window._refresh_rotary_kinematics_menu()
        rotary_changed = selected_rotary != getattr(window, "rotaryKinematics", None)
        if rotary_changed or selected_rotary in self.rotarySettings.changed_ids:
            window._select_rotary_kinematics(selected_rotary, force_refresh=True)
        elif execution_changed or sampling_changed or self._plot_options_changed(window, previous_options):
            _refresh_after_option_changes(
                window, execution_changed=execution_changed, sampling_changed=sampling_changed
            )
        elif (
            previous_options["playback_speed"] != window.playbackSpeed
            and getattr(window, "_stock_animation_active", False)
            and not window.latheMode
        ):
            window._request_milling_stock_quality()
        self.rotarySettings.reload()

    @staticmethod
    def _plot_options_changed(window, previous):
        current = _option_snapshot(window)
        keys = (
            "show_stock",
            "show_rapid",
            "dashed_rapid",
            "color_by_tool",
            "plot_grid",
            "plot_axes",
            "grid_step",
            "line_width",
            "gradient",
            "rapid_color",
            "linear_color",
            "arc_color",
            "current_color",
            "tool_color",
            "background_color",
            "stock_color",
            "cut_color",
        )
        return any(previous[key] != current[key] for key in keys)

    def reject(self):
        self.postProfileSettings.discard()
        self.rotarySettings.reload()
        LOGGER.info("options_cancelled")
        super().reject()

    def pick_color(self, target):
        color = QColorDialog.getColor(QColor(target.text()), self, "Select color")
        if color.isValid():
            target.setText(color.name())

    def _apply_editor_motion_colors(self, window):
        for key, attribute in theme.EDITOR_MOVE_COLOR_ATTRIBUTES.items():
            value = getattr(self.ui, attribute + "Edit").text()
            setattr(window, attribute, theme.themed_editor_move_value(value, key, window.uiTheme))
        window._apply_editor_theme()

    def restore_defaults(self):
        self.discoverySettings.restore_defaults()
        LOGGER.debug("options_restore_defaults_requested")
        self.ui.sinumerik840dSlCheck.setChecked(True)
        self.hotkeyEditor.reset_defaults()
        self.ui.encodingCombo.setCurrentIndex(0)
        self.ui.fileTypeCombo.setCurrentIndex(0)
        self.ui.unitsCombo.setCurrentIndex(0)
        self.ui.languageCombo.setCurrentIndex(0)
        self.ui.themeCombo.setCurrentIndex(0)
        self.ui.toolpanelIconsCombo.setCurrentIndex(1)
        self.ui.loggingCheck.setChecked(False)
        self.ui.autoUpdateCheck.setChecked(True)
        self.ui.autoUpdateMaxSegmentsSpin.setValue(AUTO_UPDATE_SEGMENTS_DEFAULT)
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
        self.ui.caretLineColorEdit.setText("#e8e8ff")
        self.ui.caretLineDarkColorEdit.setText("#2a2d2e")
        for key, attribute in theme.EDITOR_MOVE_COLOR_ATTRIBUTES.items():
            getattr(self.ui, attribute + "Edit").setText(theme.editor_colors("light")[key])
        self.ui.eolCheck.setChecked(False)
        self.ui.whitespaceCheck.setChecked(False)
        self.ui.marginCheck.setChecked(True)
        self.ui.showStockCheck.setChecked(True)
        for edit, value in (
            (self.ui.rapidColorEdit, "#d02020"),
            (self.ui.linearColorEdit, "#0000ff"),
            (self.ui.arcColorEdit, "#008000"),
            (self.ui.currentColorEdit, "#00b7ff"),
            (self.ui.toolColorEdit, "#e3aa37"),
            (self.ui.backgroundColorEdit, "#ffffff"),
            (self.ui.stlColorEdit, "#b0b0b0"),
            (self.ui.stockColorEdit, "#4fa7a0"),
            (self.ui.cutColorEdit, "#b8a879"),
        ):
            edit.setText(value)
        self.ui.backgroundGradientCheck.setChecked(False)
        self.ui.stlWireframeCheck.setChecked(False)
        self.ui.lineWidthSpin.setValue(1.5)
        self.ui.gridStepSpin.setValue(0.0)
        self.ui.axesCheck.setChecked(True)
        self.ui.gridCheck.setChecked(False)
        self.ui.showRapidCheck.setChecked(True)
        self.ui.dashedRapidCheck.setChecked(True)
        self.ui.colorByToolCheck.setChecked(False)
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
