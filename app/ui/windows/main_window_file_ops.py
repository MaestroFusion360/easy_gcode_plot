"""File, recent-file, drag-and-drop, and export helpers for the main window."""

import logging
import os
import time
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QCoreApplication, QFileInfo, QFileSystemWatcher, QIODevice, QSaveFile, QTimer
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox, QPlainTextEdit

from app.gcode.dxf_exporter import export_dxf
from app.gcode.exporter import DXF_MODE, _window_export_options, export_program
from app.gcode.kernel.io import NCTextDecodeError, read_nc_text
from app.gcode.trace_tools import format_tool_list, trace_statistics
from app.settings import normalized_recent_files as _normalized_recent_files
from app.tools.setup import reset_program_setup
from app.ui.windows.execution_worker import run_execution

LOGGER = logging.getLogger(__name__)
NC_FILE_FILTER = "NC programs (*.nc *.cnc *.ptp *.tap *.txt);;STL models (*.stl);;All files (*)"
SAVE_FILE_FILTER = "NC programs (*.nc *.cnc *.ptp *.tap *.txt);;All files (*)"


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
        path += ".nc"
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
    return (
        str(owner.ui.editor.text()),
        int(owner.exportMode),
        int(owner.exportArcMode),
        _window_export_options(owner, arc_mode=0),
        getattr(owner, "fileEncoding", "utf-8"),
    )


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
    source, mode, export_arc_mode, export_options, file_encoding = text_snapshot
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
