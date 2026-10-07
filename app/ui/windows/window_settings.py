"""Persistence and editor/plot preference handling for the main window."""

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QKeySequence, QVector3D
from PyQt6.QtWidgets import QApplication

from app import theme
from app.gcode.comments import DEFAULT_COMMENT_STYLE, comment_markers, normalize_comment_style
from app.gcode.export import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
)
from app.settings import (
    ARC_SAMPLING_PRESET_DEFAULT,
    ARC_SAMPLING_PRESETS,
    ARC_TOLERANCE_DEFAULT,
    ARC_TOLERANCE_MAX,
    ARC_TOLERANCE_MIN,
    AUTO_UPDATE_SEGMENTS_DEFAULT,
    AUTO_UPDATE_SEGMENTS_MAX,
    AUTO_UPDATE_SEGMENTS_MIN,
    DEFAULT_TOOLBAR_ICON_SIZE,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    GENERATED_MOTIONS_DEFAULT,
    GENERATED_MOTIONS_MAX,
    GENERATED_MOTIONS_MIN,
    LINE_WIDTH_MAX,
    LINE_WIDTH_MIN,
    MAXIMUM_CIRCULAR_RADIUS_DEFAULT,
    MAXIMUM_CIRCULAR_RADIUS_MAX,
    MAXIMUM_CIRCULAR_RADIUS_MIN,
    MINIMUM_CHORD_LENGTH_DEFAULT,
    MINIMUM_CHORD_LENGTH_MAX,
    MINIMUM_CHORD_LENGTH_MIN,
    MINIMUM_CIRCULAR_RADIUS_DEFAULT,
    MINIMUM_CIRCULAR_RADIUS_MAX,
    MINIMUM_CIRCULAR_RADIUS_MIN,
    TOOLBAR_ICON_SIZES,
    ToolLibraryLoadError,
    bounded_number,
    configure_logging,
    get_settings,
    load_tool_libraries,
)
from app.settings import (
    normalized_recent_files as _normalized_recent_files,
)
from app.ui.support.hotkeys import LEGACY_KEYS, is_reserved_shortcut, menu_commands, portable_shortcut
from app.ui.support.lexer import GcodeLexer
from app.ui.windows.main_window_execution import playback_interval_ms, playback_speed_level

EDITOR_FONT_FAMILY_KEY = "FONT_FAMILY"
EDITOR_FONT_SIZE_KEY = "FONT_SIZE"
EDITOR_FONT_WEIGHT_KEY = "FONT_WEIGHT"
EDITOR_FONT_ITALIC_KEY = "FONT_ITALIC"


@dataclass(frozen=True)
class _SettingSpec:
    key: str
    attribute: str
    default: object
    value_type: type
    validator: Callable[[object], object] | None = None


_STOCK_SETTINGS = (
    _SettingSpec("CONFIGURED", "stockConfigured", False, bool),
    _SettingSpec("ENABLED", "stockEnabled", False, bool),
    _SettingSpec("DIAMETER", "turnStockDiameter", 50.0, float),
    _SettingSpec("INNER_DIAMETER", "turnStockInnerDiameter", 0.0, float),
    _SettingSpec("LENGTH", "turnStockLength", 100.0, float),
    _SettingSpec("RESOLUTION", "turnStockResolution", 0.5, float),
    _SettingSpec("FRONT_ALLOWANCE", "turnStockFrontAllowance", 2.0, float),
)

_PLOT_SETTINGS = (
    _SettingSpec("ARC_TYPE", "arc_type", 1, int),
    _SettingSpec("MACHINE_XPOS", "xPosMach", 0.0, float),
    _SettingSpec("MACHINE_YPOS", "yPosMach", 0.0, float),
    _SettingSpec("MACHINE_ZPOS", "zPosMach", 0.0, float),
    _SettingSpec("LATHE_MODE", "latheMode", False, bool),
    _SettingSpec("SHOW_STOCK", "showStock", True, bool),
    _SettingSpec("SHOW_RAPID", "plotShowRapid", True, bool),
    _SettingSpec("DASHED_RAPID", "plotDashedRapid", True, bool),
    _SettingSpec("COLOR_BY_TOOL", "plotColorByTool", False, bool),
    _SettingSpec(
        "LINE_WIDTH",
        "plotLineWidth",
        1.5,
        float,
        lambda value: bounded_number(value, 1.5, LINE_WIDTH_MIN, LINE_WIDTH_MAX, name="PLOT/LINE_WIDTH"),
    ),
    _SettingSpec("GRID_STEP", "plotGridStep", 0.0, float),
    _SettingSpec("AXES", "plotAxes", True, bool),
    _SettingSpec("BACKGROUND_GRADIENT", "plotBackgroundGradient", False, bool),
    _SettingSpec("STL_WIREFRAME", "stlWireframe", False, bool),
    _SettingSpec("GRID", "plotGrid", False, bool),
    _SettingSpec("GRID_SIZE", "plotGridSize", 1000, int),
    _SettingSpec("GRID_SPACING", "plotGridSpacing", 50, int),
)

_CNC_SETTINGS = (
    _SettingSpec("SINUMERIK_840D_SL", "sinumerik840dSl", True, bool),
    _SettingSpec("HOME_CONFIGURED", "homeConfigured", True, bool),
    _SettingSpec("DEFAULT_UNITS", "defaultUnits", "mm", str),
    _SettingSpec(
        "LATHE_GCODE_SYSTEM", "latheGcodeSystem", "A", str, lambda value: value if value in {"A", "B"} else "A"
    ),
    _SettingSpec("CORRECTION_ENABLED", "correctionEnabled", True, bool),
    _SettingSpec("AUTODETECT_ARC_TYPE", "autodetectArcType", True, bool),
    _SettingSpec("IGNORE_BLOCK_SKIP", "ignoreBlockSkip", False, bool),
)

_EDITOR_SETTINGS = (
    _SettingSpec("CARETLINE_COLOR", "caretLineColor", "#e8e8ff", str),
    _SettingSpec("ENCODING", "fileEncoding", "utf-8", str),
    _SettingSpec("DEFAULT_FILE_TYPE", "defaultFileType", 0, int),
    _SettingSpec("CARETLINE_VISIBLE", "caretLine", True, bool),
    _SettingSpec("EOL_VISIBLE", "eolVisible", False, bool),
    _SettingSpec("WHITESPACE_VISIBLE", "spaceVisible", False, bool),
    _SettingSpec("MARGIN_AREA", "marginArea", True, bool),
    _SettingSpec("MARGIN_COLOR", "marginColor", "#808080", str),
    _SettingSpec("MARGIN_FONT_FAMILY", "marginFontFamily", "Courier New", str),
    _SettingSpec("MARGIN_FONT_SIZE", "marginSizeTxt", 11, int),
    _SettingSpec(EDITOR_FONT_FAMILY_KEY, "fontFamily", "Courier New", str),
    _SettingSpec(
        EDITOR_FONT_SIZE_KEY,
        "sizeTxt",
        12,
        int,
        lambda value: int(bounded_number(value, 12, FONT_SIZE_MIN, FONT_SIZE_MAX, name="EDITOR/FONT_SIZE")),
    ),
    _SettingSpec(EDITOR_FONT_WEIGHT_KEY, "fontWeight", 500, int),
    _SettingSpec(EDITOR_FONT_ITALIC_KEY, "fontItalic", False, bool),
)

_GENERAL_SETTINGS = (
    _SettingSpec("LANGUAGE", "uiLanguage", "en", str),
    _SettingSpec("LOGGING", "loggingEnabled", False, bool),
    _SettingSpec("AUTO_UPDATE", "autoUpdateEnabled", True, bool),
    _SettingSpec(
        "AUTO_UPDATE_MAX_SEGMENTS",
        "autoUpdateMaxSegments",
        AUTO_UPDATE_SEGMENTS_DEFAULT,
        int,
        lambda value: int(
            bounded_number(
                value,
                AUTO_UPDATE_SEGMENTS_DEFAULT,
                AUTO_UPDATE_SEGMENTS_MIN,
                AUTO_UPDATE_SEGMENTS_MAX,
                name="GENERAL/AUTO_UPDATE_MAX_SEGMENTS",
            )
        ),
    ),
    _SettingSpec(
        "MAX_GENERATED_MOTIONS",
        "maxGeneratedMotions",
        GENERATED_MOTIONS_DEFAULT,
        int,
        lambda value: int(
            bounded_number(
                value,
                GENERATED_MOTIONS_DEFAULT,
                GENERATED_MOTIONS_MIN,
                GENERATED_MOTIONS_MAX,
                name="GENERAL/MAX_GENERATED_MOTIONS",
            )
        ),
    ),
)

_EXPORT_SETTINGS = (
    _SettingSpec("TARGET_CNC", "exportTargetCnc", 0, int, lambda value: value if value in {0, 1, 2, 3, 4, 5} else 0),
    _SettingSpec("INCREMENTAL_MODE", "incrMode", False, bool),
    _SettingSpec("START_PROGRAM", "startPgmExp", "O0001", str),
    _SettingSpec("END_PROGRAM", "endPgmExp", "M30", str),
    _SettingSpec("SAFETY_LINE", "safLine", False, bool),
    _SettingSpec("SEQ_NUM", "seqNum", False, bool),
    _SettingSpec("SEQ_NUM_START", "seqNumStart", 1, int),
    _SettingSpec("SEQ_NUM_INCR", "seqNumIncr", 1, int),
    _SettingSpec("SEQ_NUM_SPACING", "seqNumSpacing", False, bool),
    _SettingSpec("DELIMITER", "delim", False, bool),
    _SettingSpec("LEADING_ZERO", "leadingZero", False, bool),
    _SettingSpec("MODAL_FEED", "modalFeed", True, bool),
    _SettingSpec(
        "DECIMAL_PLACES",
        "exportDecimalPlaces",
        6,
        int,
        lambda value: value if isinstance(value, int) and 0 <= value <= 12 else 6,
    ),
    _SettingSpec("FORCE_DECIMAL", "exportForceDecimal", False, bool),
    _SettingSpec("PLUS_OUTPUT", "exportPlusOutput", False, bool),
    _SettingSpec("ER_CHAR", "er", "%", str),
)


def _visible_window_position(x, y, width, height, geometries, primary_geometry=None):
    """Clamp a restored top-level window to an available screen."""
    areas = [geometry for geometry in geometries if geometry.isValid()]
    if not areas:
        return x, y

    window = QRect(x, y, max(1, width), max(1, height))

    def overlap_area(area):
        overlap = area.intersected(window)
        return max(0, overlap.width()) * max(0, overlap.height())

    target = max(areas, key=overlap_area)
    if overlap_area(target) == 0 and primary_geometry is not None and primary_geometry.isValid():
        target = primary_geometry

    max_x = max(target.left(), target.right() - width + 1)
    max_y = max(target.top(), target.bottom() - height + 1)
    return (
        min(max(x, target.left()), max_x),
        min(max(y, target.top()), max_y),
    )


class MainWindowSettingsMixin:
    """Load and save the existing 1.x main-window preferences."""

    def loadSettings(self):
        """Load application, editor, and plot settings from the ini file."""
        self.curFile = ""
        self.setCurrentFile("")
        self.setAcceptDrops(True)

        # logging.basicConfig(level=logging.DEBUG, filename="main.log")

        self.settings = get_settings()
        self._load_hotkeys()
        recent = self.settings.value("FILE/RECENT_FILES", [])
        if isinstance(recent, str):
            recent = [recent]
        self.recentFiles = _normalized_recent_files(recent)
        recent_stl = self.settings.value("FILE/RECENT_STL_FILES", [])
        if isinstance(recent_stl, str):
            recent_stl = [recent_stl]
        self.recentStlFiles = _normalized_recent_files(recent_stl)

        # Plot
        self.dist = 100
        self.rapidFeed = 10000
        self.ui.graphicsView.opts["center"] = QVector3D(0, 0, 0)

        self._load_playback_speed()
        self._load_setting_group("PLOT", _PLOT_SETTINGS)

        if self.arc_type == 2:
            self.ui.actionAbsolute.setChecked(True)
        elif self.arc_type == 3:
            self.ui.actionRadius_value.setChecked(True)
        else:
            self.ui.actionRelative_to_start.setChecked(True)

        self._load_setting_group("CNC", _CNC_SETTINGS)
        self.wcsOffsets = {
            code: (
                self.settings.value(f"CNC/G{code}_X", 0.0, type=float),
                self.settings.value(f"CNC/G{code}_Y", 0.0, type=float),
                self.settings.value(f"CNC/G{code}_Z", 0.0, type=float),
            )
            for code in range(54, 60)
        }
        self._load_tool_libraries()
        self.ui.actionLatheMode.setChecked(self.latheMode)
        self.uiTheme = theme.normalize_theme(self.settings.value("GENERAL/THEME", theme.DEFAULT_THEME))
        stored_icon_size = self.settings.value("GENERAL/TOOLBAR_ICON_SIZE", DEFAULT_TOOLBAR_ICON_SIZE, type=int)
        self.toolbarIconSize = stored_icon_size if stored_icon_size in TOOLBAR_ICON_SIZES else DEFAULT_TOOLBAR_ICON_SIZE
        self.applyToolbarIconSize(self.toolbarIconSize)
        self._load_plot_colors()
        self._load_setting_group("STOCK", _STOCK_SETTINGS)
        # FRONT_Z is the absolute front face of manually configured stock.
        # Older settings used FRONT_ALLOWANCE for both meanings, so fall back to
        # that value until the first manual stock save writes FRONT_Z explicitly.
        self.turnStockFrontZ = self.settings.value(
            "STOCK/FRONT_Z",
            self.turnStockFrontAllowance,
            type=float,
        )
        self.ui.actionGrid.setChecked(self.plotGrid)
        self._load_setting_group("EDITOR", _EDITOR_SETTINGS)
        self.arcTolerance = bounded_number(
            self.settings.value("CNC/ARC_TOLERANCE", ARC_TOLERANCE_DEFAULT),
            ARC_TOLERANCE_DEFAULT,
            ARC_TOLERANCE_MIN,
            ARC_TOLERANCE_MAX,
            name="CNC/ARC_TOLERANCE",
        )
        self._load_arc_sampling_settings()
        self._load_setting_group("GENERAL", _GENERAL_SETTINGS)
        configure_logging(self.loggingEnabled)

        # Editor
        self.ui.editor.setUtf8(True)
        self.ui.editor.setTabWidth(4)
        self.ui.editor.setEolMode(QsciScintilla.EolMode.EolWindows)
        self.ui.editor.setIndentationsUseTabs(False)
        self.ui.editor.setIndentationGuides(True)
        self.ui.editor.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

        self.ui.editor.setCaretLineBackgroundColor(QColor(self.caretLineColor))
        self.ui.editor.setCaretLineVisible(self.caretLine)
        self.ui.editor.setEolVisibility(self.eolVisible)
        if self.spaceVisible:
            self.ui.editor.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsVisible)
        else:
            self.ui.editor.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsInvisible)
        # if self.wrapWord:
        #     self.ui.editor.setWrapMode(QsciScintilla.WrapWord)
        # else:
        #     self.ui.editor.setWrapMode(QsciScintilla.WrapNone)
        if self.marginArea:
            self.ui.editor.setMarginType(1, QsciScintilla.MarginType.NumberMargin)
            self.ui.editor.setMarginLineNumbers(1, True)
            self.ui.editor.setMarginWidth(1, 80)
        self.ui.editor.setMarginsForegroundColor(QColor(self.marginColor))
        self.ui.editor.setMarginsFont(QFont(self.marginFontFamily, self.marginSizeTxt))

        self.lexer = GcodeLexer()
        self.ui.fileTypeCombo.setCurrentIndex(1 if self.defaultFileType == 1 else 0)
        self.ui.editor.setFont(
            QFont(
                self.fontFamily,
                self.sizeTxt,
                weight=self.fontWeight,
                italic=self.fontItalic,
            )
        )
        self.changeFileType(self.ui.fileTypeCombo.currentIndex())
        self.applyUiTheme()

        # Export / Block Numbers opt
        stored_export_mode = self.settings.value("EXPORT_OPT/MODE", None)
        if stored_export_mode is None:
            legacy_mode = self.settings.value("EXPORT_OPT/LANGUAGE", 0, type=int)
            if legacy_mode == 5:
                self.exportMode = TURN_FULL_PROGRAM_MODE
                self.exportArcMode = 0
            elif legacy_mode == 6:
                self.exportMode = MILL_FULL_PROGRAM_MODE
                self.exportArcMode = 0
            elif legacy_mode == 4:
                self.exportMode = EXPANDED_EXECUTION_MODE
                self.exportArcMode = 0
            else:
                self.exportMode = EXPANDED_EXECUTION_MODE
                self.exportArcMode = legacy_mode if legacy_mode in range(4) else 0
        else:
            mode = self.settings.value("EXPORT_OPT/MODE", EXPANDED_EXECUTION_MODE, type=int)
            if self.settings.value("EXPORT_OPT/MODE_SCHEMA", 1, type=int) < 2:
                mode = DXF_MODE if mode == 4 else EXPANDED_EXECUTION_MODE if mode == 3 else mode
            self.exportMode = mode if mode in range(DXF_MODE + 1) else EXPANDED_EXECUTION_MODE
            arc_mode = self.settings.value("EXPORT_OPT/ARC_MODE", 0, type=int)
            self.exportArcMode = arc_mode if arc_mode in range(4) else 0
        self._load_setting_group("EXPORT_OPT", _EXPORT_SETTINGS)
        self._load_comment_style()

        self._restore_window_geometry()

    def _restore_window_geometry(self):
        """Restore the saved position within the currently available screens."""
        is_maximized = self.settings.value("GEOMETRY/APP_MAXIMIZED", False, type=bool)
        heightApp = self.settings.value("GEOMETRY/APP_HEIGHT", 500, type=int)
        widthApp = self.settings.value("GEOMETRY/APP_WIDTH", 730, type=int)
        x = self.settings.value("GEOMETRY/START_POS_X", 475, type=int)
        y = self.settings.value("GEOMETRY/START_POS_Y", 224, type=int)
        if is_maximized:
            self.setWindowState(Qt.WindowState.WindowMaximized)
        self.resize(widthApp, heightApp)
        app = QApplication.instance()
        screens = app.screens() if app is not None else []
        geometries = [screen.availableGeometry() for screen in screens]
        primary = app.primaryScreen().availableGeometry() if app is not None and app.primaryScreen() else None
        x, y = _visible_window_position(x, y, self.width(), self.height(), geometries, primary)
        self.move(x, y)

    def _load_setting_group(self, group, specs):
        for spec in specs:
            key = f"{group}/{spec.key}"
            value = (
                self.settings.value(key, spec.default)
                if spec.validator
                else self.settings.value(key, spec.default, type=spec.value_type)
            )
            if spec.validator is not None:
                value = spec.validator(value)
            setattr(self, spec.attribute, value)

    def _save_setting_group(self, specs):
        for spec in specs:
            self.settings.setValue(spec.key, getattr(self, spec.attribute))

    def _load_comment_style(self):
        stored = self.settings.value("CNC/COMMENT_STYLE", None)
        if stored is None:
            legacy_start = self.settings.value("EXPORT_OPT/COMMENT_START", "(")
            stored = "semicolon" if legacy_start == ";" else DEFAULT_COMMENT_STYLE
        self.commentStyle = normalize_comment_style(stored)
        self.co, self.ci = comment_markers(self.commentStyle)
        self.lexer.set_comment_style(self.commentStyle)

    def _load_arc_sampling_settings(self):
        preset_ids = {preset[0] for preset in ARC_SAMPLING_PRESETS}
        self.arcSamplingPreset = str(self.settings.value("CNC/ARC_SAMPLING_PRESET", ARC_SAMPLING_PRESET_DEFAULT))
        if self.arcSamplingPreset not in preset_ids:
            self.arcSamplingPreset = ARC_SAMPLING_PRESET_DEFAULT
        self.maximumCircularRadius = bounded_number(
            self.settings.value("CNC/MAXIMUM_CIRCULAR_RADIUS", MAXIMUM_CIRCULAR_RADIUS_DEFAULT),
            MAXIMUM_CIRCULAR_RADIUS_DEFAULT,
            MAXIMUM_CIRCULAR_RADIUS_MIN,
            MAXIMUM_CIRCULAR_RADIUS_MAX,
            name="CNC/MAXIMUM_CIRCULAR_RADIUS",
        )
        self.minimumCircularRadius = bounded_number(
            self.settings.value("CNC/MINIMUM_CIRCULAR_RADIUS", MINIMUM_CIRCULAR_RADIUS_DEFAULT),
            MINIMUM_CIRCULAR_RADIUS_DEFAULT,
            MINIMUM_CIRCULAR_RADIUS_MIN,
            MINIMUM_CIRCULAR_RADIUS_MAX,
            name="CNC/MINIMUM_CIRCULAR_RADIUS",
        )
        self.minimumChordLength = bounded_number(
            self.settings.value("CNC/MINIMUM_CHORD_LENGTH", MINIMUM_CHORD_LENGTH_DEFAULT),
            MINIMUM_CHORD_LENGTH_DEFAULT,
            MINIMUM_CHORD_LENGTH_MIN,
            MINIMUM_CHORD_LENGTH_MAX,
            name="CNC/MINIMUM_CHORD_LENGTH",
        )
        self.minimumCircularRadius = min(self.minimumCircularRadius, self.maximumCircularRadius)

    def restoreToolbarState(self):
        """Restore the last movable-toolbar arrangement when available."""
        state = self.settings.value("GEOMETRY/TOOLBAR_STATE")
        if state is not None and not self.restoreState(state, 1):
            self.resetToolbarsToDefault()

    def _load_plot_colors(self):
        """Load standard plot colors, moving untouched defaults onto the active theme."""
        self.plotLineColor = theme.themed_plot_value(
            self.settings.value("PLOT/LINE_COLOR", "#0000ff"), "linear", self.uiTheme
        )
        self.plotRapidColor = theme.themed_plot_value(
            self.settings.value("PLOT/RAPID_COLOR", "#d02020"), "rapid", self.uiTheme
        )
        self.plotArcColor = theme.themed_plot_value(
            self.settings.value("PLOT/ARC_COLOR", "#008000"), "arc", self.uiTheme
        )
        self.plotCurrentColor = theme.themed_plot_value(
            self.settings.value("PLOT/CURRENT_COLOR", "#00b7ff"), "current", self.uiTheme
        )
        self.plotToolColor = theme.themed_plot_value(
            self.settings.value("PLOT/TOOL_COLOR", "#e3aa37"), "tool", self.uiTheme
        )
        self.plotBackground = theme.themed_plot_value(
            self.settings.value("PLOT/BACKGROUND", "#ffffff"), "background", self.uiTheme
        )
        self.stlColor = theme.themed_plot_value(self.settings.value("PLOT/STL_COLOR", "#b0b0b0"), "stl", self.uiTheme)
        grid_color = self.settings.value("PLOT/GRID_COLOR", "#808080")
        if QColor(grid_color).name() == "#d3d3d3":
            # Migrate the old low-contrast default, which disappears in the
            # darker half of the optional background gradient.
            grid_color = "#808080"
        self.plotGridColor = theme.themed_plot_value(grid_color, "grid", self.uiTheme)

    def applyUiTheme(self):
        """Apply the application palette and editor colors for the active theme."""
        self.uiTheme = theme.normalize_theme(self.uiTheme)
        app = QApplication.instance()
        if app is not None:
            theme.apply_application_theme(app, self.uiTheme)
        if self.uiTheme == "dark":
            hover, pressed, checked, border = "#454952", "#343940", "#3b4655", "#727a86"
        else:
            hover, pressed, checked, border = "#e7eef7", "#d0dfef", "#d7e7f8", "#7d9fc6"
        toolbar_button_style = (
            "QToolButton { border: 1px solid transparent; border-radius: 3px; padding: 3px; }"
            "QToolButton:hover {"
            f" background-color: {hover}; border-color: {border};"
            "}"
            "QToolButton:pressed {"
            f" background-color: {pressed}; border-color: {border};"
            "}"
            "QToolButton:checked {"
            f" background-color: {checked}; border-color: {border};"
            "}"
            "QToolButton:checked:hover {"
            f" background-color: {hover}; border-color: {border};"
            "}"
        )
        for toolbar in self._toolbars():
            toolbar.setStyleSheet(toolbar_button_style)
        help_dialog = getattr(self, "helpDlg", None)
        if help_dialog is not None:
            help_dialog.apply_theme(self.uiTheme)
        stl_panel = getattr(self, "stlObjectsDock", None)
        if stl_panel is not None:
            stl_panel.apply_theme(self.uiTheme)
        theme.apply_editor_theme(self.ui.editor, getattr(self, "lexer", None), self.uiTheme)

    def applyPlotTheme(self):
        """Move untouched standard plot colors onto the active theme and repaint."""
        for key, attribute in theme.PLOT_COLOR_ATTRIBUTES.items():
            current = getattr(self, attribute, None)
            setattr(self, attribute, theme.themed_plot_value(current, key, self.uiTheme))
        self.saveSettings()
        self.refreshStlAppearance()
        self.refreshPlotView()

    def _load_tool_libraries(self):
        self._tool_library_load_error = None
        try:
            self.turningToolLibrary, self.millingToolLibrary = load_tool_libraries()
        except ToolLibraryLoadError as exc:
            self.turningToolLibrary = {}
            self.millingToolLibrary = {}
            self._tool_library_load_error = str(exc)
        self.tools = {}
        self.millingTools = {}
        self.program_tool_inference = {}

    def _load_playback_speed(self):
        stored = self.settings.value("PLOT/PLAYBACK_SPEED", None)
        if stored is None:
            interval = self.settings.value("PLOT/TIMER_SPEED", 100, type=int)
            self.playbackSpeed = playback_speed_level(interval)
        else:
            self.playbackSpeed = max(1, min(5, int(stored)))
        self.speedTimer = playback_interval_ms(self.playbackSpeed)
        self.ui.playbackSpeedSlider.setValue(self.playbackSpeed)

    def setPlaybackSpeed(self, level):
        """Apply the shared playback speed from the toolbar or Options."""
        self.playbackSpeed = max(1, min(5, int(level)))
        self.speedTimer = playback_interval_ms(self.playbackSpeed)
        blocked = self.ui.playbackSpeedSlider.blockSignals(True)
        self.ui.playbackSpeedSlider.setValue(self.playbackSpeed)
        self.ui.playbackSpeedSlider.blockSignals(blocked)
        if self.timer.isActive():
            self.timer.start(self.speedTimer, self)
        self.settings.setValue("PLOT/PLAYBACK_SPEED", self.playbackSpeed)
        self.settings.setValue("PLOT/TIMER_SPEED", self.speedTimer)

    def _load_hotkeys(self):
        self.hotkeyActions = {key: action for key, action, _category in menu_commands(self)}
        self.defaultHotkeys = {key: portable_shortcut(action.shortcut()) for key, action in self.hotkeyActions.items()}
        migration_key = "HOTKEYS/F3_F4_DEFAULTS_MIGRATED"
        migrate_defaults = not self.settings.value(migration_key, False, type=bool)
        shortcuts = {}
        for key, default in self.defaultHotkeys.items():
            legacy_key = LEGACY_KEYS.get(key)
            fallback = self.settings.value(f"HOTKEYS/{legacy_key}", default) if legacy_key else default
            shortcuts[key] = self.settings.value(f"HOTKEYS/{key}", fallback)
            if migrate_defaults and key in ("actionFAQ", "actionGrid") and not str(shortcuts[key]).strip():
                shortcuts[key] = default
                self.settings.setValue(f"HOTKEYS/{key}", default)
        if migrate_defaults:
            self.settings.setValue(migration_key, True)
        self.setHotkeys(shortcuts)
        for key, shortcut in self.hotkeys.items():
            if shortcut != str(shortcuts[key]):
                self.settings.setValue(f"HOTKEYS/{key}", shortcut)

    def setHotkeys(self, shortcuts):
        """Apply menu-command shortcuts and retain their portable text."""
        normalized = {}
        for key, action in self.hotkeyActions.items():
            sequence = QKeySequence(
                str(shortcuts.get(key, self.defaultHotkeys[key])), QKeySequence.SequenceFormat.PortableText
            )
            if is_reserved_shortcut(portable_shortcut(sequence)):
                sequence = QKeySequence()
            normalized[key] = portable_shortcut(sequence)
        owners = {}
        for key, shortcut in normalized.items():
            if not shortcut:
                continue
            previous = owners.get(shortcut)
            if previous is None:
                owners[shortcut] = key
            elif self.defaultHotkeys[key] == shortcut and self.defaultHotkeys[previous] != shortcut:
                normalized[previous] = ""
                owners[shortcut] = key
            else:
                normalized[key] = ""
        self.hotkeys = normalized
        for key, action in self.hotkeyActions.items():
            action.setShortcut(QKeySequence(normalized[key], QKeySequence.SequenceFormat.PortableText))

    def _save_hotkeys(self):
        for key in self.hotkeyActions:
            self.settings.setValue(f"HOTKEYS/{key}", self.hotkeys[key])

    def saveSettings(self):
        """Persist current settings to the ini file."""
        self._save_hotkeys()
        self.settings.beginGroup("PLOT")
        self.settings.setValue("TIMER_SPEED", self.speedTimer)
        self.settings.setValue("PLAYBACK_SPEED", self.playbackSpeed)
        self._save_setting_group(_PLOT_SETTINGS)
        self.settings.setValue("LINE_COLOR", self.plotLineColor)
        self.settings.setValue("RAPID_COLOR", self.plotRapidColor)
        self.settings.setValue("ARC_COLOR", self.plotArcColor)
        self.settings.setValue("CURRENT_COLOR", self.plotCurrentColor)
        self.settings.setValue("TOOL_COLOR", self.plotToolColor)
        self.settings.setValue("BACKGROUND", self.plotBackground)
        self.settings.setValue("STL_COLOR", self.stlColor)
        self.settings.setValue("GRID_COLOR", self.plotGridColor)
        self.settings.endGroup()
        self.settings.beginGroup("STOCK")
        self._save_setting_group(_STOCK_SETTINGS)
        self.settings.setValue("FRONT_Z", self.turnStockFrontZ)
        self.settings.endGroup()
        self.settings.beginGroup("CNC")
        self._save_setting_group(_CNC_SETTINGS)
        for key, value in (
            ("COMMENT_STYLE", self.commentStyle),
            ("ARC_TOLERANCE", self.arcTolerance),
            ("ARC_SAMPLING_PRESET", self.arcSamplingPreset),
            ("MAXIMUM_CIRCULAR_RADIUS", self.maximumCircularRadius),
            ("MINIMUM_CIRCULAR_RADIUS", self.minimumCircularRadius),
            ("MINIMUM_CHORD_LENGTH", self.minimumChordLength),
        ):
            self.settings.setValue(key, value)
        for code in range(54, 60):
            x_offset, y_offset, z_offset = self.wcsOffsets.get(code, (0.0, 0.0, 0.0))
            self.settings.setValue(f"G{code}_X", x_offset)
            self.settings.setValue(f"G{code}_Y", y_offset)
            self.settings.setValue(f"G{code}_Z", z_offset)
        self.settings.endGroup()
        self.settings.beginGroup("EDITOR")
        self._save_setting_group(_EDITOR_SETTINGS)
        self.settings.endGroup()
        self.settings.beginGroup("GENERAL")
        self._save_setting_group(_GENERAL_SETTINGS)
        self.settings.remove("AUTO_UPDATE_MAX_LINES")
        self.settings.endGroup()
        self.settings.beginGroup("EXPORT_OPT")
        self.settings.setValue("MODE", self.exportMode)
        self.settings.setValue("MODE_SCHEMA", 2)
        self.settings.setValue("ARC_MODE", self.exportArcMode)
        self.settings.remove("LANGUAGE")
        self._save_setting_group(_EXPORT_SETTINGS)
        self.settings.remove("COMMENT_START")
        self.settings.remove("COMMENT_END")
        self.settings.endGroup()
        self.settings.beginGroup("GEOMETRY")
        self.settings.setValue("TOOLBAR_STATE", self.saveState(1))
        self.settings.setValue("APP_MAXIMIZED", self.isMaximized())
        if not self.isMaximized():
            self.settings.setValue("APP_HEIGHT", self.size().height())
            self.settings.setValue("APP_WIDTH", self.size().width())
            self.settings.setValue("START_POS_X", self.pos().x())
            self.settings.setValue("START_POS_Y", self.pos().y())
        self.settings.endGroup()
        self.settings.setValue("FILE/RECENT_FILES", self.recentFiles)
        self.settings.setValue("FILE/RECENT_STL_FILES", self.recentStlFiles)
        self.settings.setValue("GENERAL/THEME", self.uiTheme)
        self.settings.setValue("GENERAL/TOOLBAR_ICON_SIZE", self.toolbarIconSize)
