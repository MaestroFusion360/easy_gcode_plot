"""Persistence and editor/plot preference handling for the main window."""

import json

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QVector3D

from app.gcode.exporter import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    PLOT_DATA_MODE,
    TURN_FULL_PROGRAM_MODE,
)
from app.settings import (
    ARC_TOLERANCE_DEFAULT,
    ARC_TOLERANCE_MAX,
    ARC_TOLERANCE_MIN,
    AUTO_UPDATE_SEGMENTS_MAX,
    AUTO_UPDATE_SEGMENTS_MIN,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    LINE_WIDTH_MAX,
    LINE_WIDTH_MIN,
    bounded_number,
    configure_logging,
    get_settings,
)
from app.settings import (
    normalized_milling_tools as _normalized_milling_tools,
)
from app.settings import (
    normalized_recent_files as _normalized_recent_files,
)
from app.settings import (
    normalized_tools as _normalized_tools,
)
from app.ui.lexer import GcodeLexer
from app.ui.main_window_execution import playback_interval_ms, playback_speed_level

EDITOR_FONT_FAMILY_KEY = "FONT_FAMILY"
EDITOR_FONT_SIZE_KEY = "FONT_SIZE"
EDITOR_FONT_WEIGHT_KEY = "FONT_WEIGHT"
EDITOR_FONT_ITALIC_KEY = "FONT_ITALIC"


class MainWindowSettingsMixin:
    """Load and save the existing 1.x main-window preferences."""

    def loadSettings(self):
        """Load application, editor, and plot settings from the ini file."""
        self.curFile = ""
        self.setCurrentFile("")
        self.setAcceptDrops(True)

        # logging.basicConfig(level=logging.DEBUG, filename="main.log")

        self.settings = get_settings()
        recent = self.settings.value("FILE/RECENT_FILES", [])
        if isinstance(recent, str):
            recent = [recent]
        self.recentFiles = _normalized_recent_files(recent)

        # Plot
        self.dist = 100
        self.rapidFeed = 10000
        self.ui.graphicsView.opts["center"] = QVector3D(0, 0, 0)

        stored_playback_speed = self.settings.value("PLOT/PLAYBACK_SPEED", None)
        if stored_playback_speed is None:
            legacy_interval = self.settings.value("PLOT/TIMER_SPEED", 100, type=int)
            self.playbackSpeed = playback_speed_level(legacy_interval)
        else:
            self.playbackSpeed = max(1, min(5, int(stored_playback_speed)))
        self.speedTimer = playback_interval_ms(self.playbackSpeed)
        self.arc_type = self.settings.value("PLOT/ARC_TYPE", 1, type=int)

        if self.arc_type == 2:
            self.ui.actionAbsolute.setChecked(True)
        elif self.arc_type == 3:
            self.ui.actionRadius_value.setChecked(True)
        else:
            self.ui.actionRelative_to_start.setChecked(True)

        self.xPosMach = self.settings.value("PLOT/MACHINE_XPOS", 0, type=float)
        self.yPosMach = self.settings.value("PLOT/MACHINE_YPOS", 0, type=float)
        self.zPosMach = self.settings.value("PLOT/MACHINE_ZPOS", 0, type=float)
        self.homeConfigured = self.settings.value("CNC/HOME_CONFIGURED", True, type=bool)
        self.wcsOffsets = {
            code: (
                self.settings.value(f"CNC/G{code}_X", 0.0, type=float),
                self.settings.value(f"CNC/G{code}_Y", 0.0, type=float),
                self.settings.value(f"CNC/G{code}_Z", 0.0, type=float),
            )
            for code in range(54, 60)
        }
        self.tools = _normalized_tools(self.settings.value("CNC/TOOLS_JSON", "{}"))
        self.millingTools = _normalized_milling_tools(self.settings.value("CNC/MILLING_TOOLS_JSON", "{}"))
        self.latheMode = self.settings.value("PLOT/LATHE_MODE", False, type=bool)
        self.ui.actionLatheMode.setChecked(self.latheMode)
        self.showStock = self.settings.value("PLOT/SHOW_STOCK", True, type=bool)
        self.plotLineColor = self.settings.value("PLOT/LINE_COLOR", "#0000ff")
        self.plotRapidColor = self.settings.value("PLOT/RAPID_COLOR", "#d02020")
        self.plotArcColor = self.settings.value("PLOT/ARC_COLOR", "#008000")
        self.plotCurrentColor = self.settings.value("PLOT/CURRENT_COLOR", "#00b7ff")
        self.plotToolColor = self.settings.value("PLOT/TOOL_COLOR", "#4d99ff")
        self.plotLineWidth = bounded_number(
            self.settings.value("PLOT/LINE_WIDTH", 1.5), 1.5, LINE_WIDTH_MIN, LINE_WIDTH_MAX, name="PLOT/LINE_WIDTH"
        )
        self.plotGridStep = self.settings.value("PLOT/GRID_STEP", 0.0, type=float)
        self.plotAxes = self.settings.value("PLOT/AXES", True, type=bool)
        self.plotBackground = self.settings.value("PLOT/BACKGROUND", "#ffffff")
        self.plotBackgroundGradient = self.settings.value("PLOT/BACKGROUND_GRADIENT", False, type=bool)
        self.stlColor = self.settings.value("PLOT/STL_COLOR", "#b0b0b0")
        self.stlWireframe = self.settings.value("PLOT/STL_WIREFRAME", False, type=bool)
        self.stockConfigured = self.settings.value("STOCK/CONFIGURED", False, type=bool)
        self.stockEnabled = self.settings.value("STOCK/ENABLED", False, type=bool)
        self.turnStockDiameter = self.settings.value("STOCK/DIAMETER", 50.0, type=float)
        self.turnStockInnerDiameter = self.settings.value("STOCK/INNER_DIAMETER", 0.0, type=float)
        self.turnStockLength = self.settings.value("STOCK/LENGTH", 100.0, type=float)
        self.turnStockResolution = self.settings.value("STOCK/RESOLUTION", 0.5, type=float)
        self.turnStockFrontAllowance = self.settings.value("STOCK/FRONT_ALLOWANCE", 2.0, type=float)
        self.plotGrid = self.settings.value("PLOT/GRID", False, type=bool)
        self.plotGridColor = self.settings.value("PLOT/GRID_COLOR", "#808080")
        if QColor(self.plotGridColor).name() == "#d3d3d3":
            # Migrate the old low-contrast default, which disappears in the
            # darker half of the optional background gradient.
            self.plotGridColor = "#808080"
        self.plotGridSize = self.settings.value("PLOT/GRID_SIZE", 1000, type=int)
        self.plotGridSpacing = self.settings.value("PLOT/GRID_SPACING", 50, type=int)
        self.ui.actionGrid.setChecked(self.plotGrid)
        self.fileEncoding = self.settings.value("EDITOR/ENCODING", "utf-8")
        self.defaultFileType = self.settings.value("EDITOR/DEFAULT_FILE_TYPE", 0, type=int)
        self.defaultUnits = self.settings.value("CNC/DEFAULT_UNITS", "mm")
        self.correctionEnabled = self.settings.value("CNC/CORRECTION_ENABLED", True, type=bool)
        self.arcTolerance = bounded_number(
            self.settings.value("CNC/ARC_TOLERANCE", ARC_TOLERANCE_DEFAULT),
            ARC_TOLERANCE_DEFAULT,
            ARC_TOLERANCE_MIN,
            ARC_TOLERANCE_MAX,
            name="CNC/ARC_TOLERANCE",
        )
        self.uiLanguage = self.settings.value("GENERAL/LANGUAGE", "en")
        self.loggingEnabled = self.settings.value("GENERAL/LOGGING", False, type=bool)
        self.autoUpdateEnabled = self.settings.value("GENERAL/AUTO_UPDATE", True, type=bool)
        self.autoUpdateMaxSegments = int(
            bounded_number(
                self.settings.value("GENERAL/AUTO_UPDATE_MAX_SEGMENTS", 20000),
                20000,
                AUTO_UPDATE_SEGMENTS_MIN,
                AUTO_UPDATE_SEGMENTS_MAX,
                name="GENERAL/AUTO_UPDATE_MAX_SEGMENTS",
            )
        )
        configure_logging(self.loggingEnabled)

        # Editor
        self.ui.editor.setUtf8(True)
        self.ui.editor.setTabWidth(4)
        self.ui.editor.setEolMode(QsciScintilla.EolMode.EolWindows)
        self.ui.editor.setIndentationsUseTabs(False)
        self.ui.editor.setIndentationGuides(True)
        self.ui.editor.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

        self.caretLineColor = self.settings.value("EDITOR/CARETLINE_COLOR", "#e8e8ff")
        self.caretLine = self.settings.value("EDITOR/CARETLINE_VISIBLE", True, type=bool)
        self.eolVisible = self.settings.value("EDITOR/EOL_VISIBLE", False, type=bool)
        self.spaceVisible = self.settings.value("EDITOR/WHITESPACE_VISIBLE", False, type=bool)
        # self.wrapWord = self.settings.value("EDITOR/WRAP_WORD", True, type=bool)
        self.marginArea = self.settings.value("EDITOR/MARGIN_AREA", True, type=bool)
        self.marginColor = self.settings.value("EDITOR/MARGIN_COLOR", "#808080")
        self.marginFontFamily = self.settings.value("EDITOR/MARGIN_FONT_FAMILY", "Courier New")
        self.marginSizeTxt = self.settings.value("EDITOR/MARGIN_FONT_SIZE", 11, type=int)
        self.fontFamily = self.settings.value(f"EDITOR/{EDITOR_FONT_FAMILY_KEY}", "Courier New")
        self.sizeTxt = int(
            bounded_number(
                self.settings.value(f"EDITOR/{EDITOR_FONT_SIZE_KEY}", 12),
                12,
                FONT_SIZE_MIN,
                FONT_SIZE_MAX,
                name="EDITOR/FONT_SIZE",
            )
        )
        self.fontWeight = self.settings.value(f"EDITOR/{EDITOR_FONT_WEIGHT_KEY}", 500, type=int)
        self.fontItalic = self.settings.value(f"EDITOR/{EDITOR_FONT_ITALIC_KEY}", False, type=bool)

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
                self.exportMode = PLOT_DATA_MODE
                self.exportArcMode = 0
            else:
                self.exportMode = EXPANDED_EXECUTION_MODE
                self.exportArcMode = legacy_mode if legacy_mode in range(4) else 0
        else:
            mode = self.settings.value("EXPORT_OPT/MODE", EXPANDED_EXECUTION_MODE, type=int)
            self.exportMode = mode if mode in range(DXF_MODE + 1) else EXPANDED_EXECUTION_MODE
            arc_mode = self.settings.value("EXPORT_OPT/ARC_MODE", 0, type=int)
            self.exportArcMode = arc_mode if arc_mode in range(4) else 0
        self.forceAdr = self.settings.value("EXPORT_OPT/FORCE_ADDRESS", False, type=bool)
        self.incrMode = self.settings.value("EXPORT_OPT/INCREMENTAL_MODE", False, type=bool)
        self.startPgmExp = self.settings.value("EXPORT_OPT/START_PROGRAM", "O0001")
        self.endPgmExp = self.settings.value("EXPORT_OPT/END_PROGRAM", "M30")
        self.safLine = self.settings.value("EXPORT_OPT/SAFETY_LINE", False, type=bool)
        self.seqNum = self.settings.value("EXPORT_OPT/SEQ_NUM", False, type=bool)
        self.seqNumStart = self.settings.value("EXPORT_OPT/SEQ_NUM_START", 1, type=int)
        self.seqNumIncr = self.settings.value("EXPORT_OPT/SEQ_NUM_INCR", 1, type=int)
        self.seqNumSpacing = self.settings.value("EXPORT_OPT/SEQ_NUM_SPACING", False, type=bool)
        self.delim = self.settings.value("EXPORT_OPT/DELIMITER", False, type=bool)
        self.leadingZero = self.settings.value("EXPORT_OPT/LEADING_ZERO", False, type=bool)
        self.co = self.settings.value("EXPORT_OPT/COMMENT_START", "(")
        self.ci = self.settings.value("EXPORT_OPT/COMMENT_END", ")")
        self.er = self.settings.value("EXPORT_OPT/ER_CHAR", "%")

        # Geometry
        is_maximized = self.settings.value("GEOMETRY/APP_MAXIMIZED", False, type=bool)
        heightApp = self.settings.value("GEOMETRY/APP_HEIGHT", 500, type=int)
        widthApp = self.settings.value("GEOMETRY/APP_WIDTH", 730, type=int)
        x = self.settings.value("GEOMETRY/START_POS_X", 475, type=int)
        y = self.settings.value("GEOMETRY/START_POS_Y", 224, type=int)
        if is_maximized:
            self.setWindowState(Qt.WindowState.WindowMaximized)
        self.resize(widthApp, heightApp)
        self.move(x, y)

    def restoreToolbarState(self):
        """Restore the last movable-toolbar arrangement when available."""
        state = self.settings.value("GEOMETRY/TOOLBAR_STATE")
        if state is not None and not self.restoreState(state, 1):
            self.resetToolbarsToDefault()

    def saveSettings(self):
        """Persist current settings to the ini file."""
        self.settings.beginGroup("PLOT")
        self.settings.setValue("TIMER_SPEED", self.speedTimer)
        self.settings.setValue("PLAYBACK_SPEED", self.playbackSpeed)
        self.settings.setValue("ARC_TYPE", self.arc_type)
        self.settings.setValue("MACHINE_XPOS", self.xPosMach)
        self.settings.setValue("MACHINE_YPOS", self.yPosMach)
        self.settings.setValue("MACHINE_ZPOS", self.zPosMach)
        self.settings.setValue("LATHE_MODE", self.latheMode)
        self.settings.setValue("SHOW_STOCK", self.showStock)
        self.settings.setValue("LINE_COLOR", self.plotLineColor)
        self.settings.setValue("RAPID_COLOR", self.plotRapidColor)
        self.settings.setValue("ARC_COLOR", self.plotArcColor)
        self.settings.setValue("CURRENT_COLOR", self.plotCurrentColor)
        self.settings.setValue("TOOL_COLOR", self.plotToolColor)
        self.settings.setValue("LINE_WIDTH", self.plotLineWidth)
        self.settings.setValue("GRID_STEP", self.plotGridStep)
        self.settings.setValue("AXES", self.plotAxes)
        self.settings.setValue("BACKGROUND", self.plotBackground)
        self.settings.setValue("BACKGROUND_GRADIENT", self.plotBackgroundGradient)
        self.settings.setValue("STL_COLOR", self.stlColor)
        self.settings.setValue("STL_WIREFRAME", self.stlWireframe)
        self.settings.setValue("GRID", self.plotGrid)
        self.settings.setValue("GRID_COLOR", self.plotGridColor)
        self.settings.setValue("GRID_SIZE", self.plotGridSize)
        self.settings.setValue("GRID_SPACING", self.plotGridSpacing)
        self.settings.endGroup()
        self.settings.beginGroup("STOCK")
        self.settings.setValue("CONFIGURED", self.stockConfigured)
        self.settings.setValue("ENABLED", self.stockEnabled)
        self.settings.setValue("DIAMETER", self.turnStockDiameter)
        self.settings.setValue("INNER_DIAMETER", self.turnStockInnerDiameter)
        self.settings.setValue("LENGTH", self.turnStockLength)
        self.settings.setValue("RESOLUTION", self.turnStockResolution)
        self.settings.setValue("FRONT_ALLOWANCE", self.turnStockFrontAllowance)
        self.settings.endGroup()
        self.settings.beginGroup("CNC")
        self.settings.setValue("HOME_CONFIGURED", self.homeConfigured)
        self.settings.setValue("DEFAULT_UNITS", self.defaultUnits)
        self.settings.setValue("CORRECTION_ENABLED", self.correctionEnabled)
        self.settings.setValue("ARC_TOLERANCE", self.arcTolerance)
        for code in range(54, 60):
            x_offset, y_offset, z_offset = self.wcsOffsets.get(code, (0.0, 0.0, 0.0))
            self.settings.setValue(f"G{code}_X", x_offset)
            self.settings.setValue(f"G{code}_Y", y_offset)
            self.settings.setValue(f"G{code}_Z", z_offset)
        self.settings.setValue("TOOLS_JSON", json.dumps(self.tools, ensure_ascii=False, sort_keys=True))
        self.settings.setValue(
            "MILLING_TOOLS_JSON",
            json.dumps(self.millingTools, ensure_ascii=False, sort_keys=True),
        )
        self.settings.endGroup()
        self.settings.beginGroup("EDITOR")
        self.settings.setValue("CARETLINE_COLOR", self.caretLineColor)
        self.settings.setValue("ENCODING", self.fileEncoding)
        self.settings.setValue("DEFAULT_FILE_TYPE", self.defaultFileType)
        self.settings.setValue("CARETLINE_VISIBLE", self.caretLine)
        self.settings.setValue("EOL_VISIBLE", self.eolVisible)
        self.settings.setValue("WHITESPACE_VISIBLE", self.spaceVisible)
        # self.settings.setValue("WRAP_WORD", self.wrapWord)
        self.settings.setValue("MARGIN_AREA", self.marginArea)
        self.settings.setValue("MARGIN_COLOR", self.marginColor)
        self.settings.setValue("MARGIN_FONT_FAMILY", self.marginFontFamily)
        self.settings.setValue("MARGIN_FONT_SIZE", self.marginSizeTxt)
        self.settings.setValue(EDITOR_FONT_FAMILY_KEY, self.fontFamily)
        self.settings.setValue(EDITOR_FONT_SIZE_KEY, self.sizeTxt)
        self.settings.setValue(EDITOR_FONT_WEIGHT_KEY, self.fontWeight)
        self.settings.setValue(EDITOR_FONT_ITALIC_KEY, self.fontItalic)
        self.settings.endGroup()
        self.settings.beginGroup("GENERAL")
        self.settings.setValue("AUTO_UPDATE", self.autoUpdateEnabled)
        self.settings.setValue("AUTO_UPDATE_MAX_SEGMENTS", self.autoUpdateMaxSegments)
        self.settings.remove("AUTO_UPDATE_MAX_LINES")
        self.settings.endGroup()
        self.settings.beginGroup("EXPORT_OPT")
        self.settings.setValue("MODE", self.exportMode)
        self.settings.setValue("ARC_MODE", self.exportArcMode)
        self.settings.remove("LANGUAGE")
        self.settings.setValue("FORCE_ADDRESS", self.forceAdr)
        self.settings.setValue("INCREMENTAL_MODE", self.incrMode)
        self.settings.setValue("START_PROGRAM", self.startPgmExp)
        self.settings.setValue("END_PROGRAM", self.endPgmExp)
        self.settings.setValue("SAFETY_LINE", self.safLine)
        self.settings.setValue("SEQ_NUM", self.seqNum)
        self.settings.setValue("SEQ_NUM_START", self.seqNumStart)
        self.settings.setValue("SEQ_NUM_INCR", self.seqNumIncr)
        self.settings.setValue("SEQ_NUM_SPACING", self.seqNumSpacing)
        self.settings.setValue("DELIMITER", self.delim)
        self.settings.setValue("LEADING_ZERO", self.leadingZero)
        self.settings.setValue("COMMENT_START", self.co)
        self.settings.setValue("COMMENT_END", self.ci)
        self.settings.setValue("ER_CHAR", self.er)
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
        self.settings.setValue("GENERAL/LANGUAGE", self.uiLanguage)
        self.settings.setValue("GENERAL/LOGGING", self.loggingEnabled)
