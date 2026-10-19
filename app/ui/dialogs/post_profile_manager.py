"""Select existing postprocessors and import ready JSON profiles for export."""

from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QSignalBlocker
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from app.gcode.export import EXPANDED_EXECUTION_MODE
from app.gcode.post_profiles import target_post_for_index
from app.post_profile_library import BUILTIN_LABELS, PostProfileLibrary


class PostProfileManagementMixin:
    """Bind the Export Options target selector to the shared profile library."""

    def _init_post_profiles(self):
        self.postLibrary = PostProfileLibrary()
        self.ui.postProfileButton.clicked.connect(self._import_post_profile)
        self.targetCncCombo.currentIndexChanged.connect(self._update_post_actions)
        self._post_machine = None

    def _machine_type(self):
        return "lathe" if self.parent().latheMode else "mill"

    def _saved_post_selection(self):
        selection = getattr(self.parent(), "exportPostProfile", "")
        if selection:
            return selection
        return target_post_for_index(self.parent().exportTargetCnc, turning=self.parent().latheMode) or "auto"

    def reload_post_profiles(self, selection=None):
        selection = selection or self.targetCncCombo.currentData() or "auto"
        machine = self._machine_type()
        self._post_machine = machine
        combo = self.targetCncCombo
        with QSignalBlocker(combo):
            combo.clear()
            combo.addItem(QCoreApplication.translate("ExportOptDlg", "Auto (source controller)"), "auto")
            for target, label in BUILTIN_LABELS.items():
                if self.postLibrary.load(target)["machine"] == machine:
                    combo.addItem(QCoreApplication.translate("ExportOptDlg", label), target)
            errors = []
            for entry in self.postLibrary.list_profiles():
                if entry.machine == machine:
                    combo.addItem(
                        QCoreApplication.translate("ExportOptDlg", "User: {0}").format(entry.name), entry.path
                    )
                elif entry.error:
                    errors.append(f"{entry.name}: {entry.error}")
            index = combo.findData(selection)
            if index < 0:
                combo.addItem(
                    QCoreApplication.translate("ExportOptDlg", "Unavailable: {0}").format(Path(selection).name),
                    selection,
                )
                index = combo.count() - 1
            combo.setCurrentIndex(index)
        self._post_errors = "\n".join(errors)
        self._update_post_actions()

    def _import_post_profile(self):
        source, _filter = QFileDialog.getOpenFileName(
            self, QCoreApplication.translate("ExportOptDlg", "Import postprocessor"), "", "JSON (*.json)"
        )
        if not source:
            return
        try:
            path = self.postLibrary.import_profile(source, machine=self._machine_type())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, QCoreApplication.translate("ExportOptDlg", "Postprocessors"), str(exc))
            return
        self.reload_post_profiles(path)

    def _update_post_actions(self, _index=None):
        expanded = self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE
        self.ui.postProfileButton.setEnabled(expanded)
        self.ui.postProfileWarning.setText(getattr(self, "_post_errors", ""))
        self.ui.postProfileWarning.setVisible(expanded and bool(self.ui.postProfileWarning.text()))
        self._check_post_selection()

    def _check_post_selection(self):
        target = self.targetCncCombo.currentData()
        if not target or target == "auto":
            return
        try:
            self._validate_selected_post()
        except (OSError, ValueError) as exc:
            self.ui.postProfileWarning.setText(
                QCoreApplication.translate(
                    "ExportOptDlg", "Selected postprocessor is unavailable: {0}\nSelect Auto or another valid profile."
                ).format(exc)
            )
            self.ui.postProfileWarning.setVisible(self.ui.langCmbBox.currentIndex() == EXPANDED_EXECUTION_MODE)

    def _validate_selected_post(self):
        target = self.targetCncCombo.currentData()
        if target and target != "auto":
            profile = self.postLibrary.load(target)
            if profile["machine"] != self._machine_type():
                raise ValueError(
                    QCoreApplication.translate(
                        "ExportOptDlg", "The selected postprocessor does not match the current machine type"
                    )
                )
        return target or "auto"
