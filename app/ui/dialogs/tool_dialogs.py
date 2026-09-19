"""Tool geometry editors used by the unified Tool Library."""

import csv
import json
from pathlib import Path

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QButtonGroup, QDialog, QMessageBox

from app.tools.definitions import (
    AUTO_TIP_ORIENTATIONS,
    AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION,
    DEFAULT_AUTO_TIP_ORIENTATION,
    DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION,
    MILLING_TOOL_LABELS,
    TURNING_APPLICATIONS,
    TURNING_INSERT_TYPES,
    TURNING_TOOL_LABELS,
    tool_applications,
)
from app.tools.milling_geometry import (
    default_cutting_height,
    default_drill_tip_angle,
    default_shank_diameter,
    default_tip_diameter,
)
from app.ui.generated.editors.milling_tool_editor import Ui_MillingToolEditor
from app.ui.generated.editors.turning_tool_editor import Ui_TurningToolEditor
from app.ui.support.units import metric_value, register_length_spinboxes, set_length_units, set_metric_value


def _initialize_tool_editor(editor, parent, tool_code):
    editor.reservedCodes = set(getattr(parent, "reservedCodes", getattr(parent, "pendingTools", {}))) - {tool_code}


def _accept_unique_tool(editor):
    key, _spec = editor.value()
    if key in editor.reservedCodes:
        QMessageBox.warning(
            editor,
            QCoreApplication.translate("ToolLibraryDialog", "Duplicate tool number"),
            QCoreApplication.translate("ToolLibraryDialog", "{0} already exists. Choose a different number.").format(
                key
            ),
        )
        return
    editor.accept()


def _export_tool_library(path: str, kind: str, tools: dict[str, dict]) -> None:
    """Export the complete saved library for one machine kind as JSON or CSV."""
    target = Path(path)
    records = [{"tool": key, **tools[key]} for key in sorted(tools)]
    if target.suffix.lower() == ".csv":
        preferred = ["tool", "type", "description"]
        extra = sorted({field for record in records for field in record} - set(preferred))
        fieldnames = [field for field in preferred if any(field in record for record in records)] + extra
        # Keep an empty-library CSV useful and structurally valid.
        if not fieldnames:
            fieldnames = ["tool", "type", "description"]
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return
    payload = {"library": kind, "tools": records}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_TURNING_INSERT_ORDER = ("diamond_80", "diamond_35", "square", "round", "triangle")


def _turning_category(tool_type: str) -> str:
    if tool_type in TURNING_INSERT_TYPES:
        return "insert"
    if tool_type == "groove":
        return "groove"
    if tool_type == "thread":
        return "thread"
    if tool_type == "drill":
        return "drill"
    if tool_type == "tap":
        return "tap"
    return "insert"


def _directions_for_tool(spec: dict[str, object]) -> set[str]:
    applications = set(tool_applications(spec))
    if applications:
        return applications
    tool_type = str(spec.get("type", ""))
    orientation = spec.get("tipOrientation")
    by_direction = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(tool_type, {})
    matching = {direction for direction, orientations in by_direction.items() if orientation in orientations}
    if matching:
        return matching
    if orientation in (1, 2):
        return {"id"}
    if orientation in (6, 7):
        return {"face"}
    return {"od"}


class _TurningToolEditor(QDialog):
    """Category-oriented turning editor backed by a Designer form."""

    def __init__(self, parent=None, tool_code=None, spec=None):
        super().__init__(parent)
        _initialize_tool_editor(self, parent, tool_code)
        self.ui = Ui_TurningToolEditor()
        self.ui.setupUi(self)
        spec = spec or {}
        self._updating = True
        self._initial_type = str(spec.get("type", "diamond_80"))
        self._initial_tip_orientation = int(spec["tipOrientation"]) if "tipOrientation" in spec else None
        self.setWindowTitle(
            QCoreApplication.translate("ToolLibraryDialog", "Edit Tool")
            if tool_code
            else QCoreApplication.translate("ToolLibraryDialog", "Add Tool")
        )
        self.setModal(True)

        self.toolCode = self.ui.toolCode
        self.categoryGroup = QButtonGroup(self)
        self.categoryButtons = {
            "insert": self.ui.insertCategoryButton,
            "groove": self.ui.grooveCategoryButton,
            "thread": self.ui.threadCategoryButton,
            "drill": self.ui.drillCategoryButton,
            "tap": self.ui.tapCategoryButton,
        }
        for button in self.categoryButtons.values():
            self.categoryGroup.addButton(button)
        self.directionChecks = {"od": self.ui.odCheck, "id": self.ui.idCheck, "face": self.ui.faceCheck}
        self.insertType = self.ui.insertType
        self.grooveType = self.ui.grooveType
        self.threadType = self.ui.threadType
        self.drillType = self.ui.drillType
        self.tapType = self.ui.tapType
        self.toolType = self.insertType
        self.noseRadius = self.ui.noseRadius
        self.tipOrientation = self.ui.tipOrientation
        self.insertLength = self.ui.insertLength
        self.width = self.ui.width
        self.diameter = self.ui.diameter
        self.length = self.ui.length
        self.tipAngle = self.ui.tipAngle
        self.threadAngle = self.ui.threadAngle
        self.threadTipWidth = self.ui.threadTipWidth
        self.threadCornerRadius = self.ui.threadCornerRadius
        self.threadHelp = self.ui.threadHelp
        self.description = self.ui.description
        self.inches = self.ui.inchesCheck
        self.buttonBox = self.ui.buttonBox
        self._form = self.ui.formLayout
        self._length_controls = (
            self.noseRadius,
            self.insertLength,
            self.width,
            self.diameter,
            self.length,
            self.threadTipWidth,
            self.threadCornerRadius,
        )
        register_length_spinboxes(self._length_controls)
        self._length_labels = {
            self.ui.noseRadiusLabel: "Nose radius",
            self.ui.insertLengthLabel: "Length/Diameter",
            self.ui.widthLabel: "Groove width",
            self.ui.diameterLabel: "Tool diameter",
            self.ui.lengthLabel: "Tool length",
            self.ui.threadTipWidthLabel: "EX",
            self.ui.threadCornerRadiusLabel: "RC",
        }

        self.toolCode.setText(tool_code or "T0101")
        self.threadType.addItem(TURNING_TOOL_LABELS["thread"], "thread")
        self.drillType.addItem(TURNING_TOOL_LABELS["drill"], "drill")
        self.tapType.addItem(TURNING_TOOL_LABELS["tap"], "tap")
        self.noseRadius.setValue(float(spec.get("noseRadius", 0.4)))
        self.insertLength.setValue(float(spec.get("insertLength", self._default_insert_length(self._initial_type))))
        self.width.setValue(float(spec.get("width", 3.0)))
        self.diameter.setValue(float(spec.get("diameter", 10.0)))
        self.length.setValue(float(spec.get("length", 50.0)))
        self.tipAngle.setValue(float(spec.get("tipAngle", 118.0)))
        self.threadAngle.setValue(float(spec.get("threadAngle", 60.0)))
        self.threadTipWidth.setValue(float(spec.get("threadTipWidth", 0.8)))
        self.threadCornerRadius.setValue(float(spec.get("threadCornerRadius", 0.1)))
        self.description.setText(str(spec.get("description", "")))

        self.inches.toggled.connect(self._set_units)
        self.buttonBox.accepted.connect(self.validateAndAccept)
        self.buttonBox.rejected.connect(self.reject)
        category = _turning_category(self._initial_type)
        self.categoryButtons[category].setChecked(True)
        initial_spec = {**spec, "type": self._initial_type}
        for direction in _directions_for_tool(initial_spec):
            self.directionChecks[direction].setChecked(True)
        self._refresh_type_choices(self._initial_type)
        self._last_insert_type = self.insertType.currentData()
        self._connect_signals()
        self._updating = False
        self.updateTurningFields()
        self.toolCode.selectAll()
        self.toolCode.setFocus()

    def _set_units(self, inches: bool):
        set_length_units(self._length_controls, bool(inches), suffix=False)
        unit = "in" if inches else "mm"
        for label, text in self._length_labels.items():
            label.setText(f"{text}, {unit}")

    @staticmethod
    def _default_insert_length(tool_type) -> float:
        return 16.0 if tool_type == "diamond_35" else 12.0

    def _connect_signals(self):
        for button in self.categoryButtons.values():
            button.toggled.connect(self.updateTurningFields)
        for checkbox in self.directionChecks.values():
            checkbox.toggled.connect(self._direction_changed)
        self.insertType.currentIndexChanged.connect(self._insert_type_changed)
        self.grooveType.currentIndexChanged.connect(self.updateTurningFields)

    def _insert_type_changed(self, *_args):
        tool_type = self.insertType.currentData()
        previous = getattr(self, "_last_insert_type", None)
        if tool_type is not None and (
            previous is None or abs(metric_value(self.insertLength) - self._default_insert_length(previous)) < 1e-9
        ):
            set_metric_value(self.insertLength, self._default_insert_length(tool_type))
        self._last_insert_type = tool_type
        self.updateTurningFields()

    def category(self) -> str:
        return next((key for key, button in self.categoryButtons.items() if button.isChecked()), "insert")

    def selectedDirections(self) -> set[str]:
        return {key for key, checkbox in self.directionChecks.items() if checkbox.isChecked()}

    def currentToolType(self):
        combo = {
            "insert": self.insertType,
            "groove": self.grooveType,
            "thread": self.threadType,
            "drill": self.drillType,
            "tap": self.tapType,
        }.get(self.category())
        return combo.currentData() if combo is not None else None

    def serializedToolType(self):
        """Return the canonical geometry type; applicability is serialized separately."""
        return self.currentToolType()

    def _direction_changed(self, *_args):
        if self._updating:
            return
        if not self.selectedDirections():
            self._updating = True
            self.directionChecks["od"].setChecked(True)
            self._updating = False
        self._refresh_type_choices(self.currentToolType())
        self.updateTurningFields()

    def _refresh_type_choices(self, requested_type=None):
        directions = self.selectedDirections() or {"od"}
        insert_directions = directions & {"od", "id"} or {"od"}
        requested_type = str(requested_type or "")
        insert_types = [
            tool_type
            for tool_type in _TURNING_INSERT_ORDER
            if set(AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION[tool_type]) & insert_directions
        ]
        groove_types = ["groove"] if directions else []
        self._populate_combo(self.insertType, insert_types, requested_type)
        self._populate_combo(self.grooveType, groove_types, requested_type)

    @staticmethod
    def _populate_combo(combo, tool_types, requested_type):
        combo.blockSignals(True)
        combo.clear()
        for tool_type in tool_types:
            combo.addItem(TURNING_TOOL_LABELS[tool_type], tool_type)
        selected = combo.findData(requested_type)
        combo.setCurrentIndex(selected if selected >= 0 else (0 if combo.count() else -1))
        combo.blockSignals(False)

    def updateTurningFields(self, *_args):
        if self._updating:
            return
        category = self.category()
        directional = category in {"insert", "groove", "thread"}
        for checkbox in self.directionChecks.values():
            checkbox.setEnabled(directional)
        self._refresh_type_choices(self.currentToolType())
        for name, combo in (
            ("insert", self.insertType),
            ("groove", self.grooveType),
            ("thread", self.threadType),
            ("drill", self.drillType),
            ("tap", self.tapType),
        ):
            self._set_row_visible(combo, category == name)
        tool_type = self.currentToolType()
        insert = category == "insert" and tool_type in TURNING_INSERT_TYPES
        groove = category == "groove" and tool_type == "groove"
        thread = category == "thread" and tool_type == "thread"
        axial = category in {"drill", "tap"}
        self._set_row_visible(self.noseRadius, insert or groove)
        self._set_row_visible(self.tipOrientation, insert or groove or thread)
        self._set_row_visible(self.insertLength, insert or thread)
        self._set_row_visible(self.width, groove)
        self._set_row_visible(self.diameter, axial)
        self._set_row_visible(self.length, axial)
        self._set_row_visible(self.tipAngle, axial)
        self._set_row_visible(self.threadHelp, thread)
        self._set_row_visible(self.threadAngle, thread)
        self._set_row_visible(self.threadTipWidth, thread)
        self._set_row_visible(self.threadCornerRadius, thread)
        self._sync_tip_orientation_choices(tool_type)

    def _set_row_visible(self, widget, visible):
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _sync_tip_orientation_choices(self, tool_type):
        by_direction = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(tool_type)
        if by_direction is not None:
            directions = self.selectedDirections() or {"od"}
            if tool_type != "groove":
                directions = directions & {"od", "id"} or {"od"}
            choices = tuple(
                sorted({orientation for direction in directions for orientation in by_direction.get(direction, ())})
            )
            if not choices:
                choices = AUTO_TIP_ORIENTATIONS[tool_type]
            preferred = DEFAULT_AUTO_TIP_ORIENTATION[tool_type]
            if len(directions) == 1:
                direction = next(iter(directions))
                preferred = DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION[tool_type].get(direction, preferred)
            default = preferred if preferred in choices else choices[0]
        else:
            choices, default = (), 1
        current = self.tipOrientation.currentData()
        requested = self._initial_tip_orientation if self._initial_tip_orientation is not None else current
        orientation = int(requested) if requested is not None and int(requested) in choices else default
        self.tipOrientation.blockSignals(True)
        self.tipOrientation.clear()
        for value in choices:
            self.tipOrientation.addItem(QIcon(f":/resource/icons/orientation_box/P{value}.png"), f"P{value}", value)
        self.tipOrientation.setCurrentIndex(self.tipOrientation.findData(orientation))
        self.tipOrientation.blockSignals(False)
        self._initial_tip_orientation = None

    def validateAndAccept(self):
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or not 1 <= len(digits) <= 4:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "T code must contain 1 to 4 digits."),
            )
            return
        if self.currentToolType() is None:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "Select an available tool type."),
            )
            return
        _accept_unique_tool(self)

    def value(self):
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits):04d}"
        tool_type = self.serializedToolType()
        spec = {"type": tool_type}
        description = " ".join(self.description.text().split())
        if description:
            spec["description"] = description
        if tool_type in TURNING_INSERT_TYPES:
            selected = self.selectedDirections() & {"od", "id"}
            spec["applications"] = [item for item in TURNING_APPLICATIONS if item in selected]
            spec.update(
                noseRadius=metric_value(self.noseRadius),
                tipOrientation=int(self.tipOrientation.currentData()),
                insertLength=metric_value(self.insertLength),
            )
        elif tool_type == "groove":
            selected = self.selectedDirections()
            spec["applications"] = [item for item in TURNING_APPLICATIONS if item in selected]
            spec.update(
                width=metric_value(self.width),
                noseRadius=metric_value(self.noseRadius),
                tipOrientation=int(self.tipOrientation.currentData()),
            )
        elif tool_type == "thread":
            selected = self.selectedDirections() & {"od", "id"}
            spec["applications"] = [item for item in TURNING_APPLICATIONS if item in selected]
            spec.update(
                insertLength=metric_value(self.insertLength),
                threadAngle=self.threadAngle.value(),
                threadTipWidth=metric_value(self.threadTipWidth),
                threadCornerRadius=metric_value(self.threadCornerRadius),
                tipOrientation=int(self.tipOrientation.currentData()),
            )
        elif tool_type in {"drill", "tap"}:
            spec.update(
                diameter=metric_value(self.diameter),
                length=metric_value(self.length),
                tipAngle=self.tipAngle.value(),
            )
        return key, spec


_MILLING_TOOL_TYPES = MILLING_TOOL_LABELS


class _MillingToolEditor(QDialog):
    """Milling geometry editor backed by a Designer form."""

    def __init__(self, parent=None, tool_code=None, spec=None):
        super().__init__(parent)
        _initialize_tool_editor(self, parent, tool_code)
        self.ui = Ui_MillingToolEditor()
        self.ui.setupUi(self)
        spec = spec or {}
        self.setWindowTitle(
            QCoreApplication.translate("ToolLibraryDialog", "Edit Milling Tool")
            if tool_code
            else QCoreApplication.translate("ToolLibraryDialog", "Add Milling Tool")
        )
        self.setModal(True)

        self.toolCode = self.ui.toolCode
        self.toolType = self.ui.toolType
        self.diameter = self.ui.diameter
        self.cornerRadius = self.ui.cornerRadius
        self.length = self.ui.length
        self.cuttingHeight = self.ui.cuttingHeight
        self.shankDiameter = self.ui.shankDiameter
        self.tipDiameter = self.ui.tipDiameter
        self.chamferAngle = self.ui.chamferAngle
        self.tipAngle = self.ui.tipAngle
        self.description = self.ui.description
        self.inches = self.ui.inchesCheck
        self.buttonBox = self.ui.buttonBox
        self._length_controls = (
            self.diameter,
            self.cornerRadius,
            self.length,
            self.cuttingHeight,
            self.shankDiameter,
            self.tipDiameter,
        )
        register_length_spinboxes(self._length_controls)
        self._length_labels = {
            self.ui.diameterLabel: "Diameter",
            self.ui.cornerRadiusLabel: "Corner radius",
            self.ui.lengthLabel: "Length",
            self.ui.cuttingHeightLabel: "Cutting height",
            self.ui.shankDiameterLabel: "Shank diameter",
            self.ui.tipDiameterLabel: "Tip diameter",
        }

        self.toolCode.setText(tool_code or "T1")
        for key, label in _MILLING_TOOL_TYPES.items():
            self.toolType.addItem(label, key)
        type_index = self.toolType.findData(str(spec.get("type", "mill_flat")))
        self.toolType.setCurrentIndex(max(0, type_index))
        self.diameter.setValue(float(spec.get("diameter", 10.0)))
        self.cornerRadius.setValue(float(spec.get("cornerRadius", 0.0)))
        self.length.setValue(float(spec.get("length", 50.0)))

        tool_type = str(spec.get("type", "mill_flat"))
        diameter = self.diameter.value()
        length = self.length.value()
        self.cuttingHeight.setValue(
            float(spec.get("cuttingHeight", default_cutting_height(tool_type, diameter, length)))
        )
        self.shankDiameter.setValue(float(spec.get("shankDiameter", default_shank_diameter(diameter))))
        self.tipDiameter.setValue(float(spec.get("tipDiameter", default_tip_diameter(diameter))))
        self.chamferAngle.setValue(float(spec.get("chamferAngle", 90.0)))
        self.tipAngle.setValue(float(spec.get("tipAngle", default_drill_tip_angle())))
        self.description.setText(str(spec.get("description", "")))
        self._shapeRows = {
            self.cuttingHeight: self.ui.cuttingHeightLabel,
            self.shankDiameter: self.ui.shankDiameterLabel,
            self.tipDiameter: self.ui.tipDiameterLabel,
            self.chamferAngle: self.ui.chamferAngleLabel,
            self.tipAngle: self.ui.tipAngleLabel,
        }
        self.inches.toggled.connect(self._set_units)
        self.buttonBox.accepted.connect(self.validateAndAccept)
        self.buttonBox.rejected.connect(self.reject)
        self.toolType.currentIndexChanged.connect(self.updateRadiusField)
        self.diameter.valueChanged.connect(self.updateBallRadius)
        self.updateRadiusField()
        self.toolCode.selectAll()
        self.toolCode.setFocus()

    def _set_units(self, inches: bool):
        set_length_units(self._length_controls, bool(inches), suffix=False)
        unit = "in" if inches else "mm"
        for label, text in self._length_labels.items():
            label.setText(f"{text}, {unit}")

    def currentType(self):
        """Return the stable milling tool type key."""
        return str(self.toolType.currentData())

    def updateRadiusField(self, *_args):
        """Expose only geometry fields meaningful for the selected cutter type."""
        tool_type = self.currentType()
        self.cornerRadius.setEnabled(tool_type == "mill_bull")
        if tool_type == "mill_ball":
            self.cornerRadius.setValue(self.diameter.value() / 2.0)
        elif tool_type != "mill_bull":
            self.cornerRadius.setValue(0.0)

        stepped = tool_type in {"face_mill", "slot_mill"}
        chamfer = tool_type == "chamfer_mill"
        for field in (self.cuttingHeight, self.shankDiameter):
            field.setVisible(stepped)
            self._shapeRows[field].setVisible(stepped)
        for field in (self.tipDiameter, self.chamferAngle):
            field.setVisible(chamfer)
            self._shapeRows[field].setVisible(chamfer)
        axial = tool_type == "drill"
        self.tipAngle.setVisible(axial)
        self._shapeRows[self.tipAngle].setVisible(axial)

    def updateBallRadius(self, *_args):
        """Keep ball radius equal to half of tool diameter."""
        if self.currentType() == "mill_ball":
            self.cornerRadius.setValue(self.diameter.value() / 2.0)

    def validateAndAccept(self):
        """Accept only valid compact tool numbers and physical geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or not 1 <= int(digits) <= 99:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "T code must be T1-T99."),
            )
            return
        if self.diameter.value() <= 0.0 or self.length.value() <= 0.0:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "Diameter and length must be greater than zero."),
            )
            return
        tool_type = self.currentType()
        if tool_type == "mill_bull" and self.cornerRadius.value() > self.diameter.value() / 2.0:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "Bull corner radius cannot exceed half the diameter."),
            )
            return
        if tool_type in {"face_mill", "slot_mill"}:
            if not 0.0 < self.cuttingHeight.value() <= self.length.value():
                QMessageBox.warning(
                    self,
                    QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                    QCoreApplication.translate(
                        "ToolLibraryDialog", "Cutting height must be within the total tool length."
                    ),
                )
                return
            if not 0.0 < self.shankDiameter.value() < self.diameter.value():
                QMessageBox.warning(
                    self,
                    QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                    QCoreApplication.translate(
                        "ToolLibraryDialog", "Shank diameter must be smaller than cutter diameter."
                    ),
                )
                return
        if tool_type == "chamfer_mill" and not 0.0 <= self.tipDiameter.value() < self.diameter.value():
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate(
                    "ToolLibraryDialog", "Chamfer tip diameter must be smaller than cutter diameter."
                ),
            )
            return
        _accept_unique_tool(self)

    def value(self):
        """Return compact T1-T99 tool code and milling geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits)}"
        tool_type = self.currentType()
        diameter = metric_value(self.diameter)
        radius = metric_value(self.cornerRadius)
        if tool_type == "mill_ball":
            radius = diameter / 2.0
        elif tool_type != "mill_bull":
            radius = 0.0
        spec = {
            "type": tool_type,
            "diameter": diameter,
            "cornerRadius": radius,
            "length": metric_value(self.length),
        }
        if tool_type in {"face_mill", "slot_mill"}:
            spec.update(
                cuttingHeight=metric_value(self.cuttingHeight),
                shankDiameter=metric_value(self.shankDiameter),
            )
        elif tool_type == "chamfer_mill":
            spec.update(
                tipDiameter=metric_value(self.tipDiameter),
                chamferAngle=self.chamferAngle.value(),
            )
        elif tool_type == "drill":
            spec["tipAngle"] = self.tipAngle.value()
        description = " ".join(self.description.text().split())
        if description:
            spec["description"] = description
        return key, spec
