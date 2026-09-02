"""Main application window."""

import re
import time
from math import floor, sqrt

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QBasicTimer, QFile, QFileInfo, QSize, Qt, QTextStream, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont, QIcon, QQuaternion, QVector3D
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
)
from pyqtgraph.opengl import GLGridItem, GLLinePlotItem, GLScatterPlotItem

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources on import.
from app import get_version
from app.gcode.core import (
    calculate_scene_geometry,
    format_gcode_number,
    has_motion,
    last_index,
)
from app.gcode.exporter import export_pgm
from app.gcode.processing import GcodeProcessingMixin
from app.settings import get_settings
from app.ui.dialogs import BlockNum, Export, Find
from app.ui.generated.main_ui import Ui_MainWindow
from app.ui.lexer import GcodeLexer

# Programs above this many editor lines are never refreshed automatically:
# parsing such documents is too slow to run after every edit.
AUTO_REFRESH_MAX_LINES = 5000
# An automatic refresh is skipped when the program would generate more than this
# many toolpath points. Segment-heavy code (many G2/G3 or G83 cycles) can expand
# a small file into a huge point cloud, so the decision is made on the estimated
# point count rather than on the number of source lines.
AUTO_REFRESH_MAX_POINTS = 20000
# Delay (ms) between the last edit and the automatic scene refresh.
AUTO_REFRESH_DELAY_MS = 500


class MainWindow(GcodeProcessingMixin, QMainWindow):
    """Main application window for editing, validating, plotting, and exporting G-code."""

    def __init__(self):
        """Initialize UI, load persisted preferences, and prepare plotting state."""
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        icon = QIcon()
        icon.addFile(":/resource/icons/logo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
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

        self.settings = get_settings()

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
        self.fontFamily = self.settings.value("EDITOR/TEXT_FONT_FAMILY", "Courier New")
        self.sizeTxt = self.settings.value("EDITOR/TEXT_FONT_SIZE", 12, type=int)
        self.fontWeight = self.settings.value("EDITOR/TEXT_FONT_WEIGHT", 500, type=int)
        self.fontItalic = self.settings.value("EDITOR/TEXT_FONT_ITALIC", False, type=bool)

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

        self.exportDlg = Export(self)
        self.findDlg = Find(self)
        self.blockNumDlg = BlockNum(self)
        self.timer = QBasicTimer()
        self.autoUpdateTimer = QTimer(self)
        self.autoUpdateTimer.setSingleShot(True)
        self.autoUpdateTimer.setInterval(AUTO_REFRESH_DELAY_MS)
        self.autoUpdateTimer.timeout.connect(self.autoUpdate)

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
        self.cursorPosLabel.setText("Ln: {}/{}, Col:{}".format(line + 1, self.ui.editor.lines(), index + 1))

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
        self.ui.editor.textChanged.connect(self.scheduleAutoUpdate)
        self.ui.editor.cursorPositionChanged.connect(self.updateStatusBar)
        self.ui.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.editor.customContextMenuRequested.connect(self.editorContextMenu)

        self.ui.graphicsView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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
        print(f"Paint Execution time: {(end - start) * 1000:.3f} ms")

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
            self.scheduleAutoUpdate()

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
                print(f"Load file time: {(end - start) * 1000:.3f} ms")

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
            buttons = (
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            ret = QMessageBox.warning(
                self,
                "Easy G-code Plot",
                "The document has been modified.\nDo you want to save your changes?",
                buttons,
            )

            if ret == QMessageBox.StandardButton.Save:
                return self.save()

            if ret == QMessageBox.StandardButton.Cancel:
                return False

        return True

    def loadFile(self, fileName):
        """Load file contents into the editor and reset cursor."""
        file = QFile(fileName)
        if not file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
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
        self.scheduleAutoUpdate()

    def saveFile(self, fileName):
        """Write editor contents to disk."""
        file = QFile(fileName)
        if not file.open(QFile.OpenModeFlag.WriteOnly | QFile.OpenModeFlag.Text):
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
            self.ui.graphicsView.setCameraPosition(distance=self.dist * 6000, rotation=QQuaternion(0.5, 0.5, 0.5, 0.5))
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
                print(f"Export Execution time: {(end - start) * 1000:.3f} ms")
                self.ui.statusbar.showMessage(f"Export Execution time: {(end - start) * 1000:.3f} ms", 10000)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt)

    def exportPgm(self):
        """Generate the exportable program text based on parsed toolpath data."""
        return export_pgm(self)

    def floatToStr(self, val):
        """Format numeric values to compact strings for G-code output."""
        return format_gcode_number(val)

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
                    QMessageBox.information(self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText)
            else:
                QMessageBox.information(self, "Easy G-code Plot", "Cannot find text:\n'%s'" % findText)

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

    def scheduleAutoUpdate(self):
        """Restart the debounce timer after an edit.

        The scene is refreshed a moment after the last change only when the
        program is small enough (see ``autoUpdate``); large programs keep full
        control via the Refresh action.
        """
        self.autoUpdateTimer.stop()
        self.autoUpdateTimer.start()

    def autoUpdate(self):
        """Refresh the scene automatically once edits have settled.

        Only programs whose estimated toolpath is small are refreshed. The size
        is measured in generated points (arcs and drilling cycles expand into
        many points), so a file with few lines but many G2/G3 stays manual.
        """
        if self.ui.editor.lines() > AUTO_REFRESH_MAX_LINES:
            return

        try:
            self.convert()
        except Exception:
            return

        if not has_motion(self.lstCoord_X, self.lstCoord_Y, self.lstCoord_Z):
            return
        if self._countProgramPoints() > AUTO_REFRESH_MAX_POINTS:
            return

        self._finishDataUpdate()

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
        return last_index(li, x)

    def updateData(self):
        """Parse code, rebuild motion arrays, and refresh controls."""
        res = self.checkCode()
        if res:
            self._finishDataUpdate()

    def _finishDataUpdate(self):
        """Build the toolpath from the parsed data and enable playback controls."""
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
        self.ui.graphicsView.setCameraPosition(distance=dist, elevation=elevation, azimuth=azimuth)

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
            + "Machining Time: {h:02}:{m:02}:{s:02}".format(h=hours_part, m=minutes_part, s=seconds_part)
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
            xmin = self.co + "X MIN: {}".format(round(min(self.x_axis) * 2, 3)) + self.ci + "\n"
            xmax = self.co + "X MAX: {}".format(round(max(self.x_axis) * 2, 3)) + self.ci + "\n"
        else:
            xmin = self.co + "X MIN: {}".format(round(min(self.x_axis), 3)) + self.ci + "\n"
            xmax = self.co + "X MAX: {}".format(round(max(self.x_axis), 3)) + self.ci + "\n"

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
            QMessageBox.information(self, "Easy G-code Plot", txt.replace("(", "").replace(")", ""))
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
                    new_line = "N{}".format(st) + delim + re.sub(r"^N\d+", "", line).lstrip()
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

            center, self.dist = calculate_scene_geometry(self.x_axis, self.y_axis, self.z_axis)
            self.ui.graphicsView.opts["center"] = QVector3D(*center)
        except Exception as e:
            # logging.exception(str(e))
            QMessageBox.warning(self, "Easy G-code Plot", str(e))

    def about(self):
        """Show application about dialog."""
        QMessageBox.about(
            self,
            "Easy G-code Plot",
            f"This program is free software\nDeveloper: MaestroFusion360\nVersion: {get_version()}\n2025/12/09",
        )
