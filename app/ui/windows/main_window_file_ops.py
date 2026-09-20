"""File, recent-file, drag-and-drop, and export helpers for the main window."""

import logging
import os
import time
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QCoreApplication, QFileInfo, QIODevice, QSaveFile
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox

from app.gcode.core import format_gcode_number
from app.gcode.dxf_exporter import export_dxf
from app.gcode.exporter import DXF_MODE, _window_export_options, export_pgm, export_program
from app.gcode.kernel.io import read_nc_text
from app.settings import normalized_recent_files as _normalized_recent_files
from app.tools.setup import reset_program_setup
from app.ui.windows.execution_worker import run_execution

LOGGER = logging.getLogger(__name__)
NC_FILE_FILTER = "NC programs (*.nc *.cnc *.tap *.txt);;STL models (*.stl);;All files (*)"
SAVE_FILE_FILTER = "NC programs (*.nc *.cnc *.tap *.txt);;All files (*)"


def _file_signature(path):
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


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
            self.curFile = ""
            self._document_disk_signature = None
            self.ui.editor.clear()
            self.setCurrentFile("")
            self.clearPlot()
            if hasattr(self, "resetStockToAuto"):
                self.resetStockToAuto(refresh=False)
            self.syncGuiCapabilities()

    def openFile(self):
        """Prompt for a file to open and load its contents."""
        if self.maybeSave():
            fileName, _ = QFileDialog.getOpenFileName(self, "Open", "", NC_FILE_FILTER)
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
        self.setWindowModified(self.ui.editor.isModified())
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
            content = read_nc_text(fileName, encoding=getattr(self, "fileEncoding", "utf-8"))
        except (OSError, UnicodeError) as exc:
            LOGGER.exception("file_open_failed path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate("MainWindow", "Cannot read file %s:\n%s.") % (fileName, exc),
            )
            return

        reset_program_setup(self)
        LOGGER.info("file_opened path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
        if hasattr(self, "resetStockToAuto"):
            self.resetStockToAuto(refresh=False)
        # Opening another program invalidates the previous trajectory immediately.
        # Do not force an unbounded manual Update here: large programs must keep
        # the normal Auto Update point limit and must not block file opening.
        self.clearPlot()
        self._fit_view_after_program_load = True
        self._document_disk_signature = _file_signature(fileName)
        if hasattr(self, "autoUpdateTimer"):
            self.autoUpdateTimer.stop()
        self._loading_document = True
        try:
            self.ui.editor.setText(content)
        finally:
            self._loading_document = False
        self.ui.editor.setCursorPosition(0, 0)
        self.setCurrentFile(fileName)
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
        same_file = (
            bool(self.curFile)
            and QFileInfo(fileName).absoluteFilePath().casefold()
            == QFileInfo(self.curFile).absoluteFilePath().casefold()
        )
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
                encoding=getattr(self, "fileEncoding", "utf-8"),
            )
        except (OSError, UnicodeError) as exc:
            LOGGER.exception("file_save_failed path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MainWindow", "Easy G-code Plot"),
                QCoreApplication.translate("MainWindow", "Cannot write file %s:\n%s.") % (fileName, exc),
            )
            return False

        LOGGER.info("file_saved path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
        self.setCurrentFile(fileName)
        self._document_disk_signature = _file_signature(fileName)
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

        self.setWindowTitle(QCoreApplication.translate("MainWindow", "%s[*] - Easy G-code Plot") % name)

    def strippedName(self, fullFileName):
        """Return just the filename component."""
        return QFileInfo(fullFileName).fileName()

    def export(self):
        """Export current program to a chosen file path."""
        target = _export_target(self)
        if target is None:
            return
        path, dxf_export = target
        started = time.time()
        if not _ensure_current_export_trace(self):
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
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Easy G-code Plot"), str(exc))
            return
        elapsed_ms = (time.time() - started) * 1000.0
        LOGGER.info("export_completed path=%s duration_ms=%.3f", path, elapsed_ms)
        self.ui.statusbar.showMessage(
            QCoreApplication.translate("MainWindow", "Export Execution time: {0:.3f} ms").format(elapsed_ms), 10000
        )

    def exportPgm(self):
        """Generate the exportable program text based on parsed toolpath data."""
        return export_pgm(self)

    def floatToStr(self, val):
        """Format numeric values to compact strings for G-code output."""
        return format_gcode_number(val)
