"""Persistence and editor/plot preference handling for the main window."""

import json

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QVector3D

from app.settings import (
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

        self.speedTimer = self.settings.value("PLOT/TIMER_SPEED", 100, type=int)
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
        self.plotLineColor = self.settings.value("PLOT/LINE_COLOR", "#0000ff")
        self.plotBackground = self.settings.value("PLOT/BACKGROUND", "#ffffff")
        self.plotGrid = self.settings.value("PLOT/GRID", False, type=bool)
        self.plotGridColor = self.settings.value("PLOT/GRID_COLOR", "#d3d3d3")
        self.plotGridSize = self.settings.value("PLOT/GRID_SIZE", 1000, type=int)
        self.plotGridSpacing = self.settings.value("PLOT/GRID_SPACING", 50, type=int)
        self.ui.actionGrid.setChecked(self.plotGrid)

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
        self.sizeTxt = self.settings.value(f"EDITOR/{EDITOR_FONT_SIZE_KEY}", 12, type=int)
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
        self.ui.editor.setFont(
            QFont(
                self.fontFamily,
                self.sizeTxt,
                weight=self.fontWeight,
                italic=self.fontItalic,
            )
        )

        # Export / Block Numbers opt
        self.lang = self.settings.value("EXPORT_OPT/LANGUAGE", 0, type=int)
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

    def saveSettings(self):
        """Persist current settings to the ini file."""
        self.settings.beginGroup("PLOT")
        self.settings.setValue("TIMER_SPEED", self.speedTimer)
        self.settings.setValue("ARC_TYPE", self.arc_type)
        self.settings.setValue("MACHINE_XPOS", self.xPosMach)
        self.settings.setValue("MACHINE_YPOS", self.yPosMach)
        self.settings.setValue("MACHINE_ZPOS", self.zPosMach)
        self.settings.setValue("LATHE_MODE", self.latheMode)
        self.settings.setValue("LINE_COLOR", self.plotLineColor)
        self.settings.setValue("BACKGROUND", self.plotBackground)
        self.settings.setValue("GRID", self.plotGrid)
        self.settings.setValue("GRID_COLOR", self.plotGridColor)
        self.settings.setValue("GRID_SIZE", self.plotGridSize)
        self.settings.setValue("GRID_SPACING", self.plotGridSpacing)
        self.settings.endGroup()
        self.settings.beginGroup("CNC")
        self.settings.setValue("HOME_CONFIGURED", self.homeConfigured)
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
        self.settings.beginGroup("EXPORT_OPT")
        self.settings.setValue("LANGUAGE", self.lang)
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
        self.settings.setValue("APP_MAXIMIZED", self.isMaximized())
        if not self.isMaximized():
            self.settings.setValue("APP_HEIGHT", self.size().height())
            self.settings.setValue("APP_WIDTH", self.size().width())
            self.settings.setValue("START_POS_X", self.pos().x())
            self.settings.setValue("START_POS_Y", self.pos().y())
        self.settings.endGroup()
        self.settings.setValue("FILE/RECENT_FILES", self.recentFiles)
