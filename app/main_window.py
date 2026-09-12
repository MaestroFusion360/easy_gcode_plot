"""Main application window."""

import logging
from time import perf_counter

from PyQt6.QtCore import QBasicTimer, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QQuaternion
from PyQt6.QtWidgets import QComboBox, QMainWindow, QToolBar

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources on import.
from app.settings import RECENT_FILES_LIMIT as _RECENT_FILES_LIMIT
from app.settings import normalized_milling_tools, normalized_recent_files, normalized_tools
from app.ui.dialogs import About, BlockNum, Export, Find, MillingTools, TurningTools, Wcs
from app.ui.generated.main_ui import Ui_MainWindow
from app.ui.help import HelpDialog
from app.ui.main_window_editor_ops import MainWindowEditorMixin
from app.ui.main_window_execution import (
    AUTO_REFRESH_DELAY_MS,
    MainWindowExecutionMixin,
)
from app.ui.main_window_execution import (
    AUTO_REFRESH_MAX_POINTS as _AUTO_REFRESH_MAX_POINTS,
)
from app.ui.main_window_file_ops import MainWindowFileMixin
from app.ui.main_window_plot import (
    CURSOR_SIZE_PX as _CURSOR_SIZE_PX,
)
from app.ui.main_window_plot import (
    PICK_DISTANCE_PX as _PICK_DISTANCE_PX,
)
from app.ui.main_window_plot import (
    RAPID_COLOR as _RAPID_COLOR,
)
from app.ui.main_window_plot import (
    MainWindowPlotMixin,
)
from app.ui.main_window_stock import MainWindowStockMixin
from app.ui.options import OptionsDialog
from app.ui.plot_navigation import PlotNavigation
from app.ui.statistics import StatisticsDialog
from app.ui.stock_dialog import StockDialog
from app.ui.tokens import TokensDialog
from app.ui.window_settings import MainWindowSettingsMixin

# Backward-compatible helper names used by existing GUI tests and callers.
RECENT_FILES_LIMIT = _RECENT_FILES_LIMIT
_normalized_tools = normalized_tools
_normalized_milling_tools = normalized_milling_tools
_normalized_recent_files = normalized_recent_files
AUTO_REFRESH_MAX_POINTS = _AUTO_REFRESH_MAX_POINTS
PICK_DISTANCE_PX = _PICK_DISTANCE_PX
CURSOR_SIZE_PX = _CURSOR_SIZE_PX
RAPID_COLOR = _RAPID_COLOR
LOGGER = logging.getLogger(__name__)
TOOLBAR_ICON_SIZE = QSize(24, 24)


class MainWindow(
    MainWindowSettingsMixin,
    MainWindowFileMixin,
    MainWindowEditorMixin,
    MainWindowExecutionMixin,
    MainWindowStockMixin,
    MainWindowPlotMixin,
    QMainWindow,
):
    """Compose the main Qt window from focused UI responsibility mixins."""

    def __init__(self):
        """Initialize UI, load persisted preferences, and prepare plotting state."""
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._configure_runtime_ui()
        self._plot_navigation = PlotNavigation(self.ui.graphicsView, self._update_adaptive_grid, self._pick_trace_at)
        self.ui.graphicsView.installEventFilter(self._plot_navigation)

        icon = QIcon()
        icon.addFile(":/resource/icons/logo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.setWindowIcon(icon)

        self.loadSettings()
        self.restoreToolbarState()
        self._initialize_runtime_helpers()
        self.connectActions()
        self.createLabelStatBar()
        self.clearPlot()
        self.changeLathe()

    def _configure_runtime_ui(self):
        """Attach runtime-only widgets and action groups to the generated Designer UI."""
        for toolbar in (
            self.ui.fileToolBar,
            self.ui.editToolBar,
            self.ui.cncToolBar,
            self.ui.viewToolBar,
            self.ui.playbackToolBar,
        ):
            toolbar.setIconSize(TOOLBAR_ICON_SIZE)
        self.ui.actionStock = QAction("Stock", self)
        self.ui.actionStock.setObjectName("actionStock")
        self.ui.actionStock.setToolTip("Configure turning Stock Removal")
        self.ui.menuSettings.insertAction(self.ui.actionWCS, self.ui.actionStock)

        self.ui.actionGroupArcType = QActionGroup(self)
        self.ui.actionGroupArcType.setExclusive(True)
        for action in (
            self.ui.actionRelative_to_start,
            self.ui.actionAbsolute,
            self.ui.actionRadius_value,
        ):
            self.ui.actionGroupArcType.addAction(action)

        self.ui.fileTypeCombo = QComboBox(self)
        self.ui.fileTypeCombo.setObjectName("fileTypeCombo")
        self.ui.fileTypeCombo.addItems(["Text File", "ISO G-Code"])
        self.ui.fileTypeCombo.setToolTip("File Type")
        actions = self.ui.cncToolBar.actions()
        if actions:
            first_action = actions[0]
            self.ui.cncToolBar.insertWidget(first_action, self.ui.fileTypeCombo)
            self.ui.cncToolBar.insertSeparator(first_action)
        else:
            self.ui.cncToolBar.addWidget(self.ui.fileTypeCombo)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def _toolbars(self):
        """Return toolbars in their canonical default order."""
        return (
            self.ui.fileToolBar,
            self.ui.editToolBar,
            self.ui.cncToolBar,
            self.ui.viewToolBar,
            self.ui.playbackToolBar,
        )

    def resetToolbarsToDefault(self):
        """Restore all toolbars to one visible row in canonical order."""
        for toolbar in self._toolbars():
            self.removeToolBar(toolbar)
        for toolbar in self._toolbars():
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
            toolbar.show()
        self.settings.remove("GEOMETRY/TOOLBAR_STATE")

    def contextMenuEvent(self, event):
        """Offer toolbar visibility controls and a default-layout reset."""
        widget = self.childAt(event.pos())
        while widget is not None and not isinstance(widget, QToolBar):
            widget = widget.parentWidget()
        if widget is None:
            return super().contextMenuEvent(event)
        menu = self.createPopupMenu()
        menu.addSeparator()
        reset_action = menu.addAction("Reset to Default")
        reset_action.triggered.connect(self.resetToolbarsToDefault)
        menu.exec(event.globalPos())
        event.accept()

    def _initialize_runtime_helpers(self):
        """Create dialogs and timers after persisted settings are loaded."""
        self.aboutDlg = About(self)
        self.helpDlg = HelpDialog(self)
        self.exportDlg = Export(self)
        self.findDlg = Find(self)
        self.blockNumDlg = BlockNum(self)
        self.wcsDlg = Wcs(self)
        self.turningToolsDlg = TurningTools(self)
        self.millingToolsDlg = MillingTools(self)
        self.optionsDlg = OptionsDialog(self)
        self.tokensDlg = TokensDialog(self)
        self.statisticsDlg = StatisticsDialog(self)
        self.stockDlg = StockDialog(self)
        self.timer = QBasicTimer()
        self.autoUpdateTimer = QTimer(self)
        self.autoUpdateTimer.setSingleShot(True)
        self.autoUpdateTimer.setInterval(AUTO_REFRESH_DELAY_MS)
        self.autoUpdateTimer.timeout.connect(self.autoUpdate)

    def closeEvent(self, event):
        """Prompt to save and persist settings before closing the window."""
        if getattr(self, "_kernel_execution_active", False):
            self._kernel_cancel_requested = True
            self.ui.statusbar.showMessage("Cancelling CNC execution; close again when it has stopped.")
            event.ignore()
            return
        if self.maybeSave():
            self.saveSettings()
            self._dispose_trace_item()
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
        self.ui.actionImportSTL.triggered.connect(self.importStl)
        self.ui.actionClearSTL.triggered.connect(self.clearStl)
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
        self.ui.actionStock.triggered.connect(self.stockDlg.show)
        self.ui.actionWCS.triggered.connect(lambda: self.wcsDlg.show())
        self.ui.actionTurningTools.triggered.connect(lambda: self.turningToolsDlg.show())
        self.ui.actionMillingTools.triggered.connect(lambda: self.millingToolsDlg.show())
        self.ui.actionOptions.triggered.connect(self.optionsDlg.show)
        self.ui.actionTokens.triggered.connect(self.tokensDlg.show)

        self.ui.actionRefresh.triggered.connect(self.updateData)
        self.ui.actionZoom_In.triggered.connect(self.zoomIn)
        self.ui.actionZoom_Out.triggered.connect(self.zoomOut)
        self.ui.actionFitToView.triggered.connect(self.fitToView)
        self.ui.action3D.triggered.connect(self.view3d)
        self.ui.actionTop.triggered.connect(self.viewTop)
        self.ui.actionFront.triggered.connect(self.viewFront)
        self.ui.actionLeft.triggered.connect(self.viewLeft)
        self.ui.actionGrid.toggled.connect(self.gridChecked)
        self.ui.graphicsView.orthographicOrbitStarted.connect(self._orthographic_orbit_started)

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
        self.ui.horizontalSlider.valueChanged.connect(self.updatePlaybackStatus)
        self.ui.actionAbout.triggered.connect(self.aboutDlg.show)
        self.ui.actionFAQ.triggered.connect(self.helpDlg.show)

        self.ui.fileTypeCombo.currentIndexChanged.connect(self.changeFileType)

    def syncGuiCapabilities(self):
        """Synchronize machine-specific actions with the active execution profile."""
        turning = bool(self.latheMode)
        self.ui.actionStock.setEnabled(turning)
        self.ui.actionTurningTools.setEnabled(turning)
        self.ui.actionMillingTools.setEnabled(not turning)

        # Fanuc turning always interprets I/K relative to the arc start.  Keep
        # the configurable Arc Type visible only where it is actually used.
        self.ui.menuArc_Type.setEnabled(not turning)
        self.ui.actionRelative_to_start.setEnabled(not turning)
        self.ui.actionAbsolute.setEnabled(not turning)
        self.ui.actionRadius_value.setEnabled(not turning)
        if hasattr(self, "optionsDlg"):
            self.optionsDlg.ui.arcToleranceSpin.setEnabled(True)

    def changeArcType(self):
        """Change arc mode between relative, absolute, or radius modes."""
        if self.ui.actionRelative_to_start.isChecked():
            self.arc_type = 1
        if self.ui.actionAbsolute.isChecked():
            self.arc_type = 2
        if self.ui.actionRadius_value.isChecked():
            self.arc_type = 3
        LOGGER.info("arc_type_changed value=%d lathe=%s", self.arc_type, self.latheMode)
        self.updateData()

    def changeLathe(self):
        """Toggle lathe visualization mode and refresh plot accordingly."""
        started = perf_counter()
        if getattr(self, "_stock_animation_active", False):
            self.ui.actionPlay.setChecked(False)
            self.timer.stop()
            self._leave_stock_animation()
        if self.ui.actionLatheMode.isChecked():
            self.latheMode = True
            self._view_mode = "lathe"
            self.ui.graphicsView.setProjectionMode("perspective")
            self.ui.action3D.setEnabled(False)
            self.ui.actionTop.setEnabled(False)
            self.ui.actionFront.setEnabled(False)
            self.ui.actionLeft.setEnabled(False)
            self.ui.actionGrid.setEnabled(True)
            self.updateData(show_errors=False)
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
            self.updateData(show_errors=False)
            self.view3d()

        self.syncGuiCapabilities()
        if hasattr(self, "wcsDlg"):
            self.wcsDlg.loadValues()
        if hasattr(self, "exportDlg"):
            self.exportDlg.sync_mode_availability(self.latheMode)
        LOGGER.info(
            "machine_mode_changed mode=%s duration_ms=%.3f motions=%d",
            "lathe" if self.latheMode else "mill",
            (perf_counter() - started) * 1000.0,
            0 if self.execution_result is None else len(self.execution_result.motions),
        )

    def showStockChecked(self, checked):
        """Show or hide the passive turning-stock outline immediately."""
        self.showStock = bool(checked)
        LOGGER.info("show_stock_changed enabled=%s lathe=%s", self.showStock, self.latheMode)
        if hasattr(self, "_update_stock_outline"):
            self._update_stock_outline()
