"""Native compact tool recognition settings, using the Options form layout."""

import re
from copy import deepcopy
from html import escape

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QHeaderView, QListWidgetItem, QMessageBox, QTableWidgetItem

from app.tools.definitions import MILLING_TOOL_LABELS, TURNING_TOOL_LABELS
from app.tools.discovery import discover_tools
from app.tools.discovery_patterns import type_hint
from app.tools.discovery_rules import (
    DEFAULT_DIMENSIONS,
    default_profile,
    default_settings,
    validate_profile,
    validate_settings,
)

NAME_LABELS = {
    "mill_flat": "FLAT MILL; SQUARE MILL; END MILL; MILL FLAT",
    "mill_bull": "BULL; BULL NOSE; CORNER RADIUS; RADIUS END MILL; TOROIDAL; MILL BULL",
    "mill_ball": "BALL; BALL NOSE; SPHERICAL",
    "taper_ball_mill": "TAPER BALL; TAPERED BALL; TAPER SPHERICAL; TAPERED SPHERICAL",
    "face_mill": "FACE MILL; SHELL MILL; MILL FACE",
    "slot_mill": "SLOT MILL; DISC MILL; DISK MILL; T SLOT; WOODRUFF; KEYSEAT CUTTER; SLITTING SAW",
    "chamfer_mill": "CHAMFER; COUNTERSINK; CSINK; V BIT; V MILL",
    "drill": "DRILL; DRILLING",
    "tap": "TAP; TAPPING",
    "thread": "THREAD; THREADING",
    "groove": "GROOVE; GROOVING",
}
PARAMETERS = {
    "milling_diameter": ("Diameter", "D; DIA; DIAM; DIAMETER; Ø; ⌀"),
    "corner_radius": ("Corner radius", "CR; RE; CORNER RADIUS"),
    "flute_length": ("Flute length", "FL; FLUTELENGTH; FLUTE LENGTH"),
    "body_length": ("Body length", "BL; BODYLENGTH; BODY LENGTH"),
    "total_length": ("Total length", "L; LENGTH"),
    "taper_angle": ("Taper angle", "TAPER ANGLE; TAPER; ANGLE; B"),
    "tip_angle": ("Point angle", "TIP ANGLE; POINT ANGLE; TAPER; ANGLE"),
    "chamfer_angle": ("Chamfer angle", "CHAMFER ANGLE; TAPER; ANGLE"),
    "tip_diameter": ("Tip diameter", "TIP DIAMETER; TIP DIA; TIP D; TD"),
    "shank_diameter": ("Shank diameter", "SHANK DIAMETER; SHANK DIA; SHANK D; SD"),
    "nose_radius": ("Nose radius", "R; NR"),
    "groove_width": ("Groove width", "H; W; WIDTH"),
    "turning_diameter": ("Diameter", "D; DIA; DIAMETER"),
}


def _aliases_pattern(text, *, names=False):
    words = [word.strip().upper() for word in re.split(r"[;\n]", text) if word.strip()]
    alternatives = [r"\s+".join(re.escape(part) for part in word.split()) for word in words]
    joined = "|".join(alternatives)
    return rf"\b(?:{joined})\b" if names and joined else joined


def _display_pattern(pattern, default, summary, *, names=False):
    if pattern == default:
        return summary, False
    value = pattern
    if names and value.startswith(r"\b(?:") and value.endswith(r")\b"):
        value = value[5:-3]
    terms = value.split("|")
    decoded = [term.replace(r"\s+", " ") for term in terms]
    if all(re.fullmatch(r"[A-Z0-9 Ø⌀.]+", term) for term in decoded):
        shown = "; ".join(decoded)
        if _aliases_pattern(shown, names=names) == pattern:
            return shown, False
    return pattern, bool(pattern)


class DiscoverySettings(QObject):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.modeCombo = owner.ui.discoveryModeCombo
        self.regexCheck = owner.ui.discoveryRegexCheck
        self.typesList = owner.ui.discoveryTypesList
        self.namesEdit = owner.ui.discoveryNamesEdit
        self.parameterTable = owner.ui.discoveryParameterTable
        self.sample = owner.ui.discoveryCommentEdit
        self.preview = owner.ui.discoveryResultLabel
        self.status = owner.ui.discoveryErrorLabel
        self.testButton = owner.ui.discoveryTestButton
        self.parameterTable.verticalHeader().hide()
        self.parameterTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.parameterTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        owner.ui.discoverySplitter.setSizes([220, 760])
        owner.ui.discoverySplitter.setStretchFactor(0, 0)
        owner.ui.discoverySplitter.setStretchFactor(1, 1)
        owner.ui.discoverySplitter.setChildrenCollapsible(False)
        self.modeCombo.currentIndexChanged.connect(self._populate_tools)
        self.regexCheck.toggled.connect(self._show_parameters)
        self.typesList.currentRowChanged.connect(self._show_parameters)
        self.namesEdit.textChanged.connect(self._save_name)
        self.parameterTable.itemChanged.connect(self._save_parameter)
        self.testButton.clicked.connect(self.test_comment)
        self.load(default_settings())

    def load(self, document):
        self.document = deepcopy(document)
        self._profile = deepcopy(document)
        self._populate_tools()

    def current_profile(self):
        return deepcopy(self._profile)

    def _kind(self):
        return self.typesList.currentItem().data(Qt.ItemDataRole.UserRole)

    def _populate_tools(self):
        labels = TURNING_TOOL_LABELS if self.modeCombo.currentIndex() else MILLING_TOOL_LABELS
        blocked = self.typesList.blockSignals(True)
        self.typesList.clear()
        for kind, label in labels.items():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, kind)
            self.typesList.addItem(item)
        self.typesList.setCurrentRow(0)
        self.typesList.blockSignals(blocked)
        self.sample.setPlaceholderText("GROOVE R0.4 W3" if self.modeCombo.currentIndex() else "END MILL D10 FL30")
        self._show_parameters()

    def _show_names(self):
        kind = self._kind()
        defaults = {kind: pattern for pattern, kind in default_profile()["types"]}
        value = next(pattern for pattern, name in self._profile["types"] if name == kind)
        shown, self._name_raw = self._presentation(value, defaults[kind], NAME_LABELS.get(kind, ""), names=True)
        self.owner.ui.discoveryNamesLabel.setText(
            self.tr("Tool names / Regular expression") if self._name_raw else self.tr("Tool names / Aliases")
        )
        blocked = self.namesEdit.blockSignals(True)
        self.namesEdit.setPlainText(shown if self._name_raw else shown.replace("; ", "\n"))
        self.namesEdit.blockSignals(blocked)
        hint = self.tr("Edit the regular expression. Complex rules remain expressions in either mode.")
        if not self._name_raw:
            hint = self.tr("Enter one name per line. An empty list disables name recognition for this type.")
        self.owner.ui.discoveryFormatLabel.setText(hint)
        self.namesEdit.setToolTip(hint)
        self.namesEdit.setPlaceholderText(hint)

    def _presentation(self, value, default, summary, *, names=False):
        if self.regexCheck.isChecked():
            return value, True
        return _display_pattern(value, default, summary, names=names)

    def _parameter_keys(self):
        kind = self._kind()
        if self.modeCombo.currentIndex():
            if kind in {"drill", "tap"}:
                return ["turning_diameter"]
            return ["nose_radius", "groove_width"] if kind == "groove" else ["nose_radius"]
        keys = ["milling_diameter", "flute_length", "body_length", "total_length"]
        extra = {
            "mill_flat": ["corner_radius"],
            "mill_bull": ["corner_radius"],
            "taper_ball_mill": ["taper_angle"],
            "drill": ["tip_angle"],
            "chamfer_mill": ["chamfer_angle", "tip_diameter"],
            "face_mill": ["shank_diameter"],
            "slot_mill": ["shank_diameter"],
        }
        return keys + extra.get(kind, [])

    def _show_parameters(self, *_args):
        self._show_names()
        keys = self._parameter_keys()
        blocked = self.parameterTable.blockSignals(True)
        self.parameterTable.setRowCount(len(keys))
        for row, key in enumerate(keys):
            label = QTableWidgetItem(PARAMETERS[key][0])
            label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            label.setData(Qt.ItemDataRole.UserRole, key)
            self.parameterTable.setItem(row, 0, label)
            value = self._profile["dimensions"][key]
            shown, raw = self._presentation(value, DEFAULT_DIMENSIONS[key], PARAMETERS[key][1])
            item = QTableWidgetItem(shown)
            item.setData(Qt.ItemDataRole.UserRole, raw)
            item.setToolTip(
                self.tr("Regular expression") + ": " + value if raw else self.tr("Edit labels separated by semicolons.")
            )
            self.parameterTable.setItem(row, 1, item)
        self.parameterTable.blockSignals(blocked)
        self._check_draft()

    def _save_name(self):
        kind = self._kind()
        text = self.namesEdit.toPlainText()
        pattern = text if self._name_raw else _aliases_pattern(text, names=True)
        for entry in self._profile["types"]:
            if entry[1] == kind:
                entry[0] = pattern
        self._check_draft()

    def _save_parameter(self, item):
        if item.column() == 1:
            key = self.parameterTable.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
            self._profile["dimensions"][key] = (
                item.text() if item.data(Qt.ItemDataRole.UserRole) else _aliases_pattern(item.text())
            )
            self._check_draft()

    def _check_draft(self):
        try:
            validate_profile(self.current_profile())
        except ValueError as exc:
            self.status.setText(str(exc))
        else:
            self.status.clear()
        self.preview.clear()

    def restore_defaults(self):
        self.load(default_settings())

    def validate(self):
        try:
            self.document = validate_settings(self._profile)
        except ValueError as exc:
            QMessageBox.warning(self.owner, "Tool Discovery", str(exc))
            return False
        return True

    def test_comment(self):
        try:
            profile = validate_profile(self.current_profile())
            turning = bool(self.modeCombo.currentIndex())
            key = "T4242" if turning else "T42"
            tool = discover_tools(
                f"{key}{'' if turning else ' M6'} ({self.sample.text()})",
                turning=turning,
                rules=profile,
                default_unit_scale=25.4 if self.owner.parent().defaultUnits == "inch" else 1.0,
            )[key]
            labels = TURNING_TOOL_LABELS if turning else MILLING_TOOL_LABELS
            hint = type_hint(self.sample.text(), tuple(tuple(entry) for entry in profile["types"]))
            result = labels[tool["type"]] + ("" if hint in labels else " (default)")
            fields = {
                "diameter": "Diameter",
                "noseRadius": "Nose radius",
                "width": "Groove width",
                "cornerRadius": "Corner radius",
                "fluteLength": "Flute length",
                "bodyLength": "Body length",
                "length": "Total length",
                "taperAngle": "Taper angle",
                "tipAngle": "Point angle",
                "chamferAngle": "Chamfer angle",
                "tipDiameter": "Tip diameter",
                "shankDiameter": "Shank diameter",
            }
            details = [
                f"{escape(self.tr(label))}: {tool[field]:g} {'deg' if field.endswith('Angle') else 'mm'}"
                for field, label in fields.items()
                if field in tool
            ]
            self.preview.setText(f"<b>{escape(result)}</b><br>" + " &nbsp; | &nbsp; ".join(details))
            self.status.clear()
        except (KeyError, ValueError) as exc:
            self.preview.clear()
            self.status.setText(str(exc))
