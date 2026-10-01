"""Main application window."""

import logging
from time import perf_counter

from PyQt6.QtCore import QBasicTimer, QCoreApplication, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QIcon,
    QKeySequence,
    QPageLayout,
    QPainter,
    QPixmap,
    QQuaternion,
    QShortcut,
)
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt6.QtWidgets import QComboBox, QMainWindow, QMenu, QMessageBox, QSlider, QToolBar, QToolButton

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources on import.
from app.gcode.kernel.milling.kinematics import load_catalog
from app.settings import (
    DEFAULT_TOOLBAR_ICON_SIZE,
    normalized_milling_tools,
    normalized_recent_files,
    normalized_tools,
)
from app.settings import RECENT_FILES_LIMIT as _RECENT_FILES_LIMIT
from app.ui.dialogs.calculators import HoleCalculatorDialog, PocketCalculatorDialog
from app.ui.dialogs.general import About, BlockNum, Export, Find, Wcs
from app.ui.dialogs.help import HelpDialog
from app.ui.dialogs.options import OptionsDialog
from app.ui.dialogs.snippets import SnippetsDialog
from app.ui.dialogs.statistics import StatisticsDialog
from app.ui.dialogs.stock_dialog import StockDialog
from app.ui.dialogs.tokens import TokensDialog
from app.ui.dialogs.tool_library_dialog import ToolLibraryDialog
from app.ui.generated.main.main_ui import Ui_MainWindow
from app.ui.plot.plot_navigation import PlotNavigation
from app.ui.windows.main_window_editor_ops import MainWindowEditorMixin
from app.ui.windows.main_window_execution import (
    AUTO_REFRESH_DELAY_MS,
    MainWindowExecutionMixin,
)
from app.ui.windows.main_window_execution import (
    AUTO_REFRESH_MAX_POINTS as _AUTO_REFRESH_MAX_POINTS,
)
from app.ui.windows.main_window_file_ops import MainWindowFileMixin
from app.ui.windows.main_window_plot import (
    CURSOR_SIZE_PX as _CURSOR_SIZE_PX,
)
from app.ui.windows.main_window_plot import (
    PICK_DISTANCE_PX as _PICK_DISTANCE_PX,
)
from app.ui.windows.main_window_plot import (
    RAPID_COLOR as _RAPID_COLOR,
)
from app.ui.windows.main_window_plot import (
    MainWindowPlotMixin,
)
from app.ui.windows.main_window_stock import MainWindowStockMixin
from app.ui.windows.plot_printing import paint_plot_page, project_toolpath
from app.ui.windows.window_settings import MainWindowSettingsMixin

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
        self._configure_playback_speed_slider()
        self._plot_navigation = PlotNavigation(self.ui.graphicsView, self._plot_camera_changed, self._pick_trace_at)
        self.ui.graphicsView.installEventFilter(self._plot_navigation)

        icon = QIcon()
        icon.addFile(":/resource/icons/logo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.setWindowIcon(icon)

        self.loadSettings()
        self._configure_document_watcher()
        self._configure_rotary_kinematics_menu()
        self.restoreToolbarState()
        self._initialize_runtime_helpers()
        self.connectActions()
        self.createLabelStatBar()
        self.clearPlot()
        self.changeLathe()

    def _configure_rotary_kinematics_menu(self):
        """Expose indexed milling kinematics at the top of the Settings menu."""
        catalog = load_catalog(ignore_user_errors=True)
        saved = self.settings.value("CNC/ROTARY_KINEMATICS", "", type=str)
        self.rotaryKinematics = saved if saved in catalog and catalog[saved].enabled else None

        menu = QMenu(QCoreApplication.translate("MainWindow", "Rotary kinematics"), self.ui.menuSettings)
        menu.setObjectName("menuRotaryKinematics")
        menu.setIcon(QIcon(":/resource/icons/cnc.png"))
        first_action = self.ui.menuSettings.actions()[0] if self.ui.menuSettings.actions() else None
        if first_action is None:
            self.ui.menuSettings.addMenu(menu)
            self.ui.menuSettings.addSeparator()
        else:
            self.ui.menuSettings.insertMenu(first_action, menu)
            self.ui.menuSettings.insertSeparator(first_action)

        self._rotary_kinematics_menu = menu
        self._refresh_rotary_kinematics_menu(catalog)

    def _refresh_rotary_kinematics_menu(self, catalog=None):
        catalog = catalog or load_catalog(ignore_user_errors=True)
        menu = self._rotary_kinematics_menu
        menu.clear()
        previous_group = getattr(self, "_rotary_kinematics_group", None)
        if previous_group is not None:
            previous_group.deleteLater()
        if self.rotaryKinematics is not None and (
            self.rotaryKinematics not in catalog or not catalog[self.rotaryKinematics].enabled
        ):
            self.rotaryKinematics = None
            self.settings.setValue("CNC/ROTARY_KINEMATICS", "")
        group = QActionGroup(self)
        group.setExclusive(True)
        actions = {}
        for profile_id, profile in (
            (None, None),
            *sorted(
                ((key, value) for key, value in catalog.items() if value.enabled), key=lambda item: item[0].casefold()
            ),
        ):
            text = (
                QCoreApplication.translate("MainWindow", "None")
                if profile_id is None
                else f"{profile.name} [{profile_id}]"
            )
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(profile_id == self.rotaryKinematics)
            group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, selected=profile_id: self._select_rotary_kinematics(selected)
            )
            actions[profile_id] = action

        self._rotary_kinematics_group = group
        self._rotary_kinematics_actions = actions

    def _select_rotary_kinematics(self, profile_id, *, force_refresh=False):
        catalog = load_catalog(ignore_user_errors=True)
        if profile_id is not None and (profile_id not in catalog or not catalog[profile_id].enabled):
            profile_id = None
        changed = profile_id != getattr(self, "rotaryKinematics", None)
        self.rotaryKinematics = profile_id
        self.settings.setValue("CNC/ROTARY_KINEMATICS", profile_id or "")

        action = getattr(self, "_rotary_kinematics_actions", {}).get(profile_id)
        if action is not None and not action.isChecked():
            action.setChecked(True)
        options = getattr(self, "optionsDlg", None)
        if options is not None:
            options.sync_rotary_kinematics(profile_id)

        if not (changed or force_refresh):
            return
        view_mode = getattr(self, "_view_mode", "3d")
        self._deferred_execution_result = None
        self._deferred_execution_source = None
        if self.ui.editor.text():
            self.updateData()
        # Reapply after updateData: it redraws the scene and can restore a
        # previous camera state, including a quaternion left by table B.
        if not getattr(self, "latheMode", False):
            if view_mode == "top":
                self.viewTop()
            elif view_mode == "front":
                self.viewFront()
            elif view_mode == "left":
                self.viewLeft()
            else:
                self.view3d()

    def _configure_runtime_ui(self):
        """Attach runtime-only widgets and action groups to the generated Designer UI."""
        self._configure_wcs_icon()
        self.ui.actionStock = QAction(
            QIcon(":/resource/icons/stock.png"), QCoreApplication.translate("MainWindow", "Stock"), self
        )
        self.ui.actionStock.setObjectName("actionStock")
        self.ui.actionStock.setToolTip(QCoreApplication.translate("MainWindow", "Configure turning Stock Removal"))
        self.ui.menuSettings.insertAction(self.ui.actionWCS, self.ui.actionStock)
        self.ui.menuCNC_Functions.addSeparator()
        self.ui.cncToolBar.addSeparator()
        self.viewActionGroup = QActionGroup(self)
        self.viewActionGroup.setExclusive(True)
        for action in (self.ui.action3D, self.ui.actionTop, self.ui.actionFront, self.ui.actionLeft):
            action.setCheckable(True)
            self.viewActionGroup.addAction(action)
        self.ui.action3D.setChecked(True)
        for name, text, icon_path in (
            (
                "actionHoleCalculator",
                QCoreApplication.translate("MainWindow", "Hole Calculator"),
                ":/resource/icons/holeCalc.png",
            ),
            (
                "actionPocketCalculator",
                QCoreApplication.translate("MainWindow", "Pocket Calculator"),
                ":/resource/icons/spiral.png",
            ),
            (
                "actionSnippets",
                QCoreApplication.translate("MainWindow", "Snippets"),
                ":/resource/icons/snippets.png",
            ),
        ):
            action = QAction(QIcon(icon_path), text, self)
            action.setObjectName(name)
            setattr(self.ui, name, action)
            self.ui.menuCNC_Functions.addAction(action)
            self.ui.cncToolBar.addAction(action)

        self.ui.actionGroupArcType = QActionGroup(self)
        self.ui.actionGroupArcType.setExclusive(True)
        for action in (
            self.ui.actionRelative_to_start,
            self.ui.actionAbsolute,
            self.ui.actionRadius_value,
        ):
            self.ui.actionGroupArcType.addAction(action)

        self._configure_file_type_button()
        self._configure_stl_panel()

        self._toolbar_action_icons = {
            action: action.icon()
            for toolbar in self._toolbars()
            for action in toolbar.actions()
            if not action.icon().isNull()
        }
        self.applyToolbarIconSize(DEFAULT_TOOLBAR_ICON_SIZE)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def _configure_file_type_button(self):
        """Create the CNC toolbar's source-type chooser."""
        self.ui.fileTypeCombo = QComboBox(self)
        self.ui.fileTypeCombo.setObjectName("fileTypeCombo")
        self.ui.fileTypeCombo.addItems(
            [
                QCoreApplication.translate("MainWindow", "Text File"),
                QCoreApplication.translate("MainWindow", "ISO G-Code"),
            ]
        )
        self.ui.fileTypeCombo.hide()
        self.ui.fileTypeMenu = QMenu(self)
        self.ui.fileTypeMenu.setObjectName("fileTypeMenu")
        self._file_type_icons = (
            QIcon(":/resource/icons/text.png"),
            QIcon(":/resource/icons/text-color.png"),
        )
        self._file_type_action_group = QActionGroup(self)
        self._file_type_action_group.setExclusive(True)
        self._file_type_actions = []
        for index in range(self.ui.fileTypeCombo.count()):
            action = self.ui.fileTypeMenu.addAction(self.ui.fileTypeCombo.itemText(index))
            action.setIcon(self._file_type_icons[index])
            action.setCheckable(True)
            self._file_type_action_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, selected=index: self.ui.fileTypeCombo.setCurrentIndex(selected)
            )
            self._file_type_actions.append(action)
        self.ui.fileTypeButton = QToolButton(self.ui.cncToolBar)
        self.ui.fileTypeButton.setObjectName("fileTypeButton")
        self.ui.fileTypeButton.setMenu(self.ui.fileTypeMenu)
        self.ui.fileTypeButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.ui.fileTypeButton.setIcon(self._file_type_icons[0])
        self.ui.fileTypeButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.ui.fileTypeButton.setAutoRaise(True)
        self.ui.fileTypeButton.setToolTip(QCoreApplication.translate("MainWindow", "File Type"))
        self.syncFileTypeMenu(self.ui.fileTypeCombo.currentIndex())
        actions = self.ui.cncToolBar.actions()
        if actions:
            first_action = actions[0]
            self.ui.cncToolBar.insertWidget(first_action, self.ui.fileTypeButton)
            self.ui.cncToolBar.insertSeparator(first_action)
        else:
            self.ui.cncToolBar.addWidget(self.ui.fileTypeButton)

    def _configure_wcs_icon(self):
        """Tint the existing WCS glyph for visibility in both themes."""
        wcs_pixmap = QPixmap(":/resource/icons/wcs.png")
        if not wcs_pixmap.isNull():
            painter = QPainter(wcs_pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(wcs_pixmap.rect(), QColor("#2f77c7"))
            painter.end()
            self.ui.actionWCS.setIcon(QIcon(wcs_pixmap))

    def _configure_playback_speed_slider(self):
        self.ui.playbackSpeedSlider = QSlider(Qt.Orientation.Horizontal, self.ui.playbackToolBar)
        self.ui.playbackSpeedSlider.setObjectName("playbackSpeedSlider")
        self.ui.playbackSpeedSlider.setRange(1, 5)
        self.ui.playbackSpeedSlider.setSingleStep(1)
        self.ui.playbackSpeedSlider.setPageStep(1)
        self.ui.playbackSpeedSlider.setTickInterval(1)
        self.ui.playbackSpeedSlider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.ui.playbackSpeedSlider.setFixedWidth(120)
        self.ui.playbackSpeedSlider.setToolTip(QCoreApplication.translate("OptionsDlg", "Playback speed"))
        self.ui.playbackToolBar.addWidget(self.ui.playbackSpeedSlider)

    def syncFileTypeMenu(self, index: int):
        selected = 1 if index == 1 else 0
        for action_index, action in enumerate(self._file_type_actions):
            action.setChecked(action_index == selected)
        label = self.ui.fileTypeCombo.itemText(selected)
        self.ui.fileTypeMenu.setTitle(label)
        self.ui.fileTypeButton.setText(label)
        self.ui.fileTypeButton.setIcon(self._file_type_icons[selected])

    def applyToolbarIconSize(self, dimension: int):
        """Use one icon size for every toolbar, including small source images."""
        size = QSize(dimension, dimension)
        for toolbar in self._toolbars():
            toolbar.setIconSize(size)
        for action, original in self._toolbar_action_icons.items():
            pixmap = original.pixmap(size)
            if pixmap.size() != size:
                pixmap = pixmap.scaled(
                    size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            action.setIcon(QIcon(pixmap))

    def _toolbars(self):
        """Return toolbars in their canonical default order."""
        return (
            self.ui.fileToolBar,
            self.ui.editToolBar,
            self.ui.viewToolBar,
            self.ui.cncToolBar,
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
        self._initialize_tool_dialogs()
        self.optionsDlg = OptionsDialog(self)
        self.tokensDlg = TokensDialog(self)
        self.statisticsDlg = StatisticsDialog(self)
        self.stockDlg = StockDialog(self)
        self.holeCalculatorDlg = HoleCalculatorDialog(self)
        self.pocketCalculatorDlg = PocketCalculatorDialog(self)
        self.snippetsDlg = SnippetsDialog(self)
        getattr(self.ui, "actionHoleCalculator").triggered.connect(self.holeCalculatorDlg.show)
        getattr(self.ui, "actionPocketCalculator").triggered.connect(self.pocketCalculatorDlg.show)
        getattr(self.ui, "actionSnippets").triggered.connect(self.snippetsDlg.show)
        self.timer = QBasicTimer()
        self.ui.playbackSpeedSlider.valueChanged.connect(self.setPlaybackSpeed)
        self.autoUpdateTimer = QTimer(self)
        self.autoUpdateTimer.setSingleShot(True)
        self.autoUpdateTimer.setInterval(AUTO_REFRESH_DELAY_MS)
        self.autoUpdateTimer.timeout.connect(self.autoUpdate)

    def _initialize_tool_dialogs(self):
        self.toolLibraryDlg = ToolLibraryDialog(self)
        self.ui.actionToolLibrary.triggered.connect(self.toolLibraryDlg.show)
        if self._tool_library_load_error:
            self.ui.actionToolLibrary.setEnabled(False)
            self.ui.actionToolLibrary.setToolTip(
                QCoreApplication.translate(
                    "MainWindow", "Tool Library is unavailable because tools.db could not be read"
                )
            )
            QTimer.singleShot(0, self._show_tool_library_load_error)

    def _show_tool_library_load_error(self):
        QMessageBox.critical(
            self, QCoreApplication.translate("MainWindow", "Tool Library"), self._tool_library_load_error
        )

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_document_disk_check()

    def closeEvent(self, event):
        """Prompt to save and persist settings before closing the window."""
        if getattr(self, "_kernel_execution_active", False):
            self._kernel_cancel_requested = True
            self.ui.statusbar.showMessage(
                QCoreApplication.translate("MainWindow", "Cancelling CNC execution; close again when it has stopped.")
            )
            event.ignore()
            return
        if self.maybeSave():
            self.saveSettings()
            self._dispose_trace_item()
            event.accept()
        else:
            event.ignore()

    def _connect_editor_actions(self):
        self.ui.actionUndo.triggered.connect(lambda: self.ui.editor.undo())
        self.ui.actionRedo.triggered.connect(lambda: self.ui.editor.redo())
        self.ui.actionCut.triggered.connect(lambda: self.ui.editor.cut())
        self.ui.actionCopy.triggered.connect(lambda: self.ui.editor.copy())
        self.ui.actionPaste.triggered.connect(lambda: self.ui.editor.paste())
        self.ui.actionSelectAll.triggered.connect(lambda: self.ui.editor.selectAll())
        self.ui.actionUppercase.triggered.connect(self.uppercaseSelection)
        self.ui.actionLowercase.triggered.connect(self.lowercaseSelection)
        self.blockSkipShortcut = QShortcut(QKeySequence("Ctrl+/"), self.ui.editor)
        self.blockSkipShortcut.activated.connect(self.addBlockSkip)
        self.ui.editor.blockSkipRequested.connect(self.addBlockSkip)
        self.removeBlockSkipShortcut = QShortcut(QKeySequence("Ctrl+Shift+/"), self.ui.editor)
        self.removeBlockSkipShortcut.activated.connect(self.removeBlockSkip)
        self.ui.editor.removeBlockSkipRequested.connect(self.removeBlockSkip)
        self.ui.actionFindReplace.triggered.connect(self.runFindDlg)
        self.ui.actionCopy.setEnabled(False)
        self.ui.actionCut.setEnabled(False)
        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)
        self.ui.editor.copyAvailable.connect(self.ui.actionCopy.setEnabled)
        self.ui.editor.copyAvailable.connect(self.ui.actionCut.setEnabled)

    def connectActions(self):
        """Connect UI actions, menu items, and widgets to their handlers."""
        self.ui.actionNew.triggered.connect(self.newFile)
        self.ui.actionOpen.triggered.connect(self.openFile)
        self._setup_recent_files_menu()
        self._setup_recent_stl_menu()
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSaveAs.triggered.connect(self.saveAs)
        self.ui.actionExportData.triggered.connect(lambda: self.exportDlg.show())
        self.ui.actionImportSTL.triggered.connect(self.importStl)
        self.ui.actionClearSTL.triggered.connect(self.clearStl)
        self.ui.actionExit.triggered.connect(self.close)
        self.ui.actionPrint.triggered.connect(self.printPlot)
        self._connect_editor_actions()

        self.ui.actionRenumber.triggered.connect(lambda: self.blockNumDlg.show())
        self.ui.actionNumbRemove.triggered.connect(self.numbRemove)
        self.ui.actionRemoveSpaces.triggered.connect(self.removeSpaces)
        self.ui.actionRemoveEmptyLines.triggered.connect(self.removeLines)
        self.ui.actionStatistics.triggered.connect(self.statistics)
        self.ui.actionExportToolList.triggered.connect(self.exportToolList)
        self.ui.actionPrevToolchange.triggered.connect(self.previousToolchange)
        self.ui.actionNextToolchange.triggered.connect(self.nextToolchange)
        self.ui.actionStock.triggered.connect(self.stockDlg.show)
        self.ui.actionWCS.triggered.connect(lambda: self.wcsDlg.show())
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
        self.ui.actionSave.setEnabled(self.ui.editor.isModified())
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
        self.ui.horizontalSlider.valueChanged.connect(self._macro_playback_position_changed)
        self.ui.actionAbout.triggered.connect(self.aboutDlg.show)
        self.ui.actionFAQ.triggered.connect(self.helpDlg.show)

        self.ui.fileTypeCombo.currentIndexChanged.connect(self.changeFileType)

    def syncGuiCapabilities(self):
        """Synchronize machine-specific actions with the active execution profile."""
        turning = bool(self.latheMode)
        self.ui.actionStock.setEnabled(turning)
        self.ui.actionToolLibrary.setEnabled(not self._tool_library_load_error)
        milling_assistants_enabled = not turning
        getattr(self.ui, "actionHoleCalculator").setEnabled(milling_assistants_enabled)
        getattr(self.ui, "actionPocketCalculator").setEnabled(milling_assistants_enabled)
        if hasattr(self, "holeCalculatorDlg"):
            self.holeCalculatorDlg.set_insertion_enabled(milling_assistants_enabled)
            self.pocketCalculatorDlg.set_insertion_enabled(milling_assistants_enabled)
            if turning:
                self.holeCalculatorDlg.hide()
                self.pocketCalculatorDlg.hide()

        self.ui.menuArc_Type.setEnabled(True)
        self.ui.actionRelative_to_start.setEnabled(True)
        self.ui.actionAbsolute.setEnabled(True)
        self.ui.actionRadius_value.setEnabled(True)
        if hasattr(self, "optionsDlg"):
            self.optionsDlg.ui.arcToleranceSpin.setEnabled(True)

    def printPlot(self):
        """Preview the complete toolpath in the current camera orientation."""
        view = self.ui.graphicsView
        item = getattr(self, "_toolpath_item", None)
        if item is None or not item.segments:
            QMessageBox.warning(self, "Print", "There is no toolpath to print.")
            return
        segments = project_toolpath(
            item.source_segments, view.viewMatrix(), show_rapid=getattr(self, "plotShowRapid", True)
        )
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Print plot")
        preview.paintRequested.connect(
            lambda target: paint_plot_page(
                target,
                segments,
                dashed_rapid=getattr(self, "plotDashedRapid", True),
                color_by_tool=getattr(self, "plotColorByTool", False),
            )
        )
        preview.exec()

    def changeArcType(self):
        """Change arc mode between relative, absolute, or radius modes."""
        self._document_arc_type = None
        if self.ui.actionRelative_to_start.isChecked():
            self.arc_type = 1
        if self.ui.actionAbsolute.isChecked():
            self.arc_type = 2
        if self.ui.actionRadius_value.isChecked():
            self.arc_type = 3
        # Auto detection chooses the initial interpretation. An explicit menu
        # selection wins for the current document without changing the setting.
        self._manual_arc_type_override = True
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
            self.ui.graphicsView.setPerspectiveZoomMode("distance")
            self.ui.action3D.setEnabled(False)
            self.ui.actionTop.setEnabled(False)
            self.ui.actionFront.setEnabled(False)
            self.ui.actionLeft.setEnabled(False)
            self.ui.actionGrid.setEnabled(True)
            self.updateData(show_errors=False)
            self.ui.graphicsView.opts["fov"] = 0.01
            self.ui.graphicsView.opts["rotationMethod"] = "quaternion"
            self.ui.graphicsView.setCameraPosition(distance=self.dist * 6000, rotation=QQuaternion(0.5, 0.5, 0.5, 0.5))
            # Returning from milling leaves the camera fitted to the milling scene.
            # Fit again after the lathe scene (including passive/auto Stock) has
            # been rebuilt, even when the editor is empty.
            self.fitToView()
        else:
            self.latheMode = False
            self._view_mode = "3d"
            self.ui.graphicsView.setPerspectiveZoomMode("fov")
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
