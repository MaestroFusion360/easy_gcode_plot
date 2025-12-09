"""Easy G-code Plot main module."""

# pylint: disable=import-error,no-name-in-module

# region IMPORTS

import re
import sys
import time
from math import atan2, cos, floor, pi, sin, sqrt

from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QDialog,
    QMainWindow,
    QMessageBox,
    QLabel,
    QProgressBar,
)
from PyQt5.QtGui import QColor, QFont, QIcon, QQuaternion, QVector3D
from PyQt5.QtCore import (
    Qt,
    QBasicTimer,
    QFile,
    QFileInfo,
    QSettings,
    QSize,
    QTextStream,
    QUrl,
)
from PyQt5.Qsci import QsciLexerCustom, QsciScintilla
from pyqtgraph.opengl import GLGridItem, GLLinePlotItem, GLScatterPlotItem

from main_ui import Ui_MainWindow
from find_replace import Ui_Find
from export import Ui_ExportOptDlg
from block_num import Ui_BlockNumberDlg
from export_logic import export_pgm
import files_res

# endregion


# region BlockNum


class BlockNum(QDialog):
    """Dialog for configuring block numbering parameters."""

    def __init__(self, parent=None):
        """Initialize the dialog with parent defaults and hook signals."""
        super().__init__(parent)
        self.ui = Ui_BlockNumberDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

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


# endregion


# region Export


class Export(QDialog):
    """Dialog for configuring export options before saving G-code."""

    def __init__(self, parent=None):
        """Set up export options dialog and load persisted settings."""
        super().__init__(parent)
        self.ui = Ui_ExportOptDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

        self.loadSettings()
        self.connectActions()

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
        self.parent().lang = self.ui.langCmbBox.currentIndex()
        if self.ui.langCmbBox.currentIndex() == 4:
            self.ui.forceCmbBox.setEnabled(False)
            self.ui.incrCmbBox.setEnabled(False)
        else:
            self.ui.forceCmbBox.setEnabled(True)
            self.ui.incrCmbBox.setEnabled(True)

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


# endregion


# region Find


class Find(QDialog):
    """Dialog providing find/replace utilities for the editor."""

    def __init__(self, parent=None):
        """Configure dialog and connect buttons to parent handlers."""
        super().__init__(parent)
        self.ui = Ui_Find()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
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


# endregion


# region GcodeLexer


class GcodeLexer(QsciLexerCustom):
    """Custom QScintilla lexer for highlighting G-code."""

    def __init__(self, parent=None):
        """Initialize lexer styles and colors."""
        super().__init__(parent)

        self.stylesLexer = {
            0: "Default",
            1: "Rapid",
            2: "Linear",
            3: "Circular",
        }

        for key, value in self.stylesLexer.items():
            setattr(self, value, key)

        self.initColors()

    def initColors(self):
        """Assign colors for each move type style."""
        self.setColor(QColor("#000000"), self.Default)
        self.setColor(QColor("#ff0000"), self.Rapid)
        self.setColor(QColor("#2ecc71"), self.Linear)
        self.setColor(QColor("#0000ff"), self.Circular)

    def language(self):
        """Declare lexer language name."""
        return "G-Code"

    def description(self, style):
        """Provide a brief description for the given style id."""
        if style < len(self.stylesLexer):
            description = "Custom lexer for the G-Code"
        else:
            description = ""
        return description

    def styleText(self, start, end):
        """Apply syntax highlighting between given character positions."""
        editor = self.editor()
        if editor is None:
            return

        source = ""
        if end > editor.length():
            end = editor.length()
        if end > start:
            source = str(editor.text())[start:end]
        if not source:
            return

        # rapid = 0, linear = 1, circular = 2
        prev_move = 0
        lst = source.splitlines(True)

        self.startStyling(start)

        if start != 0:
            previous_style = editor.SendScintilla(editor.SCI_GETSTYLEAT, start - 1)
            if previous_style == self.Rapid:
                prev_move = 0
            elif previous_style == self.Linear:
                prev_move = 1
            elif previous_style == self.Circular:
                prev_move = 2
            else:
                source1 = str(editor.text())[0 : start - 1]
                lst1 = source1.splitlines(True)
                i = 0
                while i < len(lst1):
                    line = lst1[i]
                    blockskip = "".join(re.findall(r"^\/.*", line))
                    if blockskip:
                        line = line.replace(blockskip, "")
                    comment = "".join(re.findall(r"\(.*?\)", line))
                    if comment:
                        line = line.replace(comment, "")
                    circular = re.findall(r"[G]0?[2-3][\D]", line)
                    linear = re.findall(r"[G]0?[1][\D]", line)
                    rapid = re.findall(r"[G]0?[0][\D]", line)
                    if rapid:
                        prev_move = 0
                    elif linear:
                        prev_move = 1
                    elif circular:
                        prev_move = 2

                    i += 1

        i = 0
        while i < len(lst):
            line = lst[i]
            blockskip = "".join(re.findall(r"^\/.*", line))
            if blockskip:
                line = line.replace(blockskip, "")
            comment = "".join(re.findall(r"\(.*?\)", line))
            if comment:
                line = line.replace(comment, "")
            lineNum = "".join(re.findall(r"^[N]\d+[\s]+", line))
            if comment:
                line = line.replace(lineNum, "")

            axis = re.findall(
                r"[XYZIJKR]{1}(?:[+-]?[\d\.]+|\#\<.*\>|\[.*\]|\#\d+)", line
            )
            circular = re.findall(r"[G]0?[2-3][\D]", line)
            linear = re.findall(r"[G]0?[1][\D]", line)
            rapid = re.findall(r"[G]0?[0][\D]", line)

            if rapid:
                prev_move = 0
                self.setStyling(len(lst[i]), self.Rapid)
            elif linear:
                prev_move = 1
                self.setStyling(len(lst[i]), self.Linear)
            elif circular:
                prev_move = 2
                self.setStyling(len(lst[i]), self.Circular)
            elif axis:
                if prev_move == 0:
                    self.setStyling(len(lst[i]), self.Rapid)
                elif prev_move == 1:
                    self.setStyling(len(lst[i]), self.Linear)
                elif prev_move == 2:
                    self.setStyling(len(lst[i]), self.Circular)
                # else:
                #     self.setStyling(len(lst[i]), self.Default)
            else:
                self.setStyling(len(lst[i]), self.Default)

            i += 1


# endregion


# region MainWindow


class MainWindow(QMainWindow):
    """Main application window for editing, validating, plotting, and exporting G-code."""

    def __init__(self):
        """Initialize UI, load persisted preferences, and prepare plotting state."""
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        icon = QIcon()
        icon.addFile(":/resource/icons/logo.png", QSize(), QIcon.Normal, QIcon.Off)
        self.setWindowIcon(icon)

        self.loadSettings()
        self.connectActions()
        self.createLabelStatBar()
        self.clearPlot()
        self.changeLathe()

    def loadSettings(self):
        """Load application, editor, and plot settings from the ini file."""
        self.curFile = ""
        self.setCurrentFile("")
        self.setAcceptDrops(True)

        # logging.basicConfig(level=logging.DEBUG, filename="main.log")

        self.settings = QSettings("config.ini", QSettings.IniFormat)

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
        self.ui.editor.setEolMode(QsciScintilla.EolWindows)
        self.ui.editor.setIndentationsUseTabs(False)
        self.ui.editor.setIndentationGuides(True)
        self.ui.editor.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

        self.caretLineColor = self.settings.value("EDITOR/CARETLINE_COLOR", "#e8e8ff")
        self.caretLine = self.settings.value(
            "EDITOR/CARETLINE_VISIBLE", True, type=bool
        )
        self.eolVisible = self.settings.value("EDITOR/EOL_VISIBLE", False, type=bool)
        self.spaceVisible = self.settings.value(
            "EDITOR/WHITESPACE_VISIBLE", False, type=bool
        )
        # self.wrapWord = self.settings.value("EDITOR/WRAP_WORD", True, type=bool)
        self.marginArea = self.settings.value("EDITOR/MARGIN_AREA", True, type=bool)
        self.marginColor = self.settings.value("EDITOR/MARGIN_COLOR", "#808080")
        self.marginFontFamily = self.settings.value(
            "EDITOR/MARGIN_FONT_FAMILY", "Courier New"
        )
        self.marginSizeTxt = self.settings.value(
            "EDITOR/MARGIN_FONT_SIZE", 11, type=int
        )
        self.fontFamily = self.settings.value("EDITOR/TEXT_FONT_FAMILY", "Courier New")
        self.sizeTxt = self.settings.value("EDITOR/TEXT_FONT_SIZE", 12, type=int)
        self.fontWeight = self.settings.value("EDITOR/TEXT_FONT_WEIGHT", 500, type=int)
        self.fontItalic = self.settings.value(
            "EDITOR/TEXT_FONT_ITALIC", False, type=bool
        )

        self.ui.editor.setCaretLineBackgroundColor(QColor(self.caretLineColor))
        self.ui.editor.setCaretLineVisible(self.caretLine)
        self.ui.editor.setEolVisibility(self.eolVisible)
        self.ui.editor.setWhitespaceVisibility(self.spaceVisible)
        # if self.wrapWord:
        #     self.ui.editor.setWrapMode(QsciScintilla.WrapWord)
        # else:
        #     self.ui.editor.setWrapMode(QsciScintilla.WrapNone)
        if self.marginArea:
            self.ui.editor.setMarginType(1, QsciScintilla.NumberMargin)
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
        self.forceAdr = self.settings.value(
            "EXPORT_OPT/FORCE_ADDRESS", False, type=bool
        )
        self.incrMode = self.settings.value(
            "EXPORT_OPT/INCREMENTAL_MODE", False, type=bool
        )
        self.startPgmExp = self.settings.value("EXPORT_OPT/START_PROGRAM", "O0001")
        self.endPgmExp = self.settings.value("EXPORT_OPT/END_PROGRAM", "M30")
        self.safLine = self.settings.value("EXPORT_OPT/SAFETY_LINE", False, type=bool)
        self.seqNum = self.settings.value("EXPORT_OPT/SEQ_NUM", False, type=bool)
        self.seqNumStart = self.settings.value("EXPORT_OPT/SEQ_NUM_START", 1, type=int)
        self.seqNumIncr = self.settings.value("EXPORT_OPT/SEQ_NUM_INCR", 1, type=int)
        self.seqNumSpacing = self.settings.value(
            "EXPORT_OPT/SEQ_NUM_SPACING", False, type=bool
        )
        self.delim = self.settings.value("EXPORT_OPT/DELIMITER", False, type=bool)
        self.leadingZero = self.settings.value(
            "EXPORT_OPT/LEADING_ZERO", False, type=bool
        )
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

        self.exportDlg = Export(self)
        self.findDlg = Find(self)
        self.blockNumDlg = BlockNum(self)
        self.timer = QBasicTimer()

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
        self.settings.setValue("FONT_FAMILY", self.fontFamily)
        self.settings.setValue("FONT_SIZE", self.sizeTxt)
        self.settings.setValue("FONT_WEIGHT", self.fontWeight)
        self.settings.setValue("FONT_ITALIC", self.fontItalic)
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

    def updateStatusBar(self):
        """Update status bar with text length and cursor position."""
        text = self.ui.editor.text()
        line, index = self.ui.editor.getCursorPosition()
        self.chrCountLabel.setText("Length: {}".format(len(text.replace("\n", "\r\n"))))
        self.cursorPosLabel.setText(
            "Ln: {}/{}, Col:{}".format(line + 1, self.ui.editor.lines(), index + 1)
        )

    def closeEvent(self, event):
        """Prompt to save and persist settings before closing the window."""
        if self.maybeSave():
            self.saveSettings()
            event.accept()
        else:
            event.ignore()

    def connectActions(self):
        """Connect UI actions, menu items, and widgets to their handlers."""
        self.ui.actionNew.triggered.connect(self.newFile)
        self.ui.actionOpen.triggered.connect(self.openFile)
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSaveAs.triggered.connect(self.saveAs)
        self.ui.actionExportData.triggered.connect(lambda: self.exportDlg.show())
        self.ui.actionExit.triggered.connect(self.close)

        self.ui.actionUndo.triggered.connect(lambda: self.ui.editor.undo())
        self.ui.actionRedo.triggered.connect(lambda: self.ui.editor.redo())
        self.ui.actionCut.triggered.connect(lambda: self.ui.editor.cut())
        self.ui.actionCopy.triggered.connect(lambda: self.ui.editor.copy())
        self.ui.actionPaste.triggered.connect(lambda: self.ui.editor.paste())
        self.ui.actionSelectAll.triggered.connect(lambda: self.ui.editor.selectAll())
        self.ui.actionFindReplace.triggered.connect(self.runFindDlg)
        self.ui.actionCopy.setEnabled(False)
        self.ui.actionCut.setEnabled(False)
        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)
        self.ui.editor.copyAvailable.connect(self.ui.actionCopy.setEnabled)
        self.ui.editor.copyAvailable.connect(self.ui.actionCut.setEnabled)

        self.ui.actionRenumber.triggered.connect(lambda: self.blockNumDlg.show())
        self.ui.actionNumbRemove.triggered.connect(self.numbRemove)
        self.ui.actionRemoveSpaces.triggered.connect(self.removeSpaces)
        self.ui.actionRemoveEmptyLines.triggered.connect(self.removeLines)
        self.ui.actionStatistics.triggered.connect(self.statistics)

        self.ui.actionRefresh.triggered.connect(self.updateData)
        self.ui.actionZoom_In.triggered.connect(self.zoomIn)
        self.ui.actionZoom_Out.triggered.connect(self.zoomOut)
        self.ui.action3D.triggered.connect(self.view3d)
        self.ui.actionTop.triggered.connect(self.viewTop)
        self.ui.actionFront.triggered.connect(self.viewFront)
        self.ui.actionLeft.triggered.connect(self.viewLeft)
        self.ui.actionGrid.toggled.connect(self.gridChecked)

        self.ui.actionRelative_to_start.toggled.connect(self.changeArcType)
        self.ui.actionAbsolute.toggled.connect(self.changeArcType)
        self.ui.actionRadius_value.toggled.connect(self.changeArcType)
        self.ui.actionLatheMode.toggled.connect(self.changeLathe)

        self.ui.actionStep_Backward.triggered.connect(self.backward)
        self.ui.actionPlay.toggled.connect(self.play)
        self.ui.actionStop.triggered.connect(self.stop)
        self.ui.actionStep_Forward.triggered.connect(self.forward)

        self.ui.editor.modificationChanged.connect(self.documentWasModified)
        self.ui.editor.cursorPositionChanged.connect(self.updateStatusBar)
        self.ui.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.editor.customContextMenuRequested.connect(self.editorContextMenu)

        self.ui.graphicsView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.graphicsView.customContextMenuRequested.connect(self.plotContextMenu)

        self.ui.editor.cursorPositionChanged.connect(self.plotCurLine)
        self.ui.horizontalSlider.sliderMoved.connect(self.sliderDrag)
        self.ui.horizontalSlider.valueChanged.connect(self.valueHandler)
        self.ui.actionAbout.triggered.connect(self.about)

        self.ui.langCombo.currentIndexChanged.connect(self.changeLang)

    def changeLang(self, idx):
        """Switch editor lexer and fonts based on language selection."""
        start = time.time()
        self.ui.editor.setLexer(None)
        self.ui.editor.setMarginsForegroundColor(QColor(self.marginColor))
        self.ui.editor.setMarginsFont(QFont(self.marginFontFamily, self.marginSizeTxt))
        if idx == 0:
            self.ui.editor.setFont(
                QFont(
                    self.fontFamily,
                    self.sizeTxt,
                    weight=self.fontWeight,
                    italic=self.fontItalic,
                )
            )
            self.ui.editor.SendScintilla(QsciScintilla.SCI_CLEARDOCUMENTSTYLE)
        else:
            self.lexer.setFont(
                QFont(
                    self.fontFamily,
                    self.sizeTxt,
                    weight=self.fontWeight,
                    italic=self.fontItalic,
                )
            )
            self.ui.editor.setLexer(self.lexer)
        end = time.time()
        print(f"Paint Execution time: {(end-start)*1000:.3f} ms")

    def createLabelStatBar(self):
        """Create status bar widgets for cursor info, text length, and progress."""
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setMaximum(100)
        self.progressBar.setTextVisible(False)
        self.chrCountLabel = QLabel()
        self.chrCountLabel.setMinimumWidth(100)

        self.cursorPosLabel = QLabel()
        self.cursorPosLabel.setMinimumWidth(150)
        self.ui.statusbar.addPermanentWidget(self.chrCountLabel)
        self.ui.statusbar.addPermanentWidget(self.cursorPosLabel)
        self.ui.statusbar.addPermanentWidget(self.progressBar)

        self.updateStatusBar()

    def dragEnterEvent(self, event):
        """Accept drag events that contain file URLs."""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle dropping a file onto the window by loading and parsing it."""
        for url in event.mimeData().urls():
            file = QUrl(url).toLocalFile()
        if self.maybeSave():
            self.loadFile(file)
            self.updateData()

    def zoomIn(self):
        """Zoom in on the 3D plot."""
        dist = self.ui.graphicsView.opts["distance"]
        self.ui.graphicsView.setCameraPosition(distance=dist * 0.9)

    def zoomOut(self):
        """Zoom out on the 3D plot."""
        dist = self.ui.graphicsView.opts["distance"]
        self.ui.graphicsView.setCameraPosition(distance=dist * 1.1)

    def timerEvent(self, event):
        """Advance playback cursor while animating through the program."""
        if self.step >= self.ui.editor.lines():
            self.timer.stop()
            self.step = 0
            self.ui.actionPlay.setChecked(False)
            return
        self.step = self.step + 1
        self.ui.editor.setCursorPosition(self.step - 1, 0)

    def backward(self):
        """Move cursor one line up in the editor, if possible."""
        line = self.ui.editor.getCursorPosition()[0]
        if line > 1:
            self.ui.editor.setCursorPosition(line - 1, 0)
        else:
            self.ui.editor.setCursorPosition(0, 0)

    def forward(self):
        """Move cursor one line down in the editor, if possible."""
        line = self.ui.editor.getCursorPosition()[0]
        if line < self.ui.editor.lines() - 1:
            self.ui.editor.setCursorPosition(line + 1, 0)
        else:
            self.ui.editor.setCursorPosition(self.ui.editor.lines(), 0)

    def play(self):
        """Start or pause playback of toolpath highlighting."""
        if self.ui.actionPlay.isChecked():
            self.timer.start(self.speedTimer, self)
        else:
            self.timer.stop()

    def stop(self):
        """Stop playback and reset the playback step."""
        self.ui.actionPlay.setChecked(False)
        self.timer.stop()
        self.step = 0

    def sliderDrag(self):
        """Jump to the line that corresponds to the slider position."""
        if self.ui.actionPlay.isChecked():
            self.timer.stop()
            self.ui.actionPlay.setChecked(False)
        if len(self.lst_block) > 1:
            num = int(self.lst_block[self.ui.horizontalSlider.value() - 1])
            self.step = num
            self.ui.editor.setCursorPosition(num, 0)

    def gridChecked(self):
        """Toggle plot grid visibility and refresh the view."""
        val = self.ui.horizontalSlider.value()
        if self.ui.actionGrid.isChecked():
            self.plotGrid = True
        else:
            self.plotGrid = False
        self.valueHandler(val)

    def plotContextMenu(self, point):
        """Show context menu for plot view controls."""
        menu = QMenu()
        menu.addAction(self.ui.actionZoom_In)
        menu.addAction(self.ui.actionZoom_Out)
        menu.addSeparator()
        menu.addAction(self.ui.action3D)
        menu.addAction(self.ui.actionTop)
        menu.addAction(self.ui.actionFront)
        menu.addAction(self.ui.actionLeft)
        menu.addSeparator()
        menu.addAction(self.ui.actionGrid)
        menu.exec(self.ui.graphicsView.mapToGlobal(point))

    def editorContextMenu(self, point):
        """Show context menu for editor editing actions."""
        menu = QMenu()
        menu.addAction(self.ui.actionUndo)
        menu.addAction(self.ui.actionRedo)
        menu.addSeparator()
        menu.addAction(self.ui.actionCut)
        menu.addAction(self.ui.actionCopy)
        menu.addAction(self.ui.actionPaste)
        menu.addAction(self.ui.actionSelectAll)
        menu.exec(self.ui.editor.mapToGlobal(point))

    def newFile(self):
        """Clear editor contents and reset state for a new document."""
        if self.maybeSave():
            self.curFile = ""
            self.ui.editor.clear()
            self.setCurrentFile("")
            self.clearPlot()

    def openFile(self):
        """Prompt for a file to open and load its contents."""
        if self.maybeSave():
            fileName, _ = QFileDialog.getOpenFileName(self)
            if fileName:
                start = time.time()
                self.loadFile(fileName)
                end = time.time()
                print(f"Load file time: {(end-start)*1000:.3f} ms")
                # self.updateData()

    def save(self):
        """Save the current file or prompt for a destination if unnamed."""
        if self.curFile:
            return self.saveFile(self.curFile)
        return self.saveAs()

    def saveAs(self):
        """Prompt for a file path and save the document there."""
        fileName, _ = QFileDialog.getSaveFileName(self)
        if fileName:
            return self.saveFile(fileName)
        return False

    def documentWasModified(self):
        """Update window modified state and reset plot when text changes."""
        self.setWindowModified(self.ui.editor.isModified())
        self.ui.actionUndo.setEnabled(self.ui.editor.isUndoAvailable())
        self.ui.actionRedo.setEnabled(self.ui.editor.isRedoAvailable())
        self.clearPlot()

    def maybeSave(self):
        """Ask the user to save if the document has unsaved changes."""
        if self.ui.editor.isModified():
            ret = QMessageBox.warning(
                self,
                "Easy G-code Plot",
                "The document has been modified.\nDo you want to save your changes?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )

            if ret == QMessageBox.Save:
                return self.save()

            if ret == QMessageBox.Cancel:
                return False

        return True

    def loadFile(self, fileName):
        """Load file contents into the editor and reset cursor."""
        file = QFile(fileName)
        if not file.open(QFile.ReadOnly | QFile.Text):
            QMessageBox.warning(
                self,
                "Easy G-code Plot",
                "Cannot read file %s:\n%s." % (fileName, file.errorString()),
            )
            return

        inf = QTextStream(file)
        self.ui.editor.setText(inf.readAll())
        self.ui.editor.setCursorPosition(0, 0)
        self.setCurrentFile(fileName)
        self.changeLang(self.ui.langCombo.currentIndex())

    def saveFile(self, fileName):
        """Write editor contents to disk."""
        file = QFile(fileName)
        if not file.open(QFile.WriteOnly | QFile.Text):
            QMessageBox.warning(
                self,
                "Easy G-code Plot",
                "Cannot write file %s:\n%s." % (fileName, file.errorString()),
            )
            return False

        outf = QTextStream(file)
        outf << self.ui.editor.text()

        self.setCurrentFile(fileName)
        return True

    def setCurrentFile(self, fileName):
        """Update window title and modified flags for the current file."""
        self.curFile = fileName
        self.ui.editor.setModified(False)
        self.setWindowModified(False)

        if self.curFile:
            name = self.strippedName(self.curFile)
        else:
            name = "new"

        self.setWindowTitle("%s[*] - Easy G-code Plot" % name)

    def strippedName(self, fullFileName):
        """Return just the filename component."""
        return QFileInfo(fullFileName).fileName()

    def changeArcType(self):
        """Change arc mode between relative, absolute, or radius modes."""
        if self.ui.actionRelative_to_start.isChecked():
            self.arc_type = 1
        if self.ui.actionAbsolute.isChecked():
            self.arc_type = 2
        if self.ui.actionRadius_value.isChecked():
            self.arc_type = 3
        self.updateData()

    def changeLathe(self):
        """Toggle lathe visualization mode and refresh plot accordingly."""
        if self.ui.actionLatheMode.isChecked():
            self.latheMode = True
            self.ui.action3D.setEnabled(False)
            self.ui.actionTop.setEnabled(False)
            self.ui.actionFront.setEnabled(False)
            self.ui.actionLeft.setEnabled(False)
            self.updateData()
            self.ui.graphicsView.opts["fov"] = 0.01
            self.ui.graphicsView.opts["rotationMethod"] = "quaternion"
            self.ui.graphicsView.setCameraPosition(
                distance=self.dist * 6000, rotation=QQuaternion(0.5, 0.5, 0.5, 0.5)
            )
        else:
            self.latheMode = False
            self.ui.action3D.setEnabled(True)
            self.ui.actionTop.setEnabled(True)
            self.ui.actionFront.setEnabled(True)
            self.ui.actionLeft.setEnabled(True)
            self.ui.graphicsView.opts["rotationMethod"] = "euler"
            self.updateData()
            self.view3d()

    def export(self):
        """Export current program to a chosen file path."""
        path, _ = QFileDialog.getSaveFileName()
        if path:
            val = self.ui.horizontalSlider.value()
            self.updateData()
            self.valueHandler(val)
            txt = ""
            start = time.time()
            try:
                txt = self.exportPgm()
            except Exception as e:
                # logging.exception(str(e))
                QMessageBox.warning(self, "Easy G-code Plot", str(e))

            else:
                end = time.time()
                self.progressBar.setValue(0)
                print(f"Export Execution time: {(end-start)*1000:.3f} ms")
                self.ui.statusbar.showMessage(
                    f"Export Execution time: {(end-start)*1000:.3f} ms", 10000
                )
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt)

    def exportPgm(self):
        """Generate the exportable program text based on parsed toolpath data."""
        return export_pgm(self)

    def floatToStr(self, val):
        """Format numeric values to compact strings for G-code output."""
        if val is None:
            return ""
        if val == 0:
            return "0"
        return "{:.3f}".format(val).rstrip("0").rstrip(".")

    def runFindDlg(self):
        """Show the find/replace dialog, seeding it with the current selection."""
        text = self.ui.editor.selectedText()
        if text:
            self.findDlg.ui.lineEditFind.setText(text)
        self.findDlg.show()

    def find(self, findText, checkCase, checkWholeWord, wrapAround):
        """Search within the editor using the provided options."""
        doc = self.ui.editor
        forward = True
        if forward:
            line, index = doc.getSelection()[2:]
        else:
            line, index = doc.getSelection()[:2]

        state = (
            False,
            checkCase,
            checkWholeWord,
            wrapAround,
            forward,
            line,
            index,
            True,
            False,
        )
        if not doc.findFirst(findText, *state):
            if wrapAround:
                doc.setCursorPosition(0, 0)
                if not doc.findFirst(findText, *state):
                    QMessageBox.information(
                        self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText
                    )
            else:
                QMessageBox.information(
                    self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText
                )

    def replace(self, findText, replaceText, checkCase, checkWholeWord, wrapAround):
        """Replace the current match and continue searching."""
        doc = self.ui.editor
        if findText == doc.selectedText():
            doc.replace(replaceText)
        self.find(findText, checkCase, checkWholeWord, wrapAround)

    def replaceAll(self, findText, replaceText, checkCase, checkWholeWord):
        """Replace every occurrence of the search term in the editor."""
        doc = self.ui.editor
        state = (False, checkCase, checkWholeWord, False, True)
        doc.setCursorPosition(0, 0)
        while True:
            if not doc.findFirst(findText, *state):
                break
            doc.replace(replaceText)

    def clearPlot(self):
        """Reset all plotting data structures and UI controls."""

        # clear lst for self.addmotion
        self.x_axis = []
        self.y_axis = []
        self.z_axis = []
        self.i_axis = []
        self.j_axis = []
        self.k_axis = []
        self.lst_points = []
        self.lst_block = []
        self.lst_feed = []

        # clear lst for self.convert
        self.lstMove = []
        self.lstCoord_X = []
        self.lstCoord_Y = []
        self.lstCoord_Z = []
        self.lstX_incr = []
        self.lstY_incr = []
        self.lstZ_incr = []
        self.lstCoord_I = []
        self.lstCoord_J = []
        self.lstCoord_K = []
        self.lstCoord_R = []
        self.lstCenter_X = []
        self.lstCenter_Y = []
        self.lstCycleDrill = []
        self.lstCycleZ = []
        self.lstCycleP = []
        self.lstCycleQ = []
        self.lstRadius = []
        self.lstTool = []
        self.lstSpeed = []
        self.lstFeed = []
        self.lstComment = []
        self.lstPosMode = []
        self.lstArcPlane = []
        self.lstWcs = []
        self.lstHomePos = []
        self.lstCorLen = []
        self.lstCorRad = []
        self.lstCorH = []
        self.lstCorD = []
        self.lstPgmStop = []
        self.lstSpeedCode = []
        self.lstToolChange = []
        self.lstCoolant = []
        self.lstUnknownWords = []
        self.lstProgram = []

        # reset timer
        self.timer.stop()
        self.step = 0

        # clear displayed axis
        self.ui.lineEditX.clear()
        self.ui.lineEditY.clear()
        self.ui.lineEditZ.clear()
        self.ui.lineEdit_I.clear()
        self.ui.lineEdit_J.clear()
        self.ui.lineEdit_K.clear()
        self.ui.lineEditFeed.clear()

        # clear other
        self.ui.horizontalSlider.setMinimum(1)
        self.ui.horizontalSlider.setValue(1)
        self.ui.actionStep_Backward.setEnabled(False)
        self.ui.actionStep_Forward.setEnabled(False)
        self.ui.actionPlay.setChecked(False)
        self.ui.actionPlay.setEnabled(False)
        self.ui.actionStop.setEnabled(False)
        self.loadPlot()

    def valueHandler(self, value):
        """Update plot and info panes to reflect the current slider value."""
        self.loadPlot()
        try:
            if self.x_axis == [] or self.y_axis == [] or self.z_axis == []:
                return

            if value == 1:
                self.loadPlot()
                self.ui.editor.setCursorPosition(0, 0)
                return

            self.ui.lineEditX.setText(str(round(self.x_axis[value - 1], 3)))
            self.ui.lineEditY.setText(str(round(self.y_axis[value - 1], 3)))
            self.ui.lineEditZ.setText(str(round(self.z_axis[value - 1], 3)))
            if self.i_axis[value - 1] == None:
                self.ui.lineEdit_I.setText("")
            else:
                self.ui.lineEdit_I.setText(str(round(self.i_axis[value - 1], 3)))
            if self.j_axis[value - 1] == None:
                self.ui.lineEdit_J.setText("")
            else:
                self.ui.lineEdit_J.setText(str(round(self.j_axis[value - 1], 3)))
            if self.k_axis[value - 1] == None:
                self.ui.lineEdit_K.setText("")
            else:
                self.ui.lineEdit_K.setText(str(round(self.k_axis[value - 1], 3)))
            if self.lst_feed[value - 1] == self.rapidFeed:
                self.ui.lineEditFeed.setText("Rapid")
            else:
                self.ui.lineEditFeed.setText(str(self.lst_feed[value - 1]))

            point = GLScatterPlotItem(
                pos=(
                    self.lst_points[value - 1][0],
                    self.lst_points[value - 1][1],
                    self.lst_points[value - 1][2],
                ),
                color=QColor(self.plotLineColor),
                size=0.4,
                pxMode=False,
            )
            point.setGLOptions("translucent")
            self.ui.graphicsView.addItem(point)
            drawing = GLLinePlotItem(
                pos=self.lst_points[:value],
                color=QColor(self.plotLineColor),
                width=0.3,
                antialias=True,
            )
            # line = [(self.lst_points[value-1][0], self.lst_points[value-1][1],
            #             self.lst_points[value-1][2]), (self.lst_points[value-1][0],
            #             self.lst_points[value-1][1], self.lst_points[value-1][2] + 10)]
            # tool = GLLinePlotItem(pos = line, color=QColor(self.plotLineColor), width = 1, antialias = True)
            # self.ui.graphicsView.addItem(tool)
            self.ui.graphicsView.addItem(drawing)

        except Exception as e:
            # logging.exception(str(e))
            QMessageBox.warning(self, "Easy G-code Plot", str(e))

    def loadPlot(self):
        """Redraw axes, background, and optional grid before plotting points."""
        self.ui.graphicsView.clear()
        self.ui.graphicsView.setBackgroundColor(self.plotBackground)
        line1 = [(0, 0, 0), (5, 0, 0)]
        line2 = [(0, 0, 0), (0, 5, 0)]
        line3 = [(0, 0, 0), (0, 0, 5)]
        axisX = GLLinePlotItem(pos=line1, color="r", width=3, antialias=True)
        axisY = GLLinePlotItem(pos=line2, color="g", width=3, antialias=True)
        axisZ = GLLinePlotItem(pos=line3, color="y", width=3, antialias=True)
        if self.plotGrid:
            xGrid = GLGridItem()
            yGrid = GLGridItem()
            zGrid = GLGridItem()
            xGrid.setSize(self.plotGridSize, self.plotGridSize)
            xGrid.setSpacing(self.plotGridSpacing, self.plotGridSpacing)
            xGrid.setColor(QColor(self.plotGridColor))
            yGrid.setSize(self.plotGridSize, self.plotGridSize)
            yGrid.setSpacing(self.plotGridSpacing, self.plotGridSpacing)
            yGrid.setColor(QColor(self.plotGridColor))
            zGrid.setSize(self.plotGridSize, self.plotGridSize)
            zGrid.setSpacing(self.plotGridSpacing, self.plotGridSpacing)
            zGrid.setColor(QColor(self.plotGridColor))
            self.ui.graphicsView.addItem(xGrid)
            self.ui.graphicsView.addItem(yGrid)
            self.ui.graphicsView.addItem(zGrid)
            xGrid.rotate(90, 0, 1, 0)
            yGrid.rotate(90, 1, 0, 0)

        self.ui.graphicsView.addItem(axisX)
        self.ui.graphicsView.addItem(axisY)
        self.ui.graphicsView.addItem(axisZ)

    def plotCurLine(self):
        """Sync slider position with the current editor cursor line."""
        num = self.ui.editor.getCursorPosition()[0]
        if num == 0:
            self.ui.horizontalSlider.setValue(1)
        else:
            idx = self.list_rindex(self.lst_block, num)
            if idx:
                self.ui.horizontalSlider.setValue(idx + 1)

    def list_rindex(self, li, x):
        """Return the last index of x in list li."""
        for i in reversed(range(len(li))):
            if li[i] == x:
                return i

    def updateData(self):
        """Parse code, rebuild motion arrays, and refresh controls."""
        res = self.checkCode()
        if res:
            self.addMotion()
            self.calcDist()
            self.ui.actionStep_Backward.setEnabled(True)
            self.ui.actionStep_Forward.setEnabled(True)
            self.ui.actionPlay.setEnabled(True)
            self.ui.actionStop.setEnabled(True)
            self.ui.horizontalSlider.setMaximum(len(self.lst_block))
            self.ui.horizontalSlider.setMinimum(1)
            self.ui.horizontalSlider.setPageStep(int(len(self.lst_block) / 10))

    def setView(self, fov, elevation, azimuth, use_calc_dist=True, dist_scale=6000):
        """Set camera view with optional distance recalculation."""
        if use_calc_dist:
            self.calcDist()
            dist = self.dist * dist_scale
        else:
            dist = self.dist
        self.ui.graphicsView.opts["fov"] = fov
        self.ui.graphicsView.setCameraPosition(
            distance=dist, elevation=elevation, azimuth=azimuth
        )

    def view3d(self):
        """Set 3D camera angle for the plot view."""
        self.setView(60, 30, -45, use_calc_dist=False, dist_scale=1)

    def viewTop(self):
        """Switch camera to a top-down orthographic view."""
        self.setView(0.01, 90, -90)

    def viewFront(self):
        """Switch camera to a front orthographic view."""
        self.setView(0.01, 0, -90)

    def viewLeft(self):
        """Switch camera to a left orthographic view."""
        self.setView(0.01, 0, 180)

    def checkCode(self):
        """Run G-code conversion and verify that motion exists."""
        start = time.time()
        self.convert()
        end = time.time()
        print(f"Сonvert Execution time: {(end-start)*1000:.3f} ms")
        lst_convert = list(zip(self.lstCoord_X, self.lstCoord_Y, self.lstCoord_Z))
        length = 0
        for i in range(len(lst_convert)):
            if i == 0:
                continue
            length = length + sqrt(
                (lst_convert[i][0] - lst_convert[i - 1][0]) ** 2
                + (lst_convert[i][1] - lst_convert[i - 1][1]) ** 2
                + (lst_convert[i][2] - lst_convert[i - 1][2]) ** 2
            )
            if length > 0:
                return True

        return False

    def convert(self):
        """Parse raw editor G-code into structured motion lists."""
        self.clearPlot()
        text = self.ui.editor.text().upper()
        lines = text.splitlines(True)

        prevMove = 0
        prevTool = 0
        prevSpeed = 0
        prevFeed = 0
        prevCorRad = 40
        prevCorD = 0
        prevPosMode = 90
        if self.latheMode:
            prevArcPlane = 18
        else:
            prevArcPlane = 17
        prev_g81 = 80
        Z_cycle = 0
        prevQ = 0
        prevP = 0
        CoordX_abs = self.xPosMach
        CoordY_abs = self.yPosMach
        CoordZ_abs = self.zPosMach
        prevCoordI = None
        prevCoordJ = None
        prevCoordK = None
        prevCoordR = None
        homePos = 0

        for i, line in enumerate(lines):

            self.progressBar.setValue(int((i * 100) / len(lines)))

            comment = "".join(re.findall(r"\(.*?\)", line))
            if comment:
                self.lstComment.append(comment.replace("(", "").replace(")", ""))
                line = line.replace(comment, "")
            else:
                self.lstComment.append(None)

            move = "".join(re.findall(r"G0?[0-3](?=\D)", line))
            coordX = "".join(re.findall(r"X[-+]?[0-9]*\.?[0-9]+", line))
            coordY = "".join(re.findall(r"Y[-+]?[0-9]*\.?[0-9]+", line))
            coordZ = "".join(re.findall(r"Z[-+]?[0-9]*\.?[0-9]+", line))
            coordI = "".join(re.findall(r"I[-+]?[0-9]*\.?[0-9]+", line))
            coordJ = "".join(re.findall(r"J[-+]?[0-9]*\.?[0-9]+", line))
            coordK = "".join(re.findall(r"K[-+]?[0-9]*\.?[0-9]+", line))
            coordR = "".join(re.findall(r"R[-+]?[0-9]*\.?[0-9]+", line))
            tool = "".join(re.findall(r"T[0-9]{1,4}", line))
            speed = "".join(re.findall(r"S[0-9]{1,5}", line))
            feed = "".join(re.findall(r"F[0-9]*\.?[0-9]+", line))
            posMode = "".join(re.findall(r"G9[0,1](?=\D)", line))
            arcPlane = "".join(re.findall(r"G1[7-9](?=\D)", line))
            wcs = "".join(re.findall(r"G5[4-9](?=\D)", line))
            g81 = "".join(re.findall(r"G8[0-4](?=\D)", line))
            P_cycle = "".join(re.findall(r"P[-+]?[0-9]*\.?[0-9]+", line))
            Q_cycle = "".join(re.findall(r"Q[-+]?[0-9]*\.?[0-9]+", line))
            corLen = "".join(re.findall(r"G43(?=\D)", line))
            corRad = "".join(re.findall(r"G4[0-2](?=\D)", line))
            corH = "".join(re.findall(r"H[0-9]{1,4}", line))
            corD = "".join(re.findall(r"D[0-9]{1,4}", line))
            toolchange = "".join(re.findall(r"M0?6(?=\D)", line))
            stopPgrm = "".join(re.findall(r"M0?[0,1](?=\D)", line))
            spindelCode = "".join(re.findall(r"M0?[3-5](?=\D)", line))
            coolant = "".join(re.findall(r"M0?[7-9](?=\D)", line))
            homePosLine = "".join(re.findall(r"G28.*", line))

            if homePosLine:
                xHomeCoord = "".join(
                    re.findall(r"[X][-+]?[0-9]*\.?[0-9]+", homePosLine)
                )
                yHomeCoord = "".join(
                    re.findall(r"[Y][-+]?[0-9]*\.?[0-9]+", homePosLine)
                )
                zHomeCoord = "".join(
                    re.findall(r"[Z][-+]?[0-9]*\.?[0-9]+", homePosLine)
                )

                if xHomeCoord:
                    # G28X0 - 1
                    homePos = 1
                    if yHomeCoord:
                        # G28X0Y0 - 4
                        homePos = 4
                        if zHomeCoord:
                            # G28X0Y0Z0 - 7
                            homePos = 7
                    elif zHomeCoord:
                        # G28X0Z0 - 5
                        homePos = 5
                elif yHomeCoord:
                    # G28Y0 - 2
                    homePos = 2
                    if zHomeCoord:
                        # G28Y0Z0 - 6
                        homePos = 6
                elif zHomeCoord:
                    # G28Z0 - 3
                    homePos = 3
                else:
                    homePos = 0
                if homePos != 0:
                    self.lstHomePos.append(homePos)
                else:
                    self.lstHomePos.append(None)
            else:
                homePos = 0
                self.lstHomePos.append(None)

            line1 = (
                move
                + arcPlane
                + posMode
                + coordX
                + coordY
                + coordZ
                + coordI
                + coordJ
                + coordK
                + coordR
                + tool
                + speed
                + feed
                + comment
                + stopPgrm
                + spindelCode
                + toolchange
                + coolant
                + wcs
                + corLen
                + corRad
                + corH
                + corD
                + g81
                + Q_cycle
                + P_cycle
            )

            if line1 == "":
                self.lstUnknownWords.append(line)
            else:
                self.lstUnknownWords.append(None)

            if toolchange:
                self.lstToolChange.append(int(toolchange.replace("M", "")))
            else:
                self.lstToolChange.append(None)

            if g81:
                prev_g81 = int(g81.replace("G", ""))
                prevMove = 0
            self.lstCycleDrill.append(prev_g81)

            if move and prev_g81 == 80:
                prevMove = int(move.replace("G", ""))
            self.lstMove.append(prevMove)

            if posMode:
                prevPosMode = int(posMode.replace("G", ""))
            self.lstPosMode.append(prevPosMode)

            if arcPlane:
                prevArcPlane = int(arcPlane.replace("G", ""))
            self.lstArcPlane.append(prevArcPlane)

            if coordX:
                if prevPosMode == 90:
                    CoordX_abs = float(coordX.replace("X", ""))
                else:
                    if homePos == 0:
                        CoordX_abs = CoordX_abs + float(coordX.replace("X", ""))
                    elif homePos == 1 or homePos == 4 or homePos == 5 or homePos == 7:
                        CoordX_abs = self.xPosMach
                self.lstCoord_X.append(CoordX_abs)
            else:
                self.lstCoord_X.append(CoordX_abs)

            if coordY:
                if prevPosMode == 90:
                    CoordY_abs = float(coordY.replace("Y", ""))
                else:
                    if homePos == 0:
                        CoordY_abs = CoordY_abs + float(coordY.replace("Y", ""))
                    elif homePos == 2 or homePos == 4 or homePos > 5:
                        CoordY_abs = self.yPosMach
                self.lstCoord_Y.append(CoordY_abs)
            else:
                self.lstCoord_Y.append(CoordY_abs)

            if coordZ:
                if prevPosMode == 90:
                    if prev_g81 == 80:
                        CoordZ_abs = float(coordZ.replace("Z", ""))
                        Z_cycle = 0
                    else:
                        Z_cycle = float(coordZ.replace("Z", ""))
                else:
                    if prev_g81 == 80:
                        CoordZ_abs = CoordZ_abs + float(coordZ.replace("Z", ""))
                        Z_cycle = 0
                    else:
                        Z_cycle = Z_cycle + float(coordZ.replace("Z", ""))

                    if homePos == 3 or homePos > 4:
                        CoordZ_abs = self.zPosMach

                self.lstCoord_Z.append(CoordZ_abs)
                self.lstCycleZ.append(Z_cycle)
            else:
                if prev_g81 == 80:
                    Z_cycle = 0
                self.lstCoord_Z.append(CoordZ_abs)
                self.lstCycleZ.append(Z_cycle)

            if coordI:
                prevCoordI = float(coordI.replace("I", ""))
            else:
                prevCoordI = None
            self.lstCoord_I.append(prevCoordI)

            if coordJ:
                prevCoordJ = float(coordJ.replace("J", ""))
            else:
                prevCoordJ = None
            self.lstCoord_J.append(prevCoordJ)

            if coordK:
                prevCoordK = float(coordK.replace("K", ""))
            else:
                prevCoordK = None
            self.lstCoord_K.append(prevCoordK)

            if coordR:
                prevCoordR = float(coordR.replace("R", ""))
            else:
                if prev_g81 == 80:
                    prevCoordR = None
            self.lstCoord_R.append(prevCoordR)

            if P_cycle:
                prevP = float(P_cycle.replace("P", ""))
            else:
                if prev_g81 < 82 or prev_g81 > 83:
                    prevP = None
            self.lstCycleP.append(prevP)

            if Q_cycle:
                prevQ = float(Q_cycle.replace("Q", ""))
            else:
                if prev_g81 != 83:
                    prevQ = None
            self.lstCycleQ.append(prevQ)

            if tool:
                prevTool = int(tool.replace("T", ""))
            self.lstTool.append(prevTool)

            if speed:
                prevSpeed = int(speed.replace("S", ""))
            self.lstSpeed.append(prevSpeed)

            if feed:
                prevFeed = float(feed.replace("F", ""))
            self.lstFeed.append(prevFeed)

            if wcs:
                self.lstWcs.append(int(wcs.replace("G", "")))
            else:
                self.lstWcs.append(None)

            if corLen:
                self.lstCorLen.append(int(corLen.replace("G", "")))
            else:
                self.lstCorLen.append(None)

            if corH:
                self.lstCorH.append(int(corH.replace("H", "")))
            else:
                self.lstCorH.append(None)

            if corRad:
                prevCorRad = int(corRad.replace("G", ""))
            self.lstCorRad.append(prevCorRad)

            if corD:
                prevCorD = int(corD.replace("D", ""))
            self.lstCorD.append(prevCorD)

            if stopPgrm:
                self.lstPgmStop.append(int(stopPgrm.replace("M", "")))
            else:
                self.lstPgmStop.append(None)

            if spindelCode:
                self.lstSpeedCode.append(int(spindelCode.replace("M", "")))
            else:
                self.lstSpeedCode.append(None)

            if coolant:
                self.lstCoolant.append(int(coolant.replace("M", "")))
            else:
                self.lstCoolant.append(None)

        self.progressBar.setValue(0)

    def circular(self, move, plane, x1, y1, z1, i, j, x2, y2, z2, r, f, num):
        """Generate interpolated circular/helix points for plotting."""
        lst = []
        xc = x1
        yc = y1
        radius = 0
        if self.arc_type == 1:
            xc = x1 + i
            yc = y1 + j
            radius = sqrt((x1 - xc) ** 2 + (y1 - yc) ** 2)
        elif self.arc_type == 2:
            xc = i
            yc = j
            radius = sqrt((x1 - xc) ** 2 + (y1 - yc) ** 2)
        elif self.arc_type == 3:
            if r == 0:
                return []
            d = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            h = sqrt(r**2 - (d / 2) ** 2)
            radius = abs(r)
            if r > 0:
                if move == 2:
                    xc = x1 + (x2 - x1) / 2 + h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 - h * (x2 - x1) / d
                else:
                    xc = x1 + (x2 - x1) / 2 - h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 + h * (x2 - x1) / d
            elif r < 0:
                if move == 2:
                    xc = x1 + (x2 - x1) / 2 - h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 + h * (x2 - x1) / d
                else:
                    xc = x1 + (x2 - x1) / 2 + h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 - h * (x2 - x1) / d
        else:
            return []

        k = (z2 or 0) - (z1 or 0)
        zc = z1

        v0 = (xc - x1, yc - y1)
        v1 = (xc - x2, yc - y2)
        v2 = (0 - radius, 0)

        startAngle = atan2(v0[1], v0[0]) - atan2(v2[1], v2[0])
        angle = atan2(v1[1], v1[0]) - atan2(v0[1], v0[0])

        if startAngle < 0:
            startAngle = startAngle + 2 * pi

        if move == 2:
            angle = atan2(v0[1], v0[0]) - atan2(v1[1], v1[0])
        else:
            angle = atan2(v1[1], v1[0]) - atan2(v0[1], v0[0])

        if angle <= 0:
            angle = angle + 2 * pi

        # tolerance = 2 * pi/points
        points = (angle * 314) / (2 * pi)
        step = k / points
        points = int(points)

        if move == 2:
            angle = -1 * abs(angle)

        for point in range(1, points):
            delta = point * angle / points
            x = xc + radius * cos(startAngle + delta)
            y = yc + radius * sin(startAngle + delta)
            z = z1 + step * point
            if plane == 17:
                lst.append([x, y, z, xc, yc, zc, xc, yc, f, num])
            elif plane == 18:
                lst.append([x, z, y, xc, zc, yc, xc, yc, f, num])
            elif plane == 19:
                lst.append([z, x, y, zc, xc, yc, xc, yc, f, num])

        if plane == 17:
            lst.append([x2, y2, z2, xc, yc, zc, xc, yc, f, num])
        elif plane == 18:
            lst.append([x2, z2, y2, xc, zc, yc, xc, yc, f, num])
        elif plane == 19:
            lst.append([z2, x2, y2, zc, xc, yc, xc, yc, f, num])

        return lst

    def calcTime(self):
        """Calculate path lengths and estimated time from toolpath data."""
        self.lst_toolpath = []
        self.lst_toolpathTime = []
        lst = list(zip(self.x_axis, self.y_axis, self.z_axis, self.lst_feed))

        for i in range(len(lst)):
            if i == 0:
                continue

            segment_time = 0
            length = 0
            f = lst[i][3]
            length = sqrt(
                (lst[i][0] - lst[i - 1][0]) ** 2
                + (lst[i][1] - lst[i - 1][1]) ** 2
                + (lst[i][2] - lst[i - 1][2]) ** 2
            )
            if f > 0:
                segment_time = length / f

            self.lst_toolpath.append(length)
            self.lst_toolpathTime.append(segment_time)

        if len(lst) != 0:
            return True
        else:
            return False

    def addValues(self, x, y, z, i, j, k, xc, yc, f, num):
        """Add a single motion point and accompanying metadata."""
        self.x_axis.append(x)
        self.y_axis.append(y)
        self.z_axis.append(z)
        self.i_axis.append(i)
        self.j_axis.append(j)
        self.k_axis.append(k)
        self.lstCenter_X.append(xc)
        self.lstCenter_Y.append(yc)
        self.lst_feed.append(f)
        self.lst_block.append(num)

    def cycleDrill(self, cycle, posMode, x, y, z, r, z_cycle, q, feed, i):
        """Expand drilling cycles into discrete motion points."""
        if cycle > 80:
            if posMode == 90:
                z_ref = r
                z_end = z_cycle
            else:
                z_ref = z + r
                z_end = z + z_cycle

            if cycle == 83 and q != 0:
                z_cycle = z_ref
                ost = abs(z_end - z_ref) % q

                if ost > 0:
                    numbers = int(abs(z_end - z_ref) // q)
                else:
                    numbers = int(abs(z_end - z_ref) / q) - 1

                self.addValues(x, y, z, None, None, None, None, None, self.rapidFeed, i)

                for num in range(numbers):
                    z_cycle = z_cycle - q

                    self.addValues(
                        x, y, z_ref, None, None, None, None, None, self.rapidFeed, i
                    )

                    if num == 0:
                        self.addValues(
                            x, y, z_cycle, None, None, None, None, None, feed, i
                        )
                        self.addValues(
                            x, y, z_ref, None, None, None, None, None, self.rapidFeed, i
                        )
                    else:
                        self.addValues(
                            x,
                            y,
                            z_cycle + q,
                            None,
                            None,
                            None,
                            None,
                            None,
                            self.rapidFeed,
                            i,
                        )
                        self.addValues(
                            x, y, z_cycle, None, None, None, None, None, feed, i
                        )
                        self.addValues(
                            x, y, z_ref, None, None, None, None, None, self.rapidFeed, i
                        )

                self.addValues(
                    x, y, z_cycle, None, None, None, None, None, self.rapidFeed, i
                )
                self.addValues(x, y, z_end, None, None, None, None, None, feed, i)

            else:
                self.addValues(x, y, z, None, None, None, None, None, self.rapidFeed, i)
                self.addValues(
                    x, y, z_ref, None, None, None, None, None, self.rapidFeed, i
                )
                self.addValues(x, y, z_end, None, None, None, None, None, feed, i)

    def addMotion(self):
        """Populate plotting arrays based on parsed moves and feed values."""
        text = self.ui.editor.text().upper()
        lst_pgm = text.splitlines(True)
        try:
            start = time.time()

            for i in range(len(self.lstMove)):

                self.progressBar.setValue(int((i * 100) / len(self.lstMove)))

                m30 = "".join(re.findall(r"M30", lst_pgm[i]))
                m2 = "".join(re.findall(r"M[0]?2(?=\D)", lst_pgm[i]))
                blockskip = "".join(re.findall(r"^\/.*", lst_pgm[i]))

                if m30 or m2:
                    break

                if blockskip:
                    continue

                if self.latheMode:
                    scale = 0.5
                    feed = self.lstFeed[i] * self.lstSpeed[i]
                else:
                    scale = 1
                    feed = self.lstFeed[i]

                if i > 0:
                    prev_x = self.lstCoord_X[i - 1] * scale
                    prev_y = self.lstCoord_Y[i - 1]
                    prev_z = self.lstCoord_Z[i - 1]
                else:
                    prev_x = 0
                    prev_y = 0
                    prev_z = 0

                x = self.lstCoord_X[i] * scale
                y = self.lstCoord_Y[i]
                z = self.lstCoord_Z[i]

                if self.lstCoord_I[i] != None:
                    cx = self.lstCoord_I[i]
                else:
                    cx = 0

                if self.lstCoord_J[i] != None:
                    cy = self.lstCoord_J[i]
                else:
                    cy = 0

                if self.lstCoord_K[i] != None:
                    cz = self.lstCoord_K[i]
                else:
                    cz = 0

                if self.lstCoord_R[i] != None:
                    adr_R = self.lstCoord_R[i]
                else:
                    adr_R = 0

                if self.lstCycleQ[i] != None:
                    q = self.lstCycleQ[i]
                else:
                    q = 0

                self.lstX_incr.append(x - prev_x)
                self.lstY_incr.append(y - prev_y)
                self.lstZ_incr.append(z - prev_z)

                if self.lstMove[i] == 0:
                    if self.lstCycleDrill[i] > 80:
                        self.cycleDrill(
                            self.lstCycleDrill[i],
                            self.lstPosMode[i],
                            x,
                            y,
                            z,
                            adr_R,
                            self.lstCycleZ[i],
                            q,
                            feed,
                            i,
                        )

                    self.addValues(
                        x, y, z, None, None, None, None, None, self.rapidFeed, i
                    )

                elif self.lstMove[i] == 1:
                    self.addValues(x, y, z, None, None, None, None, None, feed, i)

                elif self.lstMove[i] > 1:

                    lst = []
                    if self.lstMove[i] == 2:
                        if self.lstArcPlane[i] == 17:
                            lst = self.circular(
                                2,
                                17,
                                prev_x,
                                prev_y,
                                prev_z,
                                cx,
                                cy,
                                x,
                                y,
                                z,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 18:
                            lst = self.circular(
                                3,
                                18,
                                prev_x,
                                prev_z,
                                prev_y,
                                cx,
                                cz,
                                x,
                                z,
                                y,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 19:
                            lst = self.circular(
                                2,
                                19,
                                prev_y,
                                prev_z,
                                prev_x,
                                cy,
                                cz,
                                y,
                                z,
                                x,
                                adr_R,
                                feed,
                                i,
                            )
                    elif self.lstMove[i] == 3:
                        if self.lstArcPlane[i] == 17:
                            lst = self.circular(
                                3,
                                17,
                                prev_x,
                                prev_y,
                                prev_z,
                                cx,
                                cy,
                                x,
                                y,
                                z,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 18:
                            lst = self.circular(
                                2,
                                18,
                                prev_x,
                                prev_z,
                                prev_y,
                                cx,
                                cz,
                                x,
                                z,
                                y,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 19:
                            lst = self.circular(
                                3,
                                19,
                                prev_y,
                                prev_z,
                                prev_x,
                                cy,
                                cz,
                                y,
                                z,
                                x,
                                adr_R,
                                feed,
                                i,
                            )
                    if not lst:
                        continue

                    l = list(zip(*lst))
                    self.x_axis.extend(l[0])
                    self.y_axis.extend(l[1])
                    self.z_axis.extend(l[2])
                    self.i_axis.extend(l[3])
                    self.j_axis.extend(l[4])
                    self.k_axis.extend(l[5])
                    self.lstCenter_X.extend(l[6])
                    self.lstCenter_Y.extend(l[7])
                    self.lst_feed.extend(l[8])
                    self.lst_block.extend(l[9])

        except Exception as e:
            # logging.exception(str(e))
            QMessageBox.warning(self, "Easy G-code Plot", str(e))

        else:
            end = time.time()
            self.progressBar.setValue(0)
            print(f"Сycle Execution time: {(end-start)*1000:.3f} ms")
            self.ui.statusbar.showMessage(
                f"Сycle Execution time: {(end-start)*1000:.3f} ms", 10000
            )

            self.lst_points = list(zip(self.x_axis, self.y_axis, self.z_axis))

    def lstExport(self):
        """Build filtered program data list used for exporting and stats."""

        lst = list(
            zip(
                self.lstMove,
                self.lstArcPlane,
                self.lstPosMode,
                self.lstCoord_X,
                self.lstCoord_Y,
                self.lstCoord_Z,
                self.lstX_incr,
                self.lstY_incr,
                self.lstZ_incr,
                self.lstCenter_X,
                self.lstCenter_Y,
                self.lstFeed,
                self.lstWcs,
                self.lstHomePos,
                self.lstTool,
                self.lstToolChange,
                self.lstSpeed,
                self.lstSpeedCode,
                self.lstCoolant,
                self.lstPgmStop,
                self.lstCorLen,
                self.lstCorH,
                self.lstCorRad,
                self.lstCorD,
                self.lstComment,
                self.lstCycleDrill,
                self.lstCycleZ,
                self.lstCoord_R,
                self.lstCycleP,
                self.lstCycleQ,
            )
        )

        for i in range(len(lst)):
            if self.lstUnknownWords[i] == None:
                length = sqrt((lst[i][6]) ** 2 + (lst[i][7]) ** 2 + (lst[i][8]) ** 2)
                lst1 = []
                if lst[i][0] > 1 or length > 0 or lst[i][25] > 80 or lst[i][12] != None:
                    for j in range(len(lst[i])):
                        lst1.append(lst[i][j])
                else:
                    for j in range(len(lst[i])):
                        if j < 11:
                            lst1.append(None)
                        else:
                            lst1.append(lst[i][j])
                self.lstProgram.append(lst1)

        self.calcTime()

    def toolPath(self):
        """Return formatted toolpath length and estimated machining time."""
        if not self.calcTime():
            res = ""
            return res
        time_min = round(sum(self.lst_toolpathTime), 2)
        time_hours = time_min / 60
        time_sec = time_min * 60
        hours_part = floor(time_hours)
        minutes_part = floor(time_min % 60)
        seconds_part = floor(time_sec % 60)
        res = (
            self.co
            + "Toolpath Length: {:.3f}".format((sum(self.lst_toolpath)))
            + self.ci
            + "\n"
            + self.co
            + "Machining Time: {h:02}:{m:02}:{s:02}".format(
                h=hours_part, m=minutes_part, s=seconds_part
            )
            + self.ci
            + "\n"
        )
        return res

    def toolPathLimits(self):
        """Return formatted min/max extents of the generated toolpath."""
        if not self.calcTime():
            res = ""
            return res

        if self.latheMode:
            xmin = (
                self.co
                + "X MIN: {}".format(round(min(self.x_axis) * 2, 3))
                + self.ci
                + "\n"
            )
            xmax = (
                self.co
                + "X MAX: {}".format(round(max(self.x_axis) * 2, 3))
                + self.ci
                + "\n"
            )
        else:
            xmin = (
                self.co
                + "X MIN: {}".format(round(min(self.x_axis), 3))
                + self.ci
                + "\n"
            )
            xmax = (
                self.co
                + "X MAX: {}".format(round(max(self.x_axis), 3))
                + self.ci
                + "\n"
            )

        ymin = self.co + "Y MIN: {}".format(round(min(self.y_axis), 3)) + self.ci + "\n"
        zmin = self.co + "Z MIN: {}".format(round(min(self.z_axis), 3)) + self.ci + "\n"
        ymax = self.co + "Y MAX: {}".format(round(max(self.y_axis), 3)) + self.ci + "\n"
        zmax = self.co + "Z MAX: {}".format(round(max(self.z_axis), 3)) + self.ci
        res = xmin + ymin + zmin + xmax + ymax + zmax
        return res

    def statistics(self):
        """Display path length, machining time, and limits in a message box."""
        txt = self.toolPath() + self.toolPathLimits()
        if txt:
            QMessageBox.information(
                self, "Easy G-code Plot", txt.replace("(", "").replace(")", "")
            )
        else:
            QMessageBox.information(self, "Easy G-code Plot", "No Data Available")

    def _process_selected_lines(self, handler):
        """Apply a line transformer to selected text or the whole document."""
        if not self.ui.editor.text():
            return
        text = self.ui.editor.selectedText()
        if not text:
            self.ui.editor.selectAll()
            text = self.ui.editor.text()
        lines = text.splitlines(True)
        transformed = handler(lines)
        if transformed is not None:
            self.ui.editor.replaceSelectedText("".join(transformed))

    def renumber(self):
        """Add or update block numbers for the selected or full document."""
        st = self.seqNumStart
        incr = self.seqNumIncr
        delim = " " if self.seqNumSpacing else ""

        def handler(lines):
            nonlocal st
            lst = []
            for line in lines:
                skipline = "".join(re.findall(r"^[%O\r\n]", line))
                if skipline:
                    lst.append(line)
                    continue
                num = "".join(re.findall(r"^N\d+", line))
                if num:
                    new_line = (
                        "N{}".format(st) + delim + re.sub(r"^N\d+", "", line).lstrip()
                    )
                else:
                    new_line = "N{}".format(st) + delim + line.lstrip()
                lst.append(new_line)
                st = st + incr
            return lst

        self._process_selected_lines(handler)

    def numbRemove(self):
        """Remove block numbers from the selected or full document."""

        def handler(lines):
            lst = []
            for line in lines:
                num = "".join(re.findall(r"^N\d+", line))
                if num:
                    new_line = re.sub(r"^N\d+", "", line).lstrip()
                else:
                    new_line = line
                lst.append(new_line)
            return lst

        self._process_selected_lines(handler)

    def removeSpaces(self):
        """Strip spaces from code while preserving parenthesized comments."""

        def handler(lines):
            lst = []
            for line in lines:
                comment = "".join(re.findall(r"\(.*?\)", line))
                if comment:
                    new_line = line.replace(" ", "")
                    new_line = re.sub(r"\(.*?\)", comment, new_line)
                else:
                    new_line = line.replace(" ", "")
                lst.append(new_line)
            return lst

        self._process_selected_lines(handler)

    def removeLines(self):
        """Trim empty lines from the selection or whole document."""

        def handler(lines):
            lst = []
            for line in lines:
                emptyline = "".join(re.findall(r"^[\r\n]", line))
                if emptyline:
                    new_line = line.lstrip()
                else:
                    new_line = line
                lst.append(new_line)
            return lst

        self._process_selected_lines(handler)

    def calcDist(self):
        """Calculate scene center and distance scaling based on toolpath extents."""
        try:
            if self.lst_points == []:
                return

            ax1_min = min(self.x_axis)
            ax1_max = max(self.x_axis)
            ax2_min = min(self.y_axis)
            ax2_max = max(self.y_axis)
            ax3_min = min(self.z_axis)
            ax3_max = max(self.z_axis)

            x = ax1_min + (ax1_max - ax1_min) / 2
            y = ax2_min + (ax2_max - ax2_min) / 2
            z = ax3_min + (ax3_max - ax3_min) / 2

            diag = int(sqrt((ax1_max - ax1_min) ** 2 + (ax2_max - ax2_min) ** 2))
            self.dist = diag + diag * 0.5
            self.ui.graphicsView.opts["center"] = QVector3D(x, y, z)
        except Exception as e:
            # logging.exception(str(e))
            QMessageBox.warning(self, "Easy G-code Plot", str(e))

    def about(self):
        """Show application about dialog."""
        QMessageBox.about(
            self,
            "Easy G-code Plot",
            "This program is free software\nDeveloper: MaestroFusion360\nVersion: 1.0.0\n2025/12/09",
        )


# endregion


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
