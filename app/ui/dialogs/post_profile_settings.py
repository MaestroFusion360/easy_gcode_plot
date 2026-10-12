"""Master/detail postprocessor editing inside application settings."""

from PyQt6.QtCore import QCoreApplication, QObject, QSignalBlocker, Qt
from PyQt6.QtWidgets import QInputDialog, QListWidgetItem, QMessageBox

from app.gcode.post_profiles import POST_TARGETS
from app.post_profile_library import BUILTIN_LABELS, PostProfileLibrary
from app.ui.dialogs.post_profile_editor import PostProfileEditor

_ENTRY_ROLE = Qt.ItemDataRole.UserRole


class PostProfileSettings(QObject):
    """Keep the catalog and editor together without additional editor dialogs."""

    def __init__(self, owner, library=None):
        super().__init__(owner)
        self.owner = owner
        self.ui = owner.ui
        self.library = library or PostProfileLibrary()
        self.editor = None
        self._active_row = -1
        for name, callback in (
            ("new", self._new),
            ("save", self.apply),
            ("rename", self._rename),
            ("remove", self._remove),
        ):
            getattr(self.ui, f"{name}PostProfileButton").clicked.connect(
                lambda _checked=False, fn=callback: self._run(fn)
            )
        self.ui.postProfileList.currentRowChanged.connect(self._selection_changed)
        self.ui.postProfileSplitter.setStretchFactor(0, 0)
        self.ui.postProfileSplitter.setStretchFactor(1, 1)
        self.ui.postProfileSplitter.setSizes([230, 730])
        self.reload()

    def reload(self, selection=None):
        widget = self.ui.postProfileList
        with QSignalBlocker(widget):
            widget.clear()
            for target in POST_TARGETS:
                label = QCoreApplication.translate("ExportOptDlg", "{0} (built-in)").format(
                    QCoreApplication.translate("ExportOptDlg", BUILTIN_LABELS[target])
                )
                self._add(label, "builtin", target)
            errors = []
            for entry in self.library.list_profiles():
                if entry.error:
                    errors.append(f"{entry.name}: {entry.error}")
                else:
                    self._add(entry.name, "user", entry.path)
            row = next((i for i in range(widget.count()) if widget.item(i).data(_ENTRY_ROLE)[1] == selection), 0)
            widget.setCurrentRow(row)
        self._activate(row)
        self.ui.postProfileErrorLabel.setText("\n".join(errors))

    def _add(self, label, kind, target):
        item = QListWidgetItem(label)
        item.setData(_ENTRY_ROLE, (kind, target))
        self.ui.postProfileList.addItem(item)

    def _selected(self):
        item = self.ui.postProfileList.currentItem()
        return item.data(_ENTRY_ROLE) if item else (None, None)

    def _activate(self, row, profile=None):
        self._active_row = row
        kind, target = self._selected()
        if self.editor is not None:
            self.ui.postProfileEditorLayout.removeWidget(self.editor)
            self.editor.deleteLater()
        self.editor = PostProfileEditor(
            self.library,
            target if kind == "user" else None,
            self.ui.postProfileEditorHost,
            profile=(profile or target) if kind == "draft" else self.library.load(target),
            read_only=kind == "builtin",
        )
        self.ui.postProfileEditorLayout.addWidget(self.editor)
        for name in ("save", "rename", "remove"):
            getattr(self.ui, f"{name}PostProfileButton").setEnabled(kind != "builtin")
        self.ui.postProfileErrorLabel.clear()

    def _selection_changed(self, row):
        if row == self._active_row:
            return
        if not self._resolve_dirty():
            with QSignalBlocker(self.ui.postProfileList):
                self.ui.postProfileList.setCurrentRow(self._active_row)
            return
        self._run(lambda: self._activate(row))

    def _resolve_dirty(self):
        if self.editor is None or not self.editor.is_dirty():
            return True
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self.owner,
            self.tr("Postprocessors"),
            self.tr("Save changes to this postprocessor?"),
            buttons.Save | buttons.Discard | buttons.Cancel,
            buttons.Save,
        )
        if answer == buttons.Cancel:
            return False
        return answer != buttons.Save or self.apply()

    def _run(self, callback):
        try:
            return callback()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.ui.postProfileErrorLabel.setText(str(exc))
            return False

    def apply(self):
        """Save pending edits when Save or the settings OK button is pressed."""
        if self.editor is None or not self.editor.is_dirty():
            return True
        path = self._run(self.editor.save)
        if not path:
            return False
        item = self.ui.postProfileList.item(self._active_row)
        item.setData(_ENTRY_ROLE, ("user", path))
        item.setText(self.library.name(self.editor.current_profile(), path))
        self.ui.postProfileErrorLabel.clear()
        self._refresh_export()
        return True

    def discard(self):
        """Drop unsaved edits and drafts when settings are cancelled."""
        self.reload()

    def _new(self):
        if not self._resolve_dirty():
            return
        profile = self.editor.current_profile()
        profile["name"] = QCoreApplication.translate("ExportOptDlg", "{0} copy").format(
            self.library.name(profile, profile["id"])
        )
        with QSignalBlocker(self.ui.postProfileList):
            self._add(profile["name"], "draft", profile)
            self.ui.postProfileList.setCurrentRow(self.ui.postProfileList.count() - 1)
        self._activate(self.ui.postProfileList.currentRow(), profile)
        self.editor.ui.nameEdit.setFocus()
        self.editor.ui.nameEdit.selectAll()

    def _rename(self):
        if self.editor.read_only:
            return
        name, accepted = QInputDialog.getText(
            self.owner, self.tr("Postprocessors"), self.tr("Profile name"), text=self.editor.ui.nameEdit.text()
        )
        if accepted:
            if not name.strip():
                raise ValueError(self.tr("Profile name must not be empty"))
            self.editor.ui.nameEdit.setText(name.strip())

    def _remove(self):
        if self.editor.read_only:
            return
        if (
            QMessageBox.question(self.owner, self.tr("Postprocessors"), self.tr("Remove this user profile?"))
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.editor.path:
            self.library.remove(self.editor.path)
        self.reload()
        self._refresh_export()

    def _refresh_export(self):
        window = self.owner.parent()
        if window is not None and hasattr(window, "exportDlg"):
            window.exportDlg.reload_post_profiles()
