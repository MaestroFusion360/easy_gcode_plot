"""File, recent-file, drag-and-drop, and export helpers for the main window."""

import logging
import os
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QCoreApplication, QFileInfo, QFileSystemWatcher, QIODevice, QSaveFile, QTimer
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox, QPlainTextEdit

from app.gcode.comments import SEMICOLON
from app.gcode.export import DXF_MODE, MILL_FULL_PROGRAM_MODE, ExportOptions, _window_export_options, export_program
from app.gcode.export.dxf import export_dxf
from app.gcode.export.options import EXPANDED_EXECUTION_MODE
from app.gcode.export.resolved import convert_resolved_program
from app.gcode.export.sinumerik import convert_full_program_to_fanuc, convert_full_program_to_sinumerik
from app.gcode.export.source_formatting import format_full_program_source
from app.gcode.export.validation import validate_full_program_dialect_conversion
from app.gcode.kernel.api.resources import ExecutionLimits
from app.gcode.kernel.frontend.io import NCTextDecodeError, read_nc_text
from app.gcode.source_mode import (
    SINUMERIK_MODE_SIEMENS,
    SOURCE_DIALECT_FANUC,
    SOURCE_DIALECT_SINUMERIK,
    sinumerik_initial_mode,
    source_dialect_for_path,
)
from app.gcode.trace_tools import format_tool_list, trace_statistics
from app.settings import GENERATED_MOTIONS_DEFAULT
from app.settings import normalized_recent_files as _normalized_recent_files
from app.tools.setup import reset_program_setup
from app.ui.windows.execution_worker import run_execution

LOGGER = logging.getLogger(__name__)
NC_FILE_FILTER = "NC programs (*.nc *.cnc *.ptp *.mpf *.spf *.tap *.txt);;STL models (*.stl);;All files (*)"
SAVE_FILE_FILTER = "NC programs (*.nc *.cnc *.ptp *.mpf *.spf *.tap *.txt);;All files (*)"


def _set_arc_action(owner, arc_type: int) -> None:
    actions = (owner.ui.actionRelative_to_start, owner.ui.actionAbsolute, owner.ui.actionRadius_value)
    # QActionGroup needs action signals to maintain its exclusive selection.
    # Suspend only the settings handler while applying document defaults.
    for action in actions:
        action.toggled.disconnect(owner.changeArcType)
    try:
        selected = {1: actions[0], 2: actions[1], 3: actions[2]}.get(int(arc_type), actions[0])
        selected.setChecked(True)
    finally:
        for action in actions:
            action.toggled.connect(owner.changeArcType)


def _configure_document_source_mode(owner, file_name: str, source: str) -> None:
    """Apply MPF/SPF document defaults without persisting them as user settings."""
    dialect = source_dialect_for_path(file_name, source)
    setattr(owner, "_document_source_dialect", dialect)
    _configure_document_kinematics(owner, dialect)
    setattr(owner, "_document_arc_type", None)
    setattr(owner, "_document_comment_style", None)
    if dialect == SOURCE_DIALECT_SINUMERIK and sinumerik_initial_mode(source) == SINUMERIK_MODE_SIEMENS:
        setattr(owner, "_document_arc_type", 2)
        setattr(owner, "_document_comment_style", SEMICOLON)
    comment_style = getattr(owner, "_document_comment_style")
    arc_type = getattr(owner, "_document_arc_type")
    owner.lexer.set_comment_style(comment_style or owner.commentStyle)
    _set_arc_action(owner, arc_type or owner.arc_type)


def _reset_document_source_mode(owner) -> None:
    setattr(owner, "_document_source_dialect", SOURCE_DIALECT_FANUC)
    _configure_document_kinematics(owner, SOURCE_DIALECT_FANUC)
    setattr(owner, "_document_arc_type", None)
    setattr(owner, "_document_comment_style", None)
    owner.lexer.set_comment_style(owner.commentStyle)
    _set_arc_action(owner, owner.arc_type)


def _configure_document_kinematics(owner, dialect):
    """Restrict SINUMERIK documents without overwriting the user's profile."""
    restricted = dialect == SOURCE_DIALECT_SINUMERIK
    if restricted:
        if not getattr(owner, "_document_rotary_restricted", False):
            setattr(owner, "_rotary_before_sinumerik", getattr(owner, "rotaryKinematics", None))
        owner.rotaryKinematics = None
    elif getattr(owner, "_document_rotary_restricted", False):
        owner.rotaryKinematics = getattr(owner, "_rotary_before_sinumerik", None)
    setattr(owner, "_document_rotary_restricted", restricted)
    refresh = getattr(owner, "_refresh_rotary_kinematics_menu", None)
    if refresh is not None:
        refresh()
    options = getattr(owner, "optionsDlg", None)
    if options is not None:
        options.sync_rotary_kinematics(getattr(owner, "rotaryKinematics", None))


def _read_editor_text(path: str, encoding: str) -> tuple[str, str]:
    """Open legacy Windows NC text when the default UTF-8 decoding fails."""
    try:
        return read_nc_text(path, encoding=encoding), encoding
    except NCTextDecodeError as error:
        if encoding != "utf-8" or b"\x00" in Path(path).read_bytes():
            raise error
        return read_nc_text(path, encoding="cp1251"), "cp1251"


def _file_signature(path):
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _same_file_path(first, second):
    """Compare local paths using the current platform's case semantics."""
    left = os.path.normcase(os.path.normpath(QFileInfo(str(first)).absoluteFilePath()))
    right = os.path.normcase(os.path.normpath(QFileInfo(str(second)).absoluteFilePath()))
    return left == right


def _atomic_write(path, text, *, encoding):
    data = text.encode(encoding)
    output = QSaveFile(str(path))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(output.errorString())
    if output.write(data) != len(data):
        error = output.errorString()
        output.cancelWriting()
        raise OSError(error)
    if not output.commit():
        raise OSError(output.errorString())


def _export_diagnostic_text(result, error) -> str:
    """Build a complete, copyable explanation for an export failure."""
    diagnostics = () if result is None else getattr(result, "diagnostics", ())
    sections = []
    for diagnostic in sorted(diagnostics, key=lambda item: getattr(item, "severity", "error") != "error"):
        severity = str(getattr(diagnostic, "severity", "error")).upper()
        line = getattr(diagnostic, "line", None)
        location = QCoreApplication.translate("MainWindow", "line {0}").format(line) if line is not None else ""
        heading = " — ".join(part for part in (severity, location, str(diagnostic.code)) if part)
        body = [heading, str(diagnostic.message)]
        raw = getattr(diagnostic, "raw", None)
        if raw:
            body.append(QCoreApplication.translate("MainWindow", "Source: {0}").format(raw))
        sections.append("\n".join(body))
    if not sections:
        sections.append(str(error))
    return "\n\n".join(sections)


def _show_export_error(owner, error, result) -> None:
    """Show export diagnostics in an always-visible, copyable text area."""
    invalid_execution = result is None or not result.ok or not result.complete
    dialog = QMessageBox(owner)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Export failed"))
    if invalid_execution:
        dialog.setText(
            QCoreApplication.translate(
                "MainWindow", "Export is unavailable because CNC execution is invalid or incomplete."
            )
        )
        dialog.setInformativeText(
            QCoreApplication.translate("MainWindow", "Correct the diagnostics below and run the export again.")
        )
    else:
        dialog.setText(QCoreApplication.translate("MainWindow", "The program could not be exported."))
    details = QPlainTextEdit(_export_diagnostic_text(result, error), dialog)
    details.setReadOnly(True)
    details.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    details.setMinimumSize(720, 240)
    layout = dialog.layout()
    layout.addWidget(details, layout.rowCount(), 0, 1, layout.columnCount())
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.exec()


def _export_target(owner):
    dxf_export = int(owner.exportMode) == DXF_MODE
    file_filter = "DXF (*.dxf)" if dxf_export else SAVE_FILE_FILTER
    path, _ = QFileDialog.getSaveFileName(owner, "Export", "", file_filter)
    if not path:
        return None
    if dxf_export and Path(path).suffix.casefold() != ".dxf":
        path = str(Path(path).with_suffix(".dxf"))
    elif not dxf_export and not Path(path).suffix:
        path += ".mpf" if int(getattr(owner, "exportTargetCnc", 0)) in (2, 3) else ".nc"
    return path, dxf_export


def _ensure_current_export_trace(owner) -> bool:
    result = getattr(owner, "execution_result", None)
    trace_current = (
        result is not None
        and result.ok
        and getattr(result, "complete", result.ok)
        and not getattr(owner, "_plot_source_stale", False)
    )
    if trace_current:
        return True
    value = owner.ui.horizontalSlider.value()
    if not owner.updateData():
        return False
    slider = owner.ui.horizontalSlider
    if hasattr(slider, "setValue") and hasattr(slider, "maximum"):
        slider.setValue(min(value, slider.maximum()))
    else:
        owner.valueHandler(value)
    return True


def _text_export_snapshot(owner):
    source = str(owner.ui.editor.text())
    source_dialect = source_dialect_for_path(getattr(owner, "curFile", None), source)
    inference = deepcopy(getattr(owner, "program_tool_inference", {}) or {})
    execution_options = {
        "current_tools": deepcopy(getattr(owner, "millingTools", {}) or {}),
        "previous_inference": deepcopy(inference.get("millingTools", {})),
        "correction_enabled": bool(getattr(owner, "correctionEnabled", True)),
        "lathe_gcode_system": getattr(owner, "latheGcodeSystem", "A"),
        "kinematics": deepcopy(getattr(owner, "rotaryKinematics", None)),
        "source_arc_type": getattr(owner, "_document_arc_type", None) or getattr(owner, "arc_type", 1),
        "autodetect_arc_type": getattr(owner, "autodetectArcType", True)
        and not getattr(owner, "_manual_arc_type_override", False)
        and getattr(owner, "_document_arc_type", None) is None,
        "skip_optional_blocks": bool(getattr(owner, "ignoreBlockSkip", False)),
        "arc_tolerance": float(getattr(owner, "arcTolerance", 0.01)),
        "default_unit_scale": 25.4 if getattr(owner, "defaultUnits", "mm") == "inch" else 1.0,
        "home_x": float(getattr(owner, "xPosMach", 0.0)),
        "home_y": float(getattr(owner, "yPosMach", 0.0)),
        "home_z": float(getattr(owner, "zPosMach", 0.0)),
        "wcs_offsets": deepcopy(getattr(owner, "wcsOffsets", None)),
        "emulate_g28_home": bool(getattr(owner, "homeConfigured", True)),
        "include_instructions": False,
        "limits": ExecutionLimits(
            generated_motions=max(1, int(getattr(owner, "maxGeneratedMotions", GENERATED_MOTIONS_DEFAULT)))
        ),
    }
    return (
        source,
        int(owner.exportMode),
        int(owner.exportArcMode),
        _window_export_options(owner, arc_mode=0),
        getattr(owner, "fileEncoding", "utf-8"),
        int(getattr(owner, "exportTargetCnc", 0)),
        source_dialect,
        execution_options,
    )


def _convert_full_program_dialect(source, result, target_cnc, source_dialect, options, execution_options):
    options = options or ExportOptions()
    targets = {
        1: (SOURCE_DIALECT_FANUC, convert_full_program_to_fanuc),
        2: (SOURCE_DIALECT_SINUMERIK, convert_full_program_to_sinumerik),
    }
    try:
        target_dialect, converter = targets[target_cnc]
    except KeyError as exc:
        raise ValueError("Unknown target CNC type") from exc
    if source_dialect == target_dialect:
        target_name = "SINUMERIK ISO-M" if target_cnc == 2 else "FANUC milling"
        raise ValueError(f"The source is already {target_name}; choose the other CNC type or As source")
    if target_cnc == 2:
        unsafe_compensation = {"UNVERIFIED_CUTTER_COMPENSATION", "UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION"}
        if any(item.code in unsafe_compensation for item in result.diagnostics):
            raise ValueError("SINUMERIK conversion requires cutter compensation to be resolved by the kernel")
    converted = (
        converter(
            format_full_program_source(source, options), source_result=result, execution_options=execution_options
        )
        if target_cnc == 2
        else converter(source)
    )
    converted_source = converted if target_cnc == 2 else format_full_program_source(converted, options)
    validate_full_program_dialect_conversion(
        result,
        converted_source,
        "fanuc_mill",
        source_dialect=target_dialect,
        execution_options=execution_options,
    )
    return converted_source


def _write_export(
    _unused,
    *,
    dxf_export,
    path,
    result,
    render_points,
    lathe_mode,
    text_snapshot,
    cancellation,
):
    if cancellation.is_set():
        return None
    if dxf_export:
        export_dxf(
            result,
            path,
            turning=lathe_mode,
            render_points=render_points,
            cancelled=cancellation.is_set,
        )
        return None
    assert text_snapshot is not None
    source, mode, export_arc_mode, export_options, file_encoding, target_cnc, source_dialect, execution_options = (
        text_snapshot
    )
    if target_cnc and not lathe_mode and mode == EXPANDED_EXECUTION_MODE:
        target = {1: "fanuc_mill", 2: "sinumerik_iso", 3: "sinumerik_native"}[target_cnc]
        resolved_options = replace(export_options or ExportOptions(), arc_mode=export_arc_mode)
        text = convert_resolved_program(result, target, resolved_options, cancelled=cancellation.is_set)
    elif target_cnc:
        if lathe_mode or mode != MILL_FULL_PROGRAM_MODE:
            raise ValueError("SINUMERIK/FANUC dialect conversion is available only for milling Full Program export")
        text = _convert_full_program_dialect(
            source, result, target_cnc, source_dialect, export_options, execution_options
        )
    else:
        text = export_program(
            result,
            source,
            mode=mode,
            lathe_mode=lathe_mode,
            options=export_options,
            export_arc_mode=export_arc_mode,
            cancelled=cancellation.is_set,
        )
    if cancellation.is_set():
        return None
    _atomic_write(path, text, encoding=file_encoding)
    return None


class MainWindowFileMixin:
    def _configure_document_watcher(self):
        """Watch both the file and its directory so atomic replacements are seen."""
        self._document_watcher = QFileSystemWatcher(self)
        self._document_watcher.fileChanged.connect(self._schedule_document_disk_check)
        self._document_watcher.directoryChanged.connect(self._schedule_document_disk_check)
        self._document_change_timer = QTimer(self)
        self._document_change_timer.setSingleShot(True)
        self._document_change_timer.setInterval(300)
        self._document_change_timer.timeout.connect(self._check_document_disk_change)
        self._ignored_document_signature = None
        self._document_reload_prompt_active = False

    def _watch_current_document(self):
        watcher = getattr(self, "_document_watcher", None)
        if watcher is None:
            return
        paths = watcher.files() + watcher.directories()
        if paths:
            watcher.removePaths(paths)
        file_name = getattr(self, "curFile", "")
        if not file_name:
            self._document_change_timer.stop()
            return
        path = Path(file_name).resolve()
        if path.parent.is_dir():
            watcher.addPath(str(path.parent))
        if path.is_file():
            watcher.addPath(str(path))

    def _schedule_document_disk_check(self, _path=None):
        if getattr(self, "curFile", "") and self.isVisible():
            self._document_change_timer.start()

    def _check_document_disk_change(self):
        """Ask once per external file version, retaining any rejected edit."""
        file_name = getattr(self, "curFile", "")
        if not file_name or self._document_reload_prompt_active:
            return
        path = Path(file_name).resolve()
        watcher = self._document_watcher
        if path.is_file() and str(path) not in watcher.files():
            watcher.addPath(str(path))
        signature = _file_signature(path)
        if signature is None or signature in (
            getattr(self, "_document_disk_signature", None),
            self._ignored_document_signature,
        ):
            return

        self._ignored_document_signature = signature
        prompt = QCoreApplication.translate(
            "MainWindow", "This file has been modified by another program.\nDo you want to reload it from disk?"
        )
        if self.ui.editor.isModified():
            prompt += "\n\n" + QCoreApplication.translate("MainWindow", "Reloading will discard your unsaved changes.")
        self._document_reload_prompt_active = True
        try:
            answer = QMessageBox.question(
                self,
                QCoreApplication.translate("MainWindow", "Reload file"),
                f"{path}\n\n{prompt}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        finally:
            self._document_reload_prompt_active = False
        if answer == QMessageBox.StandardButton.Yes:
            self.loadFile(file_name)

    @staticmethod
    def _first_local_drop_path(event):
        """Return the first local file from a drop event, or an empty string."""
        if not event.mimeData().hasUrls():
            return ""
        for url in event.mimeData().urls():
            if url.isLocalFile():
                return url.toLocalFile()
        return ""

    def dragEnterEvent(self, event):
        """Accept drag events only when they contain at least one local file."""
        if self._first_local_drop_path(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Open the first local file from a drop and ignore additional URLs."""
        file_name = self._first_local_drop_path(event)
        if not file_name:
            event.ignore()
            return
        if self.maybeSave():
            self.loadFile(file_name)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _setup_recent_files_menu(self):
        """Create the File -> Recent Files menu without changing the generated UI."""
        self.recentFilesMenu = QMenu(QCoreApplication.translate("MainWindow", "Recent Files"), self.ui.menu_File)
        separator = next((action for action in self.ui.menu_File.actions() if action.isSeparator()), None)
        if separator is None:
            self.ui.menu_File.addMenu(self.recentFilesMenu)
        else:
            self.ui.menu_File.insertMenu(separator, self.recentFilesMenu)
        self._update_recent_files_menu()

    def _setup_recent_stl_menu(self):
        """Add File -> Recent STL immediately after Clear STL."""
        self.recentStlMenu = QMenu(QCoreApplication.translate("MainWindow", "Recent STL"), self.ui.menu_File)
        actions = self.ui.menu_File.actions()
        clear_index = next((i for i, action in enumerate(actions) if action is self.ui.actionClearSTL), -1)
        following_separator = next(
            (action for action in actions[clear_index + 1 :] if action.isSeparator()),
            None,
        )
        if following_separator is None:
            self.ui.menu_File.addMenu(self.recentStlMenu)
        else:
            self.ui.menu_File.insertMenu(following_separator, self.recentStlMenu)
        self._update_recent_stl_menu()

    def _update_recent_stl_menu(self):
        self.recentStlMenu.clear()
        self.recentStlFiles = _normalized_recent_files(self.recentStlFiles)
        if not self.recentStlFiles:
            action = self.recentStlMenu.addAction(QCoreApplication.translate("MainWindow", "(Empty)"))
            action.setEnabled(False)
            return
        for index, path in enumerate(self.recentStlFiles, start=1):
            action = self.recentStlMenu.addAction(f"{index}. {path}")
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_stl(p))
        self.recentStlMenu.addSeparator()
        self.recentStlMenu.addAction(
            QCoreApplication.translate("MainWindow", "Clear Recent STL"), self._clear_recent_stl
        )

    def _persist_recent_stl_files(self):
        self.settings.setValue("FILE/RECENT_STL_FILES", self.recentStlFiles)
        self.settings.sync()

    def _add_recent_stl(self, path):
        absolute = QFileInfo(str(path)).absoluteFilePath()
        self.recentStlFiles = _normalized_recent_files([absolute, *self.recentStlFiles])
        self._update_recent_stl_menu()
        self._persist_recent_stl_files()

    def _remove_recent_stl(self, path):
        key = os.path.normcase(str(path))
        self.recentStlFiles = [item for item in self.recentStlFiles if os.path.normcase(item) != key]
        self._update_recent_stl_menu()
        self._persist_recent_stl_files()

    def _clear_recent_stl(self):
        self.recentStlFiles = []
        self._update_recent_stl_menu()
        self._persist_recent_stl_files()

    def _open_recent_stl(self, path):
        if not QFileInfo(path).exists():
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate("MainWindow", "File not found:\n{0}").format(path),
            )
            self._remove_recent_stl(path)
            return
        self.importStl(path)

    def _update_recent_files_menu(self):
        self.recentFilesMenu.clear()
        self.recentFiles = _normalized_recent_files(self.recentFiles)
        if not self.recentFiles:
            action = self.recentFilesMenu.addAction(QCoreApplication.translate("MainWindow", "(Empty)"))
            action.setEnabled(False)
            return
        for index, path in enumerate(self.recentFiles, start=1):
            action = self.recentFilesMenu.addAction(f"{index}. {path}")
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_file(p))
        self.recentFilesMenu.addSeparator()
        self.recentFilesMenu.addAction(
            QCoreApplication.translate("MainWindow", "Clear Recent"), self._clear_recent_files
        )

    def _persist_recent_files(self):
        self.settings.setValue("FILE/RECENT_FILES", self.recentFiles)
        self.settings.sync()

    def _remember_file_directory(self, path):
        """Persist the directory used by Open File for the next dialog."""
        directory = str(Path(path).expanduser().resolve().parent)
        self.settings.setValue("FILE/LAST_OPEN_DIRECTORY", directory)
        self.settings.sync()

    def _open_file_directory(self):
        """Return the last valid Open File directory, with useful fallbacks."""
        remembered = self.settings.value("FILE/LAST_OPEN_DIRECTORY", "", type=str)
        if remembered and Path(remembered).is_dir():
            return remembered
        current_file = getattr(self, "curFile", "")
        if current_file:
            current_directory = str(Path(current_file).expanduser().parent)
            if Path(current_directory).is_dir():
                return current_directory
        return str(Path.home())

    def _add_recent_file(self, path):
        absolute = QFileInfo(str(path)).absoluteFilePath()
        self.recentFiles = _normalized_recent_files([absolute, *self.recentFiles])
        self._update_recent_files_menu()
        self._persist_recent_files()

    def _remove_recent_file(self, path):
        key = os.path.normcase(str(path))
        self.recentFiles = [item for item in self.recentFiles if os.path.normcase(item) != key]
        self._update_recent_files_menu()
        self._persist_recent_files()

    def _clear_recent_files(self):
        self.recentFiles = []
        self._update_recent_files_menu()
        self._persist_recent_files()

    def _open_recent_file(self, path):
        if not QFileInfo(path).exists():
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate("MainWindow", "File not found:\n{0}").format(path),
            )
            self._remove_recent_file(path)
            return
        if self.maybeSave():
            self.loadFile(path)

    def newFile(self):
        """Clear editor contents and reset state for a new document."""
        if self.maybeSave():
            reset_program_setup(self)
            self._manual_arc_type_override = False
            _reset_document_source_mode(self)
            self.curFile = ""
            self._document_disk_signature = None
            self._document_encoding = None
            self._ignored_document_signature = None
            self.ui.editor.clear()
            self.setCurrentFile("")
            self._watch_current_document()
            self.clearPlot()
            self.clearStl()
            if hasattr(self, "resetStockToAuto"):
                self.resetStockToAuto(refresh=False)
            self.syncGuiCapabilities()

    def openFile(self):
        """Prompt for a file to open and load its contents."""
        if self.maybeSave():
            fileName, _ = QFileDialog.getOpenFileName(self, "Open", self._open_file_directory(), NC_FILE_FILTER)
            if fileName:
                self.loadFile(fileName)

    def save(self):
        """Save the current file or prompt for a destination if unnamed."""
        if self.curFile:
            return self.saveFile(self.curFile)
        return self.saveAs()

    def saveAs(self):
        """Prompt for a file path and save the document there."""
        fileName, _ = QFileDialog.getSaveFileName(self, "Save As", self.curFile or "", SAVE_FILE_FILTER)
        if fileName:
            if not Path(fileName).suffix:
                fileName += ".nc"
            return self.saveFile(fileName)
        return False

    def documentWasModified(self):
        """Update document actions without invalidating the displayed trace."""
        modified = self.ui.editor.isModified()
        self.setWindowModified(modified)
        self.ui.actionSave.setEnabled(modified)
        self.ui.actionUndo.setEnabled(self.ui.editor.isUndoAvailable())
        self.ui.actionRedo.setEnabled(self.ui.editor.isRedoAvailable())

    def maybeSave(self):
        """Ask the user to save if the document has unsaved changes."""
        if self.ui.editor.isModified():
            buttons = (
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            ret = QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate(
                    "MainWindow", "The document has been modified.\nDo you want to save your changes?"
                ),
                buttons,
            )

            if ret == QMessageBox.StandardButton.Save:
                return self.save()

            if ret == QMessageBox.StandardButton.Cancel:
                return False

        return True

    def loadFile(self, fileName):
        """Load file contents into the editor and reset cursor."""
        if Path(fileName).suffix.casefold() == ".stl":
            return self.importStl(fileName)
        try:
            content, document_encoding = _read_editor_text(fileName, getattr(self, "fileEncoding", "utf-8"))
        except (OSError, UnicodeError) as exc:
            LOGGER.exception("file_open_failed path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate("MainWindow", "Cannot read file %s:\n%s.") % (fileName, exc),
            )
            return

        reset_program_setup(self)
        self._manual_arc_type_override = False
        _configure_document_source_mode(self, fileName, content)
        LOGGER.info("file_opened path=%s encoding=%s", fileName, document_encoding)
        if hasattr(self, "resetStockToAuto"):
            self.resetStockToAuto(refresh=False)
        # Opening another program invalidates the previous trajectory immediately.
        # Do not force an unbounded manual Update here: large programs must keep
        # the normal Auto Update point limit and must not block file opening.
        self.clearPlot()
        self._fit_view_after_program_load = True
        self._document_disk_signature = _file_signature(fileName)
        self._document_encoding = document_encoding
        self._ignored_document_signature = None
        if hasattr(self, "autoUpdateTimer"):
            self.autoUpdateTimer.stop()
        self._loading_document = True
        try:
            self.ui.editor.setText(content)
        finally:
            self._loading_document = False
        self.ui.editor.setCursorPosition(0, 0)
        self.setCurrentFile(fileName)
        self._watch_current_document()
        self._remember_file_directory(fileName)
        self.changeFileType(self.ui.fileTypeCombo.currentIndex())
        self.syncGuiCapabilities()
        self._add_recent_file(fileName)
        # Opening the file itself must stay immediate.  Clear the old geometry
        # above, then hand recalculation back to the normal Auto Update path so
        # the user's setting is respected instead of forcing a synchronous
        # trajectory build for every Open.
        self.scheduleAutoUpdate(show_dialog=True)

    def saveFile(self, fileName):
        """Write editor contents to disk."""
        encoding = getattr(self, "_document_encoding", None) or getattr(self, "fileEncoding", "utf-8")
        same_file = bool(self.curFile) and _same_file_path(fileName, self.curFile)
        if same_file and getattr(self, "_document_disk_signature", None) is not None:
            if _file_signature(fileName) != self._document_disk_signature:
                answer = QMessageBox.warning(
                    self,
                    QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                    QCoreApplication.translate(
                        "MainWindow", "The file was changed by another application. Overwrite those changes?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return False
        try:
            _atomic_write(
                fileName,
                self.ui.editor.text(),
                encoding=encoding,
            )
        except (OSError, UnicodeError) as exc:
            LOGGER.exception("file_save_failed path=%s encoding=%s", fileName, encoding)
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate("MainWindow", "Cannot write file %s:\n%s.") % (fileName, exc),
            )
            return False

        LOGGER.info("file_saved path=%s encoding=%s", fileName, encoding)
        _configure_document_source_mode(self, fileName, self.ui.editor.text())
        self.setCurrentFile(fileName)
        self._document_disk_signature = _file_signature(fileName)
        self._document_encoding = encoding
        self._ignored_document_signature = None
        self._watch_current_document()
        self._remember_file_directory(fileName)
        self._add_recent_file(fileName)
        return True

    def setCurrentFile(self, fileName):
        """Update window title and modified flags for the current file."""
        self.curFile = fileName
        self.ui.editor.setModified(False)
        self.setWindowModified(False)
        self.ui.actionSave.setEnabled(False)

        if self.curFile:
            name = self.strippedName(self.curFile)
        else:
            name = "new"

        self.setWindowTitle(QCoreApplication.translate("MainWindow", "%s[*] - Easy G-code Plot") % name)

    def strippedName(self, fullFileName):
        """Return just the filename component."""
        return QFileInfo(fullFileName).fileName()

    def exportToolList(self):
        """Export a CIMCO-style list from the current resolved toolpath."""
        if not _ensure_current_export_trace(self):
            return False
        result = self.execution_result
        source_path = self.curFile or None
        default_stem = Path(source_path).stem if source_path else "tool-list"
        target, _selected_filter = QFileDialog.getSaveFileName(
            self,
            QCoreApplication.translate("MainWindow", "Tool List"),
            f"{default_stem}-tool-list.txt",
            QCoreApplication.translate("MainWindow", "Text files (*.txt);;All files (*)"),
        )
        if not target:
            return False
        if not Path(target).suffix:
            target += ".txt"
        tools = self.tools if self.latheMode else self.millingTools
        report = format_tool_list(
            result,
            trace_statistics(result, rapid_feed=self.rapidFeed),
            tools,
            file_path=source_path,
            turning=self.latheMode,
        )
        try:
            _atomic_write(target, report + "\n", encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.critical(
                self,
                QCoreApplication.translate("MainWindow", "Tool List"),
                QCoreApplication.translate("MainWindow", "Cannot write tool list %s:\n%s.") % (target, exc),
            )
            return False
        self.statusBar().showMessage(
            QCoreApplication.translate("MainWindow", "Tool list exported to %s") % target,
            5000,
        )
        return True

    def export(self):
        """Export current program to a chosen file path."""
        target = _export_target(self)
        if target is None:
            return
        path, dxf_export = target
        started = time.time()
        if not _ensure_current_export_trace(self):
            result = getattr(self, "execution_result", None)
            if result is None or not result.ok or not result.complete:
                _show_export_error(
                    self,
                    ValueError(
                        QCoreApplication.translate(
                            "MainWindow", "No valid CNC execution result is available for export"
                        )
                    ),
                    result,
                )
            return
        result = self.execution_result
        cancellation = Event()
        try:
            run_execution(
                self,
                _write_export,
                None,
                {
                    "dxf_export": dxf_export,
                    "path": path,
                    "result": result,
                    "render_points": self.render_points,
                    "lathe_mode": bool(self.latheMode),
                    "text_snapshot": None if dxf_export else _text_export_snapshot(self),
                    "cancellation": cancellation,
                },
                cancellation.set,
                title=QCoreApplication.translate("MainWindow", "Export"),
                status_text=QCoreApplication.translate("MainWindow", "Exporting program…"),
                cancelling_text=QCoreApplication.translate("MainWindow", "Cancelling export…"),
            )
        except InterruptedError:
            self.ui.statusbar.showMessage(QCoreApplication.translate("MainWindow", "Export cancelled."), 5000)
            return
        except Exception as exc:  # Export/file-system errors are surfaced to the GUI.
            LOGGER.exception("export_failed path=%s", path)
            _show_export_error(self, exc, result)
            return
        elapsed_ms = (time.time() - started) * 1000.0
        LOGGER.info("export_completed path=%s duration_ms=%.3f", path, elapsed_ms)
        self.ui.statusbar.showMessage(
            QCoreApplication.translate("MainWindow", "Export Execution time: {0:.3f} ms").format(elapsed_ms), 10000
        )
