"""Lightweight multi-document coordinator for the single visible QScintilla editor.

The window's existing command and plot consumers always operate on the active
file.  Inactive documents retain their QScintilla undo buffer and last resolved
trace; no independent parser or second editor is introduced.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.Qsci import QsciDocument
from PyQt6.QtCore import QCoreApplication, QPoint, QSignalBlocker, Qt
from PyQt6.QtGui import QIcon, QPalette, QPen, QPolygon
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QStyle,
    QStyleOptionToolButton,
    QStylePainter,
    QToolButton,
    QWidget,
)

from app.gcode.kernel.milling.kinematics import load_catalog
from app.settings import ui_language
from app.tools.setup import reset_program_setup
from app.ui.support.hotkeys import portable_shortcut
from app.ui.windows.main_window_file_ops import _same_file_path, _set_arc_action


@dataclass
class OpenDocument:
    document: QsciDocument
    file_name: str = ""
    encoding: str | None = None
    signature: tuple[int, int] | None = None
    ignored_signature: tuple[int, int] | None = None
    source_dialect: str = "fanuc"
    file_type: int = 0
    initial_mode: str | None = None
    arc_type: int | None = None
    comment_style: str | None = None
    manual_arc_type_override: bool = False
    untitled_number: int = 1
    cursor: tuple[int, int] = (0, 0)
    first_visible_line: int = 0
    selection: tuple[int, int, int, int] | None = None
    state: dict = field(default_factory=dict)


# Computed data belongs to the program, not to the main window.  The result
# and its sampled points are restored through the existing publication path.
_DOCUMENT_STATE = (
    "execution_result",
    "render_points",
    "_plot_source_stale",
    "_deferred_execution_result",
    "_deferred_execution_source",
    "_last_execution_ms",
    "_parsed_program_cache",
    "_auto_update_deferred",
    "program_tool_inference",
    "tools",
    "millingTools",
    "exportToolNumbers",
    "_fit_view_after_program_load",
    "latheMode",
    "_view_mode",
    "arc_type",
    "stockConfigured",
    "stockEnabled",
    "turnStockDiameter",
    "turnStockInnerDiameter",
    "turnStockLength",
    "turnStockResolution",
    "turnStockFrontAllowance",
    "turnStockFrontZ",
    "millingStockManual",
    "millingStockAllowance",
    "millingStockResolution",
    "millingStockAccuracy",
    "millingStockXMinus",
    "millingStockXPlus",
    "millingStockYMinus",
    "millingStockYPlus",
    "millingStockZMinus",
    "millingStockZPlus",
    "_stock_manual_override",
    "_stock_outline_use_configured",
)

# These preferences are shared by all documents. Cached executions must not be
# treated as current after any of their inputs change in another document.
_EXECUTION_SETTINGS = (
    "defaultUnits",
    "latheGcodeSystem",
    "sinumerik840dSl",
    "correctionEnabled",
    "autodetectArcType",
    "ignoreBlockSkip",
    "maxGeneratedMotions",
    "toolDiscovery",
    "turningToolLibrary",
    "millingToolLibrary",
    "rotaryKinematics",
    "wcsOffsets",
    "xPosMach",
    "yPosMach",
    "zPosMach",
    "homeConfigured",
    "arcTolerance",
    "maximumCircularRadius",
    "minimumCircularRadius",
    "minimumChordLength",
)

_DOCUMENT_DIALOGS = (
    "exportDlg",
    "blockNumDlg",
    "wcsDlg",
    "optionsDlg",
    "stockDlg",
    "toolLibraryDlg",
    "holeCalculatorDlg",
    "pocketCalculatorDlg",
    "snippetsDlg",
)


_RUSSIAN_LABELS = {
    "New document": "Новый документ",
    "Open documents": "Открытые документы",
    "Open documents (%1)": "Открытые документы (%1)",
    "Close document": "Закрыть документ",
    "Close": "Закрыть",
    "Close All": "Закрыть все",
    "Finish or cancel the active operation before switching documents.": (
        "Заверши или отмени текущую операцию перед переключением документов."
    ),
    "Wait for stock preparation to stop.": "Дождись остановки подготовки заготовки.",
    "Finish or cancel the open dialog before switching documents.": (
        "Заверши или отмени работу в открытом диалоге перед переключением документов."
    ),
}


def _document_tr(source):
    """Translate 2.5.0 controls even with the pre-existing bundled .qm file."""
    text = QCoreApplication.translate("MainWindow", source)
    if text == source and ui_language() == "ru":
        return _RUSSIAN_LABELS.get(source, source)
    return text


class DocumentControlButton(QToolButton):
    """Compact, palette-aware glyphs without font or native menu-arrow artifacts."""

    def __init__(self, glyph, parent):
        super().__init__(parent)
        self.glyph = glyph
        self.setAutoRaise(True)
        self.setFixedSize(25, 23)

    def paintEvent(self, event):
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        option.features &= ~QStyleOptionToolButton.ToolButtonFeature.HasMenu
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, option)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        color = self.palette().color(group, QPalette.ColorRole.ButtonText)
        painter.setPen(QPen(color, 1))
        x, y = self.rect().center().x(), self.rect().center().y()
        if self.glyph == "new":
            painter.drawLine(x - 3, y, x + 3, y)
            painter.drawLine(x, y - 3, x, y + 3)
        elif self.glyph == "list":
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(QPolygon([QPoint(x - 4, y - 2), QPoint(x + 4, y - 2), QPoint(x, y + 3)]))
        else:
            painter.drawLine(x - 3, y - 3, x + 3, y + 3)
            painter.drawLine(x - 3, y + 3, x + 3, y - 3)


class MainWindowDocumentsMixin:
    def _initialize_documents(self):
        """Install the controls without editing generated Designer source."""
        self._documents = [OpenDocument(self.ui.editor.document())]
        self._active_document_index = 0
        self._document_switching = False
        self._untitled_document_counter = 1
        self._documents[0].state = self._snapshot_runtime()
        self._document_defaults = self._fresh_document_state()

        corner = QWidget(self.ui.menubar)
        corner.setObjectName("documentControls")
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)
        self.documentNewButton = DocumentControlButton("new", corner)
        self.documentNewButton.setObjectName("documentNewButton")
        self.documentNewButton.setToolTip(_document_tr("New document"))
        self.documentNewButton.clicked.connect(self.newFile)
        self.documentListButton = DocumentControlButton("list", corner)
        self.documentListButton.setObjectName("documentListButton")
        self.documentListButton.setToolTip(_document_tr("Open documents"))
        self.documentListButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.documentListMenu = QMenu(self.documentListButton)
        self.documentListButton.setMenu(self.documentListMenu)
        self.documentListMenu.aboutToShow.connect(self._update_documents_menu)
        self.documentCloseButton = DocumentControlButton("close", corner)
        self.documentCloseButton.setObjectName("documentCloseButton")
        self.documentCloseButton.setToolTip(_document_tr("Close document"))
        self.documentCloseButton.clicked.connect(self.closeDocument)
        for button in (self.documentNewButton, self.documentListButton, self.documentCloseButton):
            button.setAccessibleName(button.toolTip())
            layout.addWidget(button)
        self.ui.menubar.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        file_menu = self.ui.menu_File
        self.actionCloseDocument = file_menu.addAction(_document_tr("Close"))
        self.actionCloseDocument.setObjectName("actionCloseDocument")
        self.actionCloseDocument.setIcon(QIcon(":/resource/icons/close.png"))
        self.actionCloseDocument.setShortcut("Ctrl+W")
        self.actionCloseDocument.triggered.connect(self.closeDocument)
        self.actionCloseAllDocuments = file_menu.addAction(_document_tr("Close All"))
        self.actionCloseAllDocuments.setObjectName("actionCloseAllDocuments")
        self.actionCloseAllDocuments.setIcon(QIcon(":/resource/icons/close-all.png"))
        self.actionCloseAllDocuments.triggered.connect(self.closeAllDocuments)
        # Give document closing its own group between saving and STL commands.
        file_menu.removeAction(self.actionCloseDocument)
        file_menu.removeAction(self.actionCloseAllDocuments)
        file_menu.insertAction(self.ui.actionImportSTL, self.actionCloseDocument)
        file_menu.insertAction(self.ui.actionImportSTL, self.actionCloseAllDocuments)
        file_menu.insertSeparator(self.ui.actionImportSTL)
        self._register_document_hotkeys()
        self._update_documents_menu()

    def _register_document_hotkeys(self):
        shortcuts = dict(self.hotkeys)
        for action in (self.actionCloseDocument, self.actionCloseAllDocuments):
            key = action.objectName()
            default = portable_shortcut(action.shortcut())
            self.hotkeyActions[key] = action
            self.defaultHotkeys[key] = default
            shortcuts[key] = self.settings.value(f"HOTKEYS/{key}", default)
            self.addAction(action)
        self.setHotkeys(shortcuts)

    def _execution_settings(self):
        values = {name: getattr(self, name) for name in _EXECUTION_SETTINGS}
        profile = values["rotaryKinematics"]
        values["rotary_profile"] = load_catalog(ignore_user_errors=True).get(profile) if profile else None
        return deepcopy(values)

    def _snapshot_runtime(self):
        state = {name: getattr(self, name) for name in _DOCUMENT_STATE}
        # These containers are edited in-place by tool/setup dialogs. A shallow
        # snapshot would let inactive documents inherit subsequent edits.
        for name in ("tools", "millingTools", "program_tool_inference", "exportToolNumbers"):
            state[name] = deepcopy(state[name])
        state["_camera"] = {
            key: type(self.ui.graphicsView.opts[key])(self.ui.graphicsView.opts[key])
            for key in ("center", "distance", "elevation", "azimuth", "rotation", "rotationMethod", "fov")
            if key in self.ui.graphicsView.opts
        }
        state["_projection_mode"] = self.ui.graphicsView.projectionMode()
        state["_orthographic_width"] = self.ui.graphicsView.orthographicWidth()
        state["_execution_settings"] = self._execution_settings()
        state["_stl_scene"] = self._capture_stl_scene()
        state["_stl_undo"] = list(self._stl_undo)
        state["_stl_redo"] = list(self._stl_redo)
        state["_stl_panel_visible"] = not self.stlObjectsDock.isHidden()
        return state

    def _fresh_document_state(self):
        state = {name: getattr(self, name) for name in _DOCUMENT_STATE}
        state.update(
            execution_result=None,
            render_points=[],
            tools={},
            millingTools={},
            program_tool_inference={},
            exportToolNumbers={},
            _parsed_program_cache=None,
            _plot_source_stale=False,
            _deferred_execution_result=None,
            _deferred_execution_source=None,
            _last_execution_ms=None,
            _auto_update_deferred=False,
            _fit_view_after_program_load=False,
            _stock_manual_override=False,
            _stock_outline_use_configured=False,
            millingStockManual=False,
        )
        return state

    def _capture_active_document(self):
        index = self._active_document_index
        if index is None or not 0 <= index < len(self._documents):
            return
        item = self._documents[index]
        editor = self.ui.editor
        item.document = editor.document()
        item.file_name = self.curFile
        item.encoding = self._document_encoding
        item.signature = self._document_disk_signature
        item.ignored_signature = self._ignored_document_signature
        item.source_dialect = self._document_source_dialect
        item.file_type = self.ui.fileTypeCombo.currentIndex()
        item.initial_mode = self._document_initial_mode
        item.arc_type = self._document_arc_type
        item.comment_style = self._document_comment_style
        item.manual_arc_type_override = self._manual_arc_type_override
        item.cursor = editor.getCursorPosition()
        item.first_visible_line = editor.firstVisibleLine()
        item.selection = editor.getSelection() if editor.hasSelectedText() else None
        item.state = self._snapshot_runtime()
        item.state["_playback_position"] = self.ui.horizontalSlider.value()
        item.state["_modified"] = editor.isModified()

    def _document_switch_allowed(self):
        """Never rebind the editor while callbacks could publish another trace."""
        if self._document_switching:
            return False
        if self._document_dialog_open():
            self.ui.statusbar.showMessage(
                _document_tr("Finish or cancel the open dialog before switching documents."), 5000
            )
            return False
        if any(
            getattr(self, flag)
            for flag in ("_kernel_execution_active", "_auto_update_in_progress", "_stock_export_active")
        ):
            self.ui.statusbar.showMessage(
                _document_tr("Finish or cancel the active operation before switching documents."),
                5000,
            )
            return False
        if not self._cancel_milling_seek():
            self.ui.statusbar.showMessage(_document_tr("Wait for stock preparation to stop."), 5000)
            return False
        return True

    def _document_dialog_open(self):
        return QApplication.activeModalWidget() is not None or any(
            getattr(self, name).isVisible() for name in _DOCUMENT_DIALOGS if hasattr(self, name)
        )

    def _document_reload_busy(self):
        return self._document_dialog_open() or any(
            getattr(self, flag)
            for flag in (
                "_document_switching",
                "_kernel_execution_active",
                "_auto_update_in_progress",
                "_stock_export_active",
            )
        )

    def _restore_document_source(self, item):
        self.ui.editor.setDocument(item.document)
        self.curFile = item.file_name
        self._document_encoding = item.encoding
        self._document_disk_signature = item.signature
        self._ignored_document_signature = item.ignored_signature
        self._document_source_dialect = item.source_dialect
        self._document_initial_mode = item.initial_mode
        self._document_arc_type = item.arc_type
        self._document_comment_style = item.comment_style
        self._manual_arc_type_override = item.manual_arc_type_override
        self.lexer.set_comment_style(item.comment_style or self.commentStyle)
        with QSignalBlocker(self.ui.fileTypeCombo):
            self.ui.fileTypeCombo.setCurrentIndex(item.file_type)
        self.changeFileType(self.ui.fileTypeCombo.currentIndex())
        self.arc_type = item.state["arc_type"]
        _set_arc_action(self, item.arc_type or self.arc_type)

    def _restore_document_mode(self, turning):
        changed = turning != self.latheMode
        with QSignalBlocker(self.ui.actionLatheMode):
            self.ui.actionLatheMode.setChecked(turning)
        self.latheMode = turning
        view = self.ui.graphicsView
        view.setPerspectiveZoomMode("distance" if turning else "fov")
        for action in (self.ui.action3D, self.ui.actionTop, self.ui.actionFront, self.ui.actionLeft):
            action.setEnabled(not turning)
        self.ui.actionGrid.setEnabled(turning)
        view.opts["fov"] = 0.01 if turning else 60
        view.opts["rotationMethod"] = "quaternion" if turning else "euler"
        view.setProjectionMode("perspective" if turning else "orthographic")
        return changed

    def _restore_document_scene(self, item, mode_changed):
        state = item.state
        for name in _DOCUMENT_STATE:
            if name not in ("execution_result", "render_points", "latheMode", "_view_mode"):
                value = state[name]
                if name in ("tools", "millingTools", "program_tool_inference", "exportToolNumbers"):
                    value = deepcopy(value)
                setattr(self, name, value)
        scene = state.get("_stl_scene")
        if scene is None:
            scene = type(self._capture_stl_scene())((), -1, None)
        self._restore_stl_scene(scene)
        self.stlObjectsDock.setVisible(state.get("_stl_panel_visible", bool(scene.objects)))
        self._stl_undo = list(state.get("_stl_undo", ()))
        self._stl_redo = list(state.get("_stl_redo", ()))
        self.stlObjectsDock.set_history_available(undo=bool(self._stl_undo), redo=bool(self._stl_redo))
        result, points = state["execution_result"], state["render_points"]
        if result is not None:
            self.finishDataUpdate(result, points, state.get("_playback_position"))
        else:
            self.execution_result, self.render_points = None, []
            self._update_stock_outline()
        self._plot_source_stale = state["_plot_source_stale"]
        self._deferred_execution_result = state["_deferred_execution_result"]
        self._deferred_execution_source = state["_deferred_execution_source"]
        if self.latheMode:
            self._view_mode = "lathe"
            if mode_changed:
                self.fitToView()
        else:
            desired = state.get("_view_mode", "3d")
            getattr(self, "view" + desired.title() if desired in ("top", "front", "left") else "view3d")()
        camera = state.get("_camera")
        if camera is not None:
            self.ui.graphicsView.opts.update({key: type(value)(value) for key, value in camera.items()})
            view = self.ui.graphicsView
            if state["_projection_mode"] == "orthographic":
                view.setOrthographicProjection(state["_orthographic_width"], 0.01, 1000.0)
            else:
                view.setProjectionMode("perspective")
            self._plot_camera_changed()
            view.update()

    def _sync_document_consumers(self, item):
        self.ui.editor.setCursorPosition(*item.cursor)
        if item.selection is not None:
            self.ui.editor.setSelection(*item.selection)
        self.ui.editor.setFirstVisibleLine(item.first_visible_line)
        self._update_document_title()
        self.documentWasModified()
        self._watch_current_document()
        self.updateStatusBar()
        self.timeStatusLabel.setText("Exec: --")
        self.updateExecutionStatus(elapsed_ms=item.state.get("_last_execution_ms"))
        self.ui.statusbar.clearMessage()
        self.wcsDlg.loadValues()
        self.exportDlg.sync_mode_availability(self.latheMode)
        self.syncGuiCapabilities()
        self.statisticsDlg.hide()
        if self.tokensDlg.isVisible():
            # Refresh the inspector's selected tab after restoring the document.
            self.tokensDlg._refresh_current_tab()  # pylint: disable=protected-access
        self._update_documents_menu()

    def _activate_document(self, index):
        if not 0 <= index < len(self._documents):
            return False
        if index == self._active_document_index:
            return True
        if not self._document_switch_allowed():
            return False
        self._capture_active_document()
        self.autoUpdateTimer.stop()
        self.timer.stop()
        self._document_change_timer.stop()
        self._document_switching = True
        self._loading_document = True
        try:
            item = self._documents[index]
            self.clearPlot()
            self._active_document_index = index
            settings = self._execution_settings()
            previous_settings = item.state.get("_execution_settings", settings)
            if previous_settings != settings:
                if any(previous_settings[key] != settings[key] for key in ("rotaryKinematics", "rotary_profile")):
                    item.state.pop("_camera", None)
                item.state.update(
                    _plot_source_stale=True,
                    _parsed_program_cache=None,
                    _deferred_execution_result=None,
                    _deferred_execution_source=None,
                )
            self._restore_document_source(item)
            mode_changed = self._restore_document_mode(bool(item.state["latheMode"]))
            self._restore_document_scene(item, mode_changed)
            self._sync_document_consumers(item)
        finally:
            self._loading_document = False
            self._document_switching = False
        if self._plot_source_stale and self.autoUpdateEnabled:
            self.scheduleAutoUpdate()
        self._schedule_document_disk_check()
        return True

    def _blank_document(self, *, inherit_mode=False):
        self._untitled_document_counter += 1
        state = deepcopy(self._document_defaults)
        if inherit_mode:
            state.update(latheMode=self.latheMode, _view_mode="lathe" if self.latheMode else "3d")
        return OpenDocument(
            QsciDocument(), untitled_number=self._untitled_document_counter, file_type=self.defaultFileType, state=state
        )

    def _new_document_slot(self):
        """Add an untitled buffer, keeping all existing files and undo stacks."""
        if not self._document_switch_allowed():
            return False
        self._capture_active_document()
        entry = self._blank_document(inherit_mode=True)
        self._documents.append(entry)
        # _activate_document needs the previous entry to remain selected until
        # it captures its state; the redundant capture above is intentional.
        if not self._activate_document(len(self._documents) - 1):
            self._documents.pop()
            return False
        reset_program_setup(self)
        self._document_arc_type = None
        self._document_comment_style = None
        self._manual_arc_type_override = False
        self._document_source_dialect = "fanuc"
        self._document_initial_mode = None
        self._document_encoding = None
        self._document_disk_signature = None
        self._ignored_document_signature = None
        self.setCurrentFile("")
        self.clearPlot()
        self.updateExecutionStatus()
        self._capture_active_document()
        self._update_documents_menu()
        return True

    def _empty_initial_slot(self):
        """Fill the active empty buffer, including one explicitly created by +."""
        return not self.curFile and not self.ui.editor.isModified() and not self.ui.editor.text()

    def _document_index_for_path(self, path):
        for index, item in enumerate(self._documents):
            if item.file_name and _same_file_path(item.file_name, path):
                return index
        return None

    def _update_document_title(self):
        name = Path(self.curFile).name if self.curFile else "new"
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "%s[*] - Easy G-code Plot") % name)
        self.setWindowModified(self.ui.editor.isModified())

    def _update_documents_menu(self):
        menu = getattr(self, "documentListMenu", None)
        if menu is None:
            return
        menu.clear()
        for index, item in enumerate(self._documents):
            name = Path(item.file_name).name if item.file_name else f"new {item.untitled_number}"
            modified = (
                self.ui.editor.isModified()
                if index == self._active_document_index
                else bool(item.state.get("_modified", False))
            )
            action = menu.addAction(("* " if modified else "") + name)
            action.setCheckable(True)
            action.setChecked(index == self._active_document_index)
            action.setToolTip(item.file_name or name)
            action.setStatusTip(item.file_name or name)
            action.triggered.connect(lambda _checked=False, i=index: self._activate_document(i))
        self.documentListButton.setToolTip(_document_tr("Open documents (%1)").replace("%1", str(len(self._documents))))

    def closeDocument(self):
        if not self._document_switch_allowed() or not self.maybeSave():
            return False
        index = self._active_document_index
        self.autoUpdateTimer.stop()
        self._documents.pop(index)
        self._active_document_index = None
        if not self._documents:
            # Keep one empty editor after closing the last document.
            self._documents.append(self._blank_document())
            return self._activate_document(0)
        return self._activate_document(min(index, len(self._documents) - 1))

    def closeAllDocuments(self, *, exiting=False):
        """Close until empty, stopping immediately on Save/Cancel failure."""
        if not self._document_switch_allowed():
            return False
        closing_state = self._snapshot_runtime() if exiting else None
        while self._documents:
            if not self.maybeSave():
                return False
            index = self._active_document_index
            self._documents.pop(index)
            self._active_document_index = None
            if not self._documents:
                break
            if not self._activate_document(min(index, len(self._documents) - 1)):
                return False
        if exiting:
            # Persist the user's active document preferences, not the defaults
            # of the empty editor normally created by File > Close All.
            for name in _DOCUMENT_STATE:
                setattr(self, name, closing_state[name])
            self.saveSettings()
            return True
        self._documents = [self._blank_document()]
        self._active_document_index = None
        return self._activate_document(0)
