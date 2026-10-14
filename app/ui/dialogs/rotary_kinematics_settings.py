"""Transactional profile management for the Designer-backed Options tab."""

import json
from copy import deepcopy
from uuid import uuid4

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QInputDialog, QListWidgetItem, QMessageBox

from app.gcode.kernel.milling.kinematics import (
    builtin_profile_ids,
    load_catalog,
    parse_catalog,
    profile_document,
    save_user_profiles,
)
from app.settings import ROTARY_PROFILE_ENABLED_KEY, get_settings, load_rotary_profile_visibility

_REFERENCE_CHECKED_PROFILES = frozenset(
    {
        "4ax_table_a",
        "4ax_table_b",
        "4ax_table_c",
        "5ax_table_ac_angled",
        "5ax_table_bc_angled",
    }
)


class RotaryKinematicsSettings:
    def __init__(self, dialog):
        self.dialog = dialog
        self.ui = dialog.ui
        self.documents = {}
        self.original = {}
        self.selected = None
        self.builtins = builtin_profile_ids()
        self.rows = []
        self.limit_rows = [
            (getattr(self.ui, f"rotaryMin{number}Edit"), getattr(self.ui, f"rotaryMax{number}Edit"))
            for number in (1, 2)
        ]
        for number in (1, 2):
            branch = getattr(self.ui, f"rotaryBranch{number}Combo")
            address = getattr(self.ui, f"rotaryAddress{number}Combo")
            branch.addItem(QCoreApplication.translate("OptionsDlg", "Table"), "table")
            branch.addItem(QCoreApplication.translate("OptionsDlg", "Head"), "head")
            address.addItem(QCoreApplication.translate("OptionsDlg", "None"), None)
            for letter in "ABC":
                address.addItem(letter, letter)
            vectors = tuple(getattr(self.ui, f"rotary{letter}{number}Edit") for letter in "XYZ")
            self.rows.append((branch, address, vectors))
        self.ui.rotaryProfileSplitter.setStretchFactor(0, 0)
        self.ui.rotaryProfileSplitter.setStretchFactor(1, 1)
        self.ui.rotaryProfileSplitter.setSizes([230, 730])
        self.ui.rotaryProfileList.currentRowChanged.connect(self._selection_changed)
        self.ui.rotaryCopyButton.clicked.connect(self.copy_profile)
        self.ui.rotarySaveButton.clicked.connect(self.stage)
        self.ui.rotaryRenameButton.clicked.connect(self.rename_profile)
        self.ui.rotaryDeleteButton.clicked.connect(self.delete_profile)
        self.reload()

    @property
    def changed_ids(self):
        documents = {
            key
            for key in self.documents.keys() | self.original.keys()
            if self.documents.get(key) != self.original.get(key)
        }
        visibility = {
            key
            for key in self.visibility.keys() | self.original_visibility.keys()
            if self.visibility.get(key) != self.original_visibility.get(key)
        }
        return documents | visibility

    def reload(self):
        self.settings = getattr(self.dialog.parent(), "settings", None) or get_settings()
        self.visibility = load_rotary_profile_visibility(self.settings)
        self.original_visibility = dict(self.visibility)
        catalog = load_catalog(ignore_user_errors=True)
        self.documents = {key: profile_document(key) for key in catalog}
        self.original = deepcopy(self.documents)
        self.selected = None
        self._populate(next(iter(catalog), None))

    def profile_row(self, profile_id):
        profiles = self.ui.rotaryProfileList
        return next(
            (i for i in range(profiles.count()) if profiles.item(i).data(Qt.ItemDataRole.UserRole) == profile_id), -1
        )

    def _populate(self, selected):
        profiles = self.ui.rotaryProfileList
        blocked = profiles.blockSignals(True)
        profiles.clear()
        for key, item in sorted(self.documents.items()):
            suffix = QCoreApplication.translate("OptionsDlg", " (built-in)") if key in self.builtins else ""
            entry = QListWidgetItem(item["name"] + suffix)
            entry.setData(Qt.ItemDataRole.UserRole, key)
            entry.setToolTip(item["name"])
            profiles.addItem(entry)
        profiles.setCurrentRow(self.profile_row(selected))
        profiles.blockSignals(blocked)
        self.selected = selected
        self._display()

    def _selection_changed(self, row):
        profiles = self.ui.rotaryProfileList
        entry = profiles.item(row)
        selected = entry.data(Qt.ItemDataRole.UserRole) if entry is not None else None
        if not self.stage():
            blocked = profiles.blockSignals(True)
            profiles.setCurrentRow(self.profile_row(self.selected))
            profiles.blockSignals(blocked)
            return
        self.selected = selected
        self._display()

    def _display(self):
        item = self.documents.get(self.selected)
        if item is None:
            return
        editable = self.selected not in self.builtins
        self.ui.rotaryProfileIdLabel.setText(item["name"])
        self.ui.rotaryNameEdit.setText(item["name"])
        self.ui.rotaryNameEdit.setReadOnly(not editable)
        self.ui.rotaryEnabledCheck.setChecked(item["enabled"] if editable else self.visibility.get(self.selected, True))
        self.ui.rotaryAxis1Group.setEnabled(editable)
        self.ui.rotaryAxis2Group.setEnabled(editable)
        self.ui.rotaryRenameButton.setEnabled(editable)
        self.ui.rotarySaveButton.setEnabled(editable)
        self.ui.rotaryDeleteButton.setEnabled(editable)
        joints = [(branch, joint) for branch in ("table", "head") for joint in item[branch]]
        for row, (branch, address, vectors) in enumerate(self.rows):
            owner, joint = joints[row] if row < len(joints) else ("table", {"address": None, "axis": [0, 0, 1]})
            branch.setCurrentIndex(branch.findData(owner))
            address.setCurrentIndex(address.findData(joint["address"]))
            for edit, value in zip(vectors, joint["axis"], strict=True):
                edit.setText(str(value))
            self._display_limits(row, joint)
        if editable:
            status = QCoreApplication.translate("OptionsDlg", "User profile (unverified)")
        elif self.selected in _REFERENCE_CHECKED_PROFILES:
            status = QCoreApplication.translate("OptionsDlg", "Checked against reference programs (read-only)")
        else:
            status = QCoreApplication.translate("OptionsDlg", "Built-in profile (read-only; unverified)")
        self.ui.rotaryStatusLabel.setText(status)

    def _display_limits(self, row, joint):
        for edit, key in zip(self.limit_rows[row], ("min", "max"), strict=True):
            value = joint.get(key)
            edit.setText("" if value is None else str(value))

    def _edited_joint(self, row, address, vectors):
        joint = {"address": address.currentData(), "axis": [float(edit.text()) for edit in vectors]}
        for edit, key in zip(self.limit_rows[row], ("min", "max"), strict=True):
            value = edit.text().strip()
            if value:
                joint[key] = float(value)
        return joint

    def _edited_document(self):
        item = deepcopy(self.documents[self.selected])
        item.update(name=self.ui.rotaryNameEdit.text().strip(), enabled=self.ui.rotaryEnabledCheck.isChecked())
        item["table"], item["head"] = [], []
        for row, (branch, address, vectors) in enumerate(self.rows):
            if address.currentData() is None:
                continue
            item[branch.currentData()].append(self._edited_joint(row, address, vectors))
        parse_catalog({"schema_version": 1, "profiles": [item]})
        return item

    def stage(self):
        if self.selected is None:
            return True
        if self.selected in self.builtins:
            if self.ui.rotaryEnabledCheck.isChecked():
                self.visibility.pop(self.selected, None)
            else:
                self.visibility[self.selected] = False
            return True
        try:
            item = self._edited_document()
        except (ValueError, AttributeError) as exc:
            QMessageBox.warning(
                self.dialog,
                QCoreApplication.translate("OptionsDlg", "Rotary Kinematics"),
                QCoreApplication.translate("OptionsDlg", "Invalid profile parameters.") + "\n" + str(exc),
            )
            return False
        self.documents[self.selected] = item
        self.ui.rotaryProfileIdLabel.setText(item["name"])
        index = self.profile_row(self.selected)
        self.ui.rotaryProfileList.item(index).setText(item["name"])
        self.ui.rotaryProfileList.item(index).setToolTip(item["name"])
        return True

    def _ask_name(self, title, default):
        name, accepted = QInputDialog.getText(
            self.dialog,
            title,
            QCoreApplication.translate("OptionsDlg", "Profile name"),
            text=default,
        )
        if not accepted:
            return None
        if not name.strip():
            QMessageBox.warning(
                self.dialog, title, QCoreApplication.translate("OptionsDlg", "Profile name must not be empty")
            )
            return None
        return name.strip()

    def copy_profile(self):
        if not self.stage() or self.selected is None:
            return
        item = deepcopy(self.documents[self.selected])
        name = self._ask_name(
            QCoreApplication.translate("OptionsDlg", "Copy profile"),
            item["name"] + " " + QCoreApplication.translate("OptionsDlg", "(copy)"),
        )
        if name is None:
            return
        item["id"] = "user_" + uuid4().hex
        item["name"] = name
        self.documents[item["id"]] = item
        self._populate(item["id"])
        self.ui.rotaryNameEdit.setFocus()
        self.ui.rotaryNameEdit.selectAll()

    def rename_profile(self):
        if self.selected is None or self.selected in self.builtins:
            return
        name = self._ask_name(QCoreApplication.translate("OptionsDlg", "Rename"), self.ui.rotaryNameEdit.text())
        if name is not None:
            self.ui.rotaryNameEdit.setText(name)
            self.stage()

    def delete_profile(self):
        if self.selected is None or self.selected in self.builtins:
            return
        del self.documents[self.selected]
        self._populate(next(iter(self.documents), None))

    def apply(self):
        if not self.stage():
            return False
        if not self.changed_ids:
            return True
        try:
            if self.documents != self.original:
                save_user_profiles([item for key, item in self.documents.items() if key not in self.builtins])
            self.settings.setValue(ROTARY_PROFILE_ENABLED_KEY, json.dumps(self.visibility))
            window = self.dialog.parent()
            if window is not None:
                window.rotaryProfileEnabled = dict(self.visibility)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self.dialog, QCoreApplication.translate("OptionsDlg", "Rotary Kinematics"), str(exc))
            return False
        return True
