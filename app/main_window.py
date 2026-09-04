"""Main application window."""

import re
import time
from math import floor

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QBasicTimer, QEvent, QFile, QFileInfo, QObject, QSize, Qt, QTextStream, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont, QIcon, QQuaternion, QVector3D, QVector4D
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
    last_index,
)
from app.gcode.exporter import export_pgm
from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace, trace_statistics
from app.plot_grid import adaptive_grid_geometry
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
RECENT_FILES_LIMIT = 5
PICK_DISTANCE_PX = 8.0
CURSOR_SIZE_PX = 7.0
RAPID_COLOR = "#d02020"


def _normalized_recent_files(paths, limit=RECENT_FILES_LIMIT):
    """Return a stable, case-insensitive MRU list without empty values."""
    out = []
    seen = set()
    for value in paths or []:
        path = str(value).strip()
        key = path.casefold()
        if not path or key in seen:
            continue
        out.append(path)
        seen.add(key)
        if len(out) >= limit:
            break
    return out


def _point_segment_distance(px, py, ax, ay, bx, by):
    """Return the 2D distance from a point to a line segment."""
    dx = bx - ax
    dy = by - ay
    if dx == 0.0 and dy == 0.0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    qx = ax + t * dx
    qy = ay + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


class PlotNavigation(QObject):
    """CAD-like viewport navigation matching the CNCEditor OpenTK controls."""

    def __init__(self, view, on_view_changed=None, on_pick=None):
        super().__init__(view)
        self.view = view
        self.on_view_changed = on_view_changed or (lambda: None)
        self.on_pick = on_pick or (lambda _pos: None)
        self._drag_pos = None

    def eventFilter(self, watched, event):
        if watched is not self.view:
            return False

        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._drag_pos = None
                self.on_pick(event.position())
                return True
            if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
                self._drag_pos = event.position()
                return True
        elif event_type == QEvent.Type.MouseButtonRelease:
            if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
                self._drag_pos = None
                return True
        elif event_type == QEvent.Type.MouseMove and self._drag_pos is not None:
            pos = event.position()
            diff = pos - self._drag_pos
            self._drag_pos = pos

            if event.buttons() & Qt.MouseButton.LeftButton:
                self.view.pan(diff.x(), diff.y(), 0, relative="view")
                QTimer.singleShot(0, self.on_view_changed)
                return True
            if event.buttons() & Qt.MouseButton.MiddleButton:
                if self.view.opts["rotationMethod"] == "euler":
                    self.view.orbit(-diff.x(), diff.y())
                else:
                    self.view.pan(diff.x(), diff.y(), 0, relative="view")
                    QTimer.singleShot(0, self.on_view_changed)
                return True

        elif event_type == QEvent.Type.Wheel:
            # GLViewWidget applies its zoom after event filters have run.
            QTimer.singleShot(0, self.on_view_changed)
        elif event_type == QEvent.Type.Resize:
            QTimer.singleShot(0, self.on_view_changed)

        return False


class MainWindow(QMainWindow):
    """Main application window for editing, validating, plotting, and exporting G-code."""

    def __init__(self):
        """Initialize UI, load persisted preferences, and prepare plotting state."""
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._plot_navigation = PlotNavigation(self.ui.graphicsView, self._update_adaptive_grid, self._pick_trace_at)
        self.ui.graphicsView.installEventFilter(self._plot_navigation)

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
        self.settings.setValue("FILE/RECENT_FILES", self.recentFiles)

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
        self._setup_recent_files_menu()
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
        """Zoom in on the plot."""
        dist = self.ui.graphicsView.opts["distance"]
        self.ui.graphicsView.setCameraPosition(distance=dist * 0.9)
        self._update_adaptive_grid()

    def zoomOut(self):
        """Zoom out on the plot."""
        dist = self.ui.graphicsView.opts["distance"]
        self.ui.graphicsView.setCameraPosition(distance=dist * 1.1)
        self._update_adaptive_grid()

    def timerEvent(self, event):
        """Advance playback by logical CNC motion, not editor line."""
        del event
        maximum = self.ui.horizontalSlider.maximum()
        value = self.ui.horizontalSlider.value()
        if maximum <= 0 or value >= maximum:
            self.stop()
            return
        self.ui.horizontalSlider.setValue(value + 1)

    def backward(self):
        """Move one logical motion backward."""
        value = self.ui.horizontalSlider.value()
        self.ui.horizontalSlider.setValue(max(self.ui.horizontalSlider.minimum(), value - 1))

    def forward(self):
        """Move one logical motion forward."""
        value = self.ui.horizontalSlider.value()
        self.ui.horizontalSlider.setValue(min(self.ui.horizontalSlider.maximum(), value + 1))

    def play(self):
        """Start or pause playback of toolpath highlighting."""
        if self.ui.actionPlay.isChecked():
            self.timer.start(self.speedTimer, self)
        else:
            self.timer.stop()

    def stop(self):
        """Stop logical-motion playback and return to the first motion."""
        self.ui.actionPlay.setChecked(False)
        self.timer.stop()
        self.step = 0
        if self.ui.horizontalSlider.maximum() >= 1:
            self.ui.horizontalSlider.setValue(1)

    def sliderDrag(self):
        """Synchronize editor cursor with the selected logical motion."""
        if self.ui.actionPlay.isChecked():
            self.timer.stop()
            self.ui.actionPlay.setChecked(False)
        self._sync_editor_to_motion(self.ui.horizontalSlider.value() - 1)

    def gridChecked(self):
        """Toggle plot grid visibility and refresh the view."""
        self.plotGrid = self.ui.actionGrid.isChecked()
        self.loadPlot()
        self._create_trace_items()
        if self.execution_result is not None and self.execution_result.motions:
            self.valueHandler(self.ui.horizontalSlider.value())

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

    def _setup_recent_files_menu(self):
        """Create the File -> Recent Files menu without changing the generated UI."""
        self.recentFilesMenu = QMenu("Recent Files", self.ui.menu_File)
        separator = next((action for action in self.ui.menu_File.actions() if action.isSeparator()), None)
        if separator is None:
            self.ui.menu_File.addMenu(self.recentFilesMenu)
        else:
            self.ui.menu_File.insertMenu(separator, self.recentFilesMenu)
        self._update_recent_files_menu()

    def _update_recent_files_menu(self):
        self.recentFilesMenu.clear()
        self.recentFiles = _normalized_recent_files(self.recentFiles)
        if not self.recentFiles:
            action = self.recentFilesMenu.addAction("(Empty)")
            action.setEnabled(False)
            return
        for index, path in enumerate(self.recentFiles, start=1):
            action = self.recentFilesMenu.addAction(f"{index}. {path}")
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_file(p))
        self.recentFilesMenu.addSeparator()
        self.recentFilesMenu.addAction("Clear Recent", self._clear_recent_files)

    def _persist_recent_files(self):
        self.settings.setValue("FILE/RECENT_FILES", self.recentFiles)
        self.settings.sync()

    def _add_recent_file(self, path):
        absolute = QFileInfo(str(path)).absoluteFilePath()
        self.recentFiles = _normalized_recent_files([absolute, *self.recentFiles])
        self._update_recent_files_menu()
        self._persist_recent_files()

    def _remove_recent_file(self, path):
        key = str(path).casefold()
        self.recentFiles = [item for item in self.recentFiles if item.casefold() != key]
        self._update_recent_files_menu()
        self._persist_recent_files()

    def _clear_recent_files(self):
        self.recentFiles = []
        self._update_recent_files_menu()
        self._persist_recent_files()

    def _open_recent_file(self, path):
        if not QFileInfo(path).exists():
            QMessageBox.warning(self, "Easy G-code Plot", f"File not found:\n{path}")
            self._remove_recent_file(path)
            return
        if self.maybeSave():
            self.loadFile(path)

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
        self._add_recent_file(fileName)

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
        self._add_recent_file(fileName)
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
            self._view_mode = "lathe"
            self.ui.action3D.setEnabled(False)
            self.ui.actionTop.setEnabled(False)
            self.ui.actionFront.setEnabled(False)
            self.ui.actionLeft.setEnabled(False)
            self.ui.actionGrid.setEnabled(True)
            self.updateData()
            self.ui.graphicsView.opts["fov"] = 0.01
            self.ui.graphicsView.opts["rotationMethod"] = "quaternion"
            self.ui.graphicsView.setCameraPosition(distance=self.dist * 6000, rotation=QQuaternion(0.5, 0.5, 0.5, 0.5))
            self._update_adaptive_grid()
        else:
            self.latheMode = False
            self._view_mode = "3d"
            self.ui.action3D.setEnabled(True)
            self.ui.actionTop.setEnabled(True)
            self.ui.actionFront.setEnabled(True)
            self.ui.actionLeft.setEnabled(True)
            self.ui.actionGrid.setEnabled(False)
            self.ui.graphicsView.opts["rotationMethod"] = "euler"
            self.updateData()
            self.view3d()

        if hasattr(self, "exportDlg"):
            self.exportDlg.set_expanded_turn_available(self.latheMode)

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

    def _execute_editor_source(self, *, show_errors=True):
        source = self.ui.editor.text()
        language = "fanuc_turn" if self.latheMode else "fanuc_mill"
        result = execute(
            source,
            language=language,
            home_x=self.xPosMach,
            home_y=self.yPosMach,
            home_z=self.zPosMach,
            emulate_g28_home=True,
        )
        if not result.ok and show_errors:
            message = "\n".join(f"{d.code}: {d.message}" for d in result.diagnostics) or "Unable to execute G-code"
            QMessageBox.warning(self, "Easy G-code Plot", message)
        elif result.diagnostics and show_errors:
            self.ui.statusbar.showMessage("; ".join(f"{d.code}: {d.message}" for d in result.diagnostics), 10000)
        return result

    def _create_trace_items(self):
        self._rapid_item = GLLinePlotItem(pos=[], color=QColor(RAPID_COLOR), width=0.3, antialias=True, mode="lines")
        self._drawing_item = GLLinePlotItem(
            pos=[], color=QColor(self.plotLineColor), width=0.3, antialias=True, mode="lines"
        )
        self._cursor_item = GLScatterPlotItem(
            pos=[], color=QColor(self.plotLineColor), size=CURSOR_SIZE_PX, pxMode=True
        )
        self._cursor_item.setGLOptions("translucent")
        self.ui.graphicsView.addItem(self._rapid_item)
        self.ui.graphicsView.addItem(self._drawing_item)
        self.ui.graphicsView.addItem(self._cursor_item)

    def _trace_segment_vertices(self, end):
        """Split the rendered prefix into rapid and cutting line-segment vertices."""
        result = self.execution_result
        points = self.render_points[:end]
        rapid = []
        cutting = []
        if result is None or len(points) < 2:
            return rapid, cutting
        for previous, current in zip(points, points[1:]):
            motion_index = current.motion_index
            if not 0 <= motion_index < len(result.motions):
                continue
            target = rapid if result.motions[motion_index].move == 0 else cutting
            target.extend(
                [
                    (previous.x, previous.y, previous.z),
                    (current.x, current.y, current.z),
                ]
            )
        return rapid, cutting

    def _project_world_to_screen(self, x, y, z):
        """Project one world point to GLViewWidget pixel coordinates."""
        view = self.ui.graphicsView
        viewport = view.getViewport()
        try:
            projection = view.projectionMatrix(viewport, viewport)
        except TypeError:  # pyqtgraph < 0.14 compatibility
            projection = view.projectionMatrix(viewport)  # pylint: disable=no-value-for-parameter
        clip = projection * view.viewMatrix() * QVector4D(float(x), float(y), float(z), 1.0)
        w = clip.w()
        if abs(w) < 1e-12:
            return None
        ndc_x = clip.x() / w
        ndc_y = clip.y() / w
        vx, vy, vw, vh = viewport
        return (
            vx + (ndc_x + 1.0) * 0.5 * vw,
            vy + (1.0 - (ndc_y + 1.0) * 0.5) * vh,
        )

    def _pick_trace_at(self, position):
        """Select the nearest trajectory segment on Shift+Click in a 2D view."""
        view_mode = "lathe" if self.latheMode else getattr(self, "_view_mode", "3d")
        if view_mode not in {"lathe", "top", "front", "left"} or not self.render_points:
            return False

        px = float(position.x())
        py = float(position.y())
        best_distance = PICK_DISTANCE_PX
        best_motion = None
        projected_previous = self._project_world_to_screen(
            self.render_points[0].x, self.render_points[0].y, self.render_points[0].z
        )
        for current in self.render_points[1:]:
            projected_current = self._project_world_to_screen(current.x, current.y, current.z)
            if projected_previous is not None and projected_current is not None:
                distance = _point_segment_distance(
                    px, py, projected_previous[0], projected_previous[1], projected_current[0], projected_current[1]
                )
                if distance <= best_distance:
                    best_distance = distance
                    best_motion = current.motion_index
            projected_previous = projected_current

        result = self.execution_result
        if result is None or best_motion is None or not 0 <= best_motion < len(result.motions):
            return False
        self.ui.horizontalSlider.setValue(best_motion + 1)
        self._sync_editor_to_motion(best_motion)
        source_block = result.motions[best_motion].source_block
        if source_block is not None:
            self.ui.statusbar.showMessage(
                f"Trajectory source: line {source_block + 1}, motion {best_motion + 1} (Shift+Click)", 5000
            )
        return True

    def _sync_editor_to_motion(self, idx):
        result = self.execution_result
        if result is None or not 0 <= idx < len(result.motions):
            return
        block = result.motions[idx].source_block
        if block is None or block < 0 or block >= self.ui.editor.lines():
            return
        if self.ui.editor.getCursorPosition()[0] == block:
            return
        self._syncing_cursor = True
        try:
            self.ui.editor.setCursorPosition(block, 0)
        finally:
            self._syncing_cursor = False

    def _countProgramPoints(self):
        result = self.execution_result or self._execute_editor_source(show_errors=False)
        if result is None or not result.motions:
            return 0
        return len(render_trace(result, lathe_radius_view=self.latheMode, arc_type=self.arc_type))

    def autoUpdate(self):
        """Debounced refresh for programs whose sampled render path is small."""
        if self.ui.editor.lines() > AUTO_REFRESH_MAX_LINES:
            return
        result = self._execute_editor_source(show_errors=False)
        if result is None or not result.motions:
            return
        points = render_trace(result, lathe_radius_view=self.latheMode, arc_type=self.arc_type)
        if len(points) > AUTO_REFRESH_MAX_POINTS:
            return
        self._finishDataUpdate(result, points)

    def clearPlot(self):
        """Reset authoritative execution and render/playback state."""
        self.execution_result = None
        self.render_points = []
        self._motion_render_end = []
        self._source_motion_index = {}
        self._syncing_cursor = False
        self._drawing_item = None
        self._rapid_item = None
        self._cursor_item = None
        self._lathe_grid_item = None
        self._lathe_grid_center = (0.0, 0.0)
        self._milling_grid_item = None
        self._milling_grid_center = (0.0, 0.0, 0.0)
        self.timer.stop()
        self.step = 0
        for widget in (
            self.ui.lineEditX,
            self.ui.lineEditY,
            self.ui.lineEditZ,
            self.ui.lineEdit_I,
            self.ui.lineEdit_J,
            self.ui.lineEdit_K,
            self.ui.lineEditFeed,
        ):
            widget.clear()
        self.ui.horizontalSlider.setMinimum(1)
        self.ui.horizontalSlider.setMaximum(1)
        self.ui.horizontalSlider.setValue(1)
        self.ui.actionStep_Backward.setEnabled(False)
        self.ui.actionStep_Forward.setEnabled(False)
        self.ui.actionPlay.setChecked(False)
        self.ui.actionPlay.setEnabled(False)
        self.ui.actionStop.setEnabled(False)
        self.loadPlot()

    def valueHandler(self, value):
        """Display one logical motion and draw the sampled prefix efficiently."""
        result = self.execution_result
        if result is None or not result.motions:
            return
        idx = max(0, min(len(result.motions) - 1, value - 1))
        motion = result.motions[idx]
        scale_x = 0.5 if self.latheMode else 1.0
        self.ui.lineEditX.setText(str(round(motion.end_x * scale_x, 3)))
        self.ui.lineEditY.setText(str(round(motion.end_y, 3)))
        self.ui.lineEditZ.setText(str(round(motion.end_z, 3)))
        self.ui.lineEdit_I.setText("" if motion.i is None else str(round(motion.i, 3)))
        self.ui.lineEdit_J.setText("" if motion.j is None else str(round(motion.j, 3)))
        self.ui.lineEdit_K.setText("" if motion.k is None else str(round(motion.k, 3)))
        self.ui.lineEditFeed.setText("Rapid" if motion.move == 0 else ("" if motion.feed is None else str(motion.feed)))
        end = self._motion_render_end[idx] if idx < len(self._motion_render_end) else len(self.render_points)
        xyz = [(p.x, p.y, p.z) for p in self.render_points[:end]]
        if self._drawing_item is None or self._rapid_item is None or self._cursor_item is None:
            self._create_trace_items()
        rapid_xyz, cutting_xyz = self._trace_segment_vertices(end)
        self._rapid_item.setData(pos=rapid_xyz, color=QColor(RAPID_COLOR), width=0.3, antialias=True, mode="lines")
        self._drawing_item.setData(
            pos=cutting_xyz, color=QColor(self.plotLineColor), width=0.3, antialias=True, mode="lines"
        )
        if xyz:
            self._cursor_item.setData(pos=[xyz[-1]], color=QColor(self.plotLineColor), size=CURSOR_SIZE_PX, pxMode=True)
        self._sync_editor_to_motion(idx)

    def loadPlot(self):
        """Redraw axes, background, and the active orthographic grid."""
        self.ui.graphicsView.clear()
        self._drawing_item = None
        self._rapid_item = None
        self._cursor_item = None
        self._lathe_grid_item = None
        self._lathe_grid_center = (0.0, 0.0)
        self._milling_grid_item = None
        self._milling_grid_center = (0.0, 0.0, 0.0)
        self.ui.graphicsView.setBackgroundColor(self.plotBackground)
        line1 = [(0, 0, 0), (5, 0, 0)]
        line2 = [(0, 0, 0), (0, 5, 0)]
        line3 = [(0, 0, 0), (0, 0, 5)]
        axisX = GLLinePlotItem(pos=line1, color="r", width=3, antialias=True)
        axisY = GLLinePlotItem(pos=line2, color="g", width=3, antialias=True)
        axisZ = GLLinePlotItem(pos=line3, color="y", width=3, antialias=True)
        if self.plotGrid:
            if self.latheMode:
                self._lathe_grid_item = GLGridItem()
                self._lathe_grid_item.setColor(QColor(self.plotGridColor))
                self._lathe_grid_item.rotate(90, 1, 0, 0)
                self.ui.graphicsView.addItem(self._lathe_grid_item)
            elif getattr(self, "_view_mode", "3d") in {"top", "front", "left"}:
                self._milling_grid_item = GLGridItem()
                self._milling_grid_item.setColor(QColor(self.plotGridColor))
                if self._view_mode == "front":
                    self._milling_grid_item.rotate(90, 1, 0, 0)
                elif self._view_mode == "left":
                    self._milling_grid_item.rotate(90, 0, 1, 0)
                self.ui.graphicsView.addItem(self._milling_grid_item)
            self._update_adaptive_grid()

        self.ui.graphicsView.addItem(axisX)
        self.ui.graphicsView.addItem(axisY)
        self.ui.graphicsView.addItem(axisZ)

    def _adaptive_grid_size(self):
        view = self.ui.graphicsView
        return adaptive_grid_geometry(
            view.opts["distance"], view.opts["fov"], view.height(), viewport_width=view.width()
        )

    def _update_adaptive_grid(self):
        """Update the active 2D/orthographic grid after zoom, pan, or resize."""
        if self.latheMode:
            self._update_lathe_grid()
        else:
            self._update_milling_grid()

    def _update_lathe_grid(self):
        """Adapt the single XZ lathe grid to the current camera zoom."""
        grid = getattr(self, "_lathe_grid_item", None)
        if grid is None or not self.latheMode or not self.plotGrid:
            return
        spacing, size = self._adaptive_grid_size()
        grid.setSize(size, size)
        grid.setSpacing(spacing, spacing)
        center = self.ui.graphicsView.opts["center"]
        snapped_x = round(center.x() / spacing) * spacing
        snapped_z = round(center.z() / spacing) * spacing
        old_x, old_z = getattr(self, "_lathe_grid_center", (0.0, 0.0))
        grid.translate(snapped_x - old_x, 0.0, snapped_z - old_z)
        self._lathe_grid_center = (snapped_x, snapped_z)

    def _update_milling_grid(self):
        """Adapt the active milling grid in Top, Front, and Left views only."""
        grid = getattr(self, "_milling_grid_item", None)
        view_mode = getattr(self, "_view_mode", "3d")
        if grid is None or self.latheMode or not self.plotGrid or view_mode not in {"top", "front", "left"}:
            return

        spacing, size = self._adaptive_grid_size()
        grid.setSize(size, size)
        grid.setSpacing(spacing, spacing)
        center = self.ui.graphicsView.opts["center"]
        if view_mode == "top":
            snapped = (round(center.x() / spacing) * spacing, round(center.y() / spacing) * spacing, 0.0)
        elif view_mode == "front":
            snapped = (round(center.x() / spacing) * spacing, 0.0, round(center.z() / spacing) * spacing)
        else:
            snapped = (0.0, round(center.y() / spacing) * spacing, round(center.z() / spacing) * spacing)

        old = getattr(self, "_milling_grid_center", (0.0, 0.0, 0.0))
        grid.translate(snapped[0] - old[0], snapped[1] - old[1], snapped[2] - old[2])
        self._milling_grid_center = snapped

    def plotCurLine(self):
        """Map the current source line to its last logical motion."""
        if self._syncing_cursor:
            return
        line = self.ui.editor.getCursorPosition()[0]
        idx = self._source_motion_index.get(line)
        if idx is not None:
            self.ui.horizontalSlider.setValue(idx + 1)

    def list_rindex(self, li, x):
        """Return the last index of x in list li."""
        return last_index(li, x)

    def updateData(self):
        """Execute editor source through the single authoritative CNC kernel."""
        result = self._execute_editor_source(show_errors=True)
        if result is None or not result.motions:
            self.clearPlot()
            return False
        self._finishDataUpdate(result)
        return True

    def _finishDataUpdate(self, result=None, points=None):
        """Bind ``ExecutionResult`` to render, statistics and playback consumers."""
        if result is not None:
            self.execution_result = result
        result = self.execution_result
        if result is None:
            return
        self.render_points = (
            points
            if points is not None
            else render_trace(result, lathe_radius_view=self.latheMode, arc_type=self.arc_type)
        )
        self._source_motion_index = {}
        for idx, motion in enumerate(result.motions):
            if motion.source_block is not None:
                # A canned-cycle source block can expand to many motions.  An
                # editor click should select the first generated motion, while
                # playback still walks all generated motions normally.
                self._source_motion_index.setdefault(motion.source_block, idx)

        self._motion_render_end = [0] * len(result.motions)
        for point_index, point in enumerate(self.render_points, start=1):
            if 0 <= point.motion_index < len(self._motion_render_end):
                self._motion_render_end[point.motion_index] = point_index
        last = 0
        for idx, end in enumerate(self._motion_render_end):
            if end:
                last = end
            self._motion_render_end[idx] = last
        self.calcDist()
        enabled = bool(result.motions)
        self.ui.actionStep_Backward.setEnabled(enabled)
        self.ui.actionStep_Forward.setEnabled(enabled)
        self.ui.actionPlay.setEnabled(enabled)
        self.ui.actionStop.setEnabled(enabled)
        self.ui.horizontalSlider.blockSignals(True)
        self.ui.horizontalSlider.setMinimum(1)
        self.ui.horizontalSlider.setMaximum(max(1, len(result.motions)))
        self.ui.horizontalSlider.setPageStep(max(1, len(result.motions) // 10))
        self.ui.horizontalSlider.setValue(max(1, len(result.motions)))
        self.ui.horizontalSlider.blockSignals(False)
        self.loadPlot()
        self._create_trace_items()
        if result.motions:
            self.valueHandler(len(result.motions))

    def setView(self, fov, elevation, azimuth, use_calc_dist=True, dist_scale=6000):
        """Set camera view with optional distance recalculation."""
        if use_calc_dist:
            self.calcDist()
            dist = self.dist * dist_scale
        else:
            dist = self.dist
        self.ui.graphicsView.opts["fov"] = fov
        self.ui.graphicsView.setCameraPosition(distance=dist, elevation=elevation, azimuth=azimuth)
        self._update_adaptive_grid()

    def _refresh_view_plot(self):
        self.loadPlot()
        self._create_trace_items()
        if self.execution_result is not None and self.execution_result.motions:
            self.valueHandler(self.ui.horizontalSlider.value())

    def view3d(self):
        """Set 3D camera angle with grid disabled."""
        self._view_mode = "3d"
        self.ui.actionGrid.setEnabled(False)
        self.setView(60, 30, -45, use_calc_dist=False, dist_scale=1)
        self._refresh_view_plot()

    def viewTop(self):
        """Switch camera to a top-down orthographic view."""
        self._view_mode = "top"
        self.ui.actionGrid.setEnabled(True)
        self.setView(0.01, 90, -90)
        self._refresh_view_plot()

    def viewFront(self):
        """Switch camera to a front orthographic view."""
        self._view_mode = "front"
        self.ui.actionGrid.setEnabled(True)
        self.setView(0.01, 0, -90)
        self._refresh_view_plot()

    def viewLeft(self):
        """Switch camera to a left orthographic view."""
        self._view_mode = "left"
        self.ui.actionGrid.setEnabled(True)
        self.setView(0.01, 0, 180)
        self._refresh_view_plot()

    def lstExport(self):
        """Compatibility hook: export data now comes directly from ExecutionResult."""
        return list(self.execution_result.motions) if self.execution_result is not None else []

    def toolPath(self):
        """Return trace-based path length and estimated machining time."""
        if self.execution_result is None or not self.execution_result.motions:
            return ""
        stats = trace_statistics(
            self.execution_result,
            lathe_radius_view=self.latheMode,
            rapid_feed=self.rapidFeed,
            arc_type=self.arc_type,
        )
        time_min = float(stats["total_time_min"])
        time_sec = time_min * 60
        return (
            self.co
            + f"Toolpath Length: {float(stats['total_length']):.3f}"
            + self.ci
            + "\n"
            + self.co
            + "Machining Time: {h:02}:{m:02}:{s:02}".format(
                h=floor(time_min / 60), m=floor(time_min % 60), s=floor(time_sec % 60)
            )
            + self.ci
            + "\n"
        )

    def toolPathLimits(self):
        """Return min/max extents from the authoritative trace."""
        if self.execution_result is None or not self.execution_result.motions:
            return ""
        stats = trace_statistics(
            self.execution_result,
            lathe_radius_view=False,
            rapid_feed=self.rapidFeed,
            arc_type=self.arc_type,
        )
        bounds = stats["bounds"]
        if bounds is None:
            return ""
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds
        if self.latheMode:
            # Kernel turning X is diameter-space already.
            pass
        return (
            self.co
            + f"X MIN: {round(xmin, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Y MIN: {round(ymin, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Z MIN: {round(zmin, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"X MAX: {round(xmax, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Y MAX: {round(ymax, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Z MAX: {round(zmax, 3)}"
            + self.ci
        )

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
        """Calculate camera center/distance from sampled render points."""
        if not self.render_points:
            return
        xs = [p.x for p in self.render_points]
        ys = [p.y for p in self.render_points]
        zs = [p.z for p in self.render_points]
        center, self.dist = calculate_scene_geometry(xs, ys, zs)
        self.ui.graphicsView.opts["center"] = QVector3D(*center)

    def about(self):
        """Show application about dialog."""
        QMessageBox.about(
            self,
            "Easy G-code Plot",
            f"This program is free software\nDeveloper: MaestroFusion360\nVersion: {get_version()}\n2025/12/09",
        )
