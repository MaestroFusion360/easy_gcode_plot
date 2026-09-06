"""File, recent-file, drag-and-drop, and export helpers for the main window."""

import logging
import time
from pathlib import Path

from PyQt6.QtCore import QFileInfo
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox

from app.gcode.core import format_gcode_number
from app.gcode.exporter import export_pgm
from app.settings import normalized_recent_files as _normalized_recent_files

LOGGER = logging.getLogger(__name__)


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
        try:
            content = Path(fileName).read_text(encoding=getattr(self, "fileEncoding", "utf-8"))
        except (OSError, UnicodeError) as exc:
            LOGGER.exception("file_open_failed path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
            QMessageBox.warning(
                self,
                "Easy G-code Plot",
                "Cannot read file %s:\n%s." % (fileName, exc),
            )
            return

        LOGGER.info("file_opened path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
        self.ui.editor.setText(content)
        self.ui.editor.setCursorPosition(0, 0)
        self.setCurrentFile(fileName)
        self.changeLang(self.ui.langCombo.currentIndex())
        self.scheduleAutoUpdate()
        self._add_recent_file(fileName)

    def saveFile(self, fileName):
        """Write editor contents to disk."""
        try:
            Path(fileName).write_text(self.ui.editor.text(), encoding=getattr(self, "fileEncoding", "utf-8"))
        except (OSError, UnicodeError) as exc:
            LOGGER.exception("file_save_failed path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
            QMessageBox.warning(
                self,
                "Easy G-code Plot",
                "Cannot write file %s:\n%s." % (fileName, exc),
            )
            return False

        LOGGER.info("file_saved path=%s encoding=%s", fileName, getattr(self, "fileEncoding", "utf-8"))
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

    def export(self):
        """Export current program to a chosen file path."""
        path, _ = QFileDialog.getSaveFileName()
        if not path:
            return
        val = self.ui.horizontalSlider.value()
        if not self.updateData():
            return
        self.valueHandler(val)
        start = time.time()
        try:
            txt = self.exportPgm()
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(txt)
        except Exception as exc:  # Export/file-system errors are surfaced to the GUI.
            LOGGER.exception("export_failed path=%s", path)
            QMessageBox.warning(self, "Easy G-code Plot", str(exc))
            return
        end = time.time()
        LOGGER.info("export_completed path=%s duration_ms=%.3f", path, (end - start) * 1000)
        self.progressBar.setValue(0)
        self.ui.statusbar.showMessage(f"Export Execution time: {(end - start) * 1000:.3f} ms", 10000)

    def exportPgm(self):
        """Generate the exportable program text based on parsed toolpath data."""
        return export_pgm(self)

    def floatToStr(self, val):
        """Format numeric values to compact strings for G-code output."""
        return format_gcode_number(val)
