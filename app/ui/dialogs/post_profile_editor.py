"""Embedded editor for NC post profiles bound to Designer widgets.

Layout lives in ``post_profile_editor.ui``; this module only maps the named
widgets to profile fields and validates the
result with the same rules the exporter uses.
"""

from __future__ import annotations

import copy

from PyQt6.QtCore import QCoreApplication, QEvent, QMimeData, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from app.ui.generated.dialogs.post_profile_editor import Ui_PostProfileEditorDlg

_AXES = ("X", "Y", "Z", "A", "B", "C")
_ADDRESS_MIME = "application/x-easy-gcode-address"


class _FlowLayout(QLayout):
    """Compact left-to-right layout that wraps address tiles."""

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, test_only=False)

    def _layout(self, rect, *, test_only):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > area.right() and line_height:
                x = area.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class _AddressTile(QToolButton):
    """Draggable address tile used by the sequencing editor."""

    def __init__(self, address, title, parent=None):
        super().__init__(parent)
        self.address = address
        self._press_position = QPoint()
        self.setText(title)
        self.setCheckable(True)
        self.setAutoRaise(False)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumWidth(64)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return super().mouseMoveEvent(event)
        distance = (event.position().toPoint() - self._press_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)
        mime = QMimeData()
        mime.setData(_ADDRESS_MIME, self.address.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.MoveAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


# (widget, profile path) for single-line text fields.
_LINES = (
    ("nameEdit", ("name",)),
    ("extensionEdit", ("extension",)),
    ("rapidMoveEdit", ("motion", "rapidMove")),
    ("linearMoveEdit", ("motion", "linearMove")),
    ("circularMoveCWEdit", ("motion", "circularMoveCW")),
    ("circularMoveCCWEdit", ("motion", "circularMoveCCW")),
    ("planeXYEdit", ("motion", "planeXY")),
    ("planeXZEdit", ("motion", "planeXZ")),
    ("planeYZEdit", ("motion", "planeYZ")),
    ("threadMoveEdit", ("motion", "threadMove")),
    ("absoluteEdit", ("positioning", "absolute")),
    ("incrementalEdit", ("positioning", "incremental")),
    ("referenceRapidEdit", ("reference", "rapid")),
    ("referenceLinearEdit", ("reference", "linear")),
    ("homeG28AllEdit", ("home", "G28", "all")),
    ("homeG28XEdit", ("home", "G28", "X")),
    ("homeG28YEdit", ("home", "G28", "Y")),
    ("homeG28ZEdit", ("home", "G28", "Z")),
    ("homeG53AllEdit", ("home", "G53", "all")),
    ("homeG53XEdit", ("home", "G53", "X")),
    ("homeG53YEdit", ("home", "G53", "Y")),
    ("homeG53ZEdit", ("home", "G53", "Z")),
    ("cyclesCancelEdit", ("cycles", "cancel")),
    ("cyclesReturnInitialEdit", ("cycles", "returnInitial")),
    ("cyclesReturnSafetyEdit", ("cycles", "returnSafety")),
    ("cyclesRigidTapEdit", ("cycles", "rigidTap")),
    ("cyclesDrillEdit", ("cycles", "drill")),
    ("cyclesDrillDwellEdit", ("cycles", "drillDwell")),
    ("cyclesPeckDrillEdit", ("cycles", "peckDrill")),
    ("cyclesHighSpeedPeckEdit", ("cycles", "highSpeedPeck")),
    ("cyclesTapEdit", ("cycles", "tap")),
    ("cyclesBoreFeedEdit", ("cycles", "boreFeed")),
    ("cyclesBoreStopEdit", ("cycles", "boreStop")),
    ("toolChangeEdit", ("tool", "toolChange")),
    ("spindleCWEdit", ("spindle", "cw")),
    ("spindleCCWEdit", ("spindle", "ccw")),
    ("spindleStopEdit", ("spindle", "stop")),
    ("spindleCSSOnEdit", ("spindle", "cssOn")),
    ("spindleCSSOffEdit", ("spindle", "cssOff")),
    ("spindleMaxSpeedEdit", ("spindle", "maxSpeed")),
    ("coolantMistEdit", ("coolant", "mist")),
    ("coolantFloodEdit", ("coolant", "flood")),
    ("coolantOffEdit", ("coolant", "off")),
    ("feedPerMinuteEdit", ("feed", "perMinute")),
    ("feedPerRevEdit", ("feed", "perRev")),
    ("feedInverseTimeEdit", ("feed", "inverseTime")),
    ("unitsInchEdit", ("units", "inch")),
    ("unitsMetricEdit", ("units", "metric")),
    ("dwellCommandEdit", ("dwell", "command")),
    ("dwellScaleEdit", ("dwell", "scale")),
    ("programStartEdit", ("program", "start")),
    ("programStopEdit", ("program", "stop")),
    ("programOptionalStopEdit", ("program", "optionalStop")),
    ("programEndEdit", ("program", "end")),
    ("commentTemplateEdit", ("comment", "template")),
    ("tcpOnEdit", ("multiaxis", "tcpOn")),
    ("tcpOffEdit", ("multiaxis", "tcpOff")),
    ("nativeCycleCallEdit", ("native", "cycleCall")),
    ("nativeDwellDefinitionEdit", ("native", "dwellDefinition")),
)

# (widget, profile path) for multi-line text fields holding a list of lines.
_LISTS = (
    ("preambleEdit", ("program", "preamble")),
    ("safetyEdit", ("program", "safety")),
)

# (widget, profile path) for boolean fields.
_CHECKS = (
    ("multiTurn", ("format", "multiTurnArcs")),
    ("spaces", ("options", "delimiter")),
    ("leadingZero", ("options", "leadingZero")),
    ("forceDecimal", ("options", "forceDecimal")),
    ("plusSign", ("options", "plusOutput")),
    ("inverseTimeCheck", ("supports", "inverseTime")),
    ("supportsMultiTurnArcsCheck", ("supports", "multiTurnArcs")),
    ("absoluteArcCentersCheck", ("supports", "absoluteArcCenters")),
    ("tcpCheck", ("supports", "tcp")),
)

# (widget, profile path, values-by-index) for comboboxes.
_COMBOS = (
    ("machineCombo", ("machine",), ("mill", "lathe")),
    ("units", ("options", "units"), ("mm", "inch")),
    ("coordinates", ("options", "incrementalMode"), (False, True)),
    ("cyclesSyntaxCombo", ("cycles", "syntax"), ("iso", "native")),
    ("dwellAddressCombo", ("dwell", "address"), ("P", "F", "X")),
    ("programModeCombo", ("program", "mode"), ("G290", "G291")),
    ("precision", ("options", "decimalPlaces"), tuple(range(13))),
    ("centerSplit", ("format", "arcSplitAngle"), (30, 45, 90, 120, 180, 360)),
    ("radiusSplit", ("format", "radiusSplitAngle"), (30, 45, 90, 120, 180, 360)),
)

# Fields always shown even when the profile omits them (defaults apply).
_ALWAYS = frozenset({"centerSplit", "radiusSplit"})


def _humanize(text):
    spaced = "".join(char if not char.isupper() or index == 0 else f" {char}" for index, char in enumerate(str(text)))
    return spaced[:1].upper() + spaced[1:]


def _coerce(text, template):
    if isinstance(template, bool):
        return str(text).strip().lower() in {"true", "1", "yes"}
    if isinstance(template, int):
        return int(str(text).strip())
    if isinstance(template, float):
        return float(str(text).strip())
    return text


class PostProfileEditor(QWidget):
    """Configure the supported output behavior of a user post profile."""

    def __init__(self, library, path=None, parent=None, *, profile=None, read_only=False):
        super().__init__(parent)
        self.library = library
        self.path = str(library.managed_path(path)) if path is not None else None
        self.profile = copy.deepcopy(profile) if profile is not None else library.load(path)
        self._saved_profile = copy.deepcopy(self.profile)
        self.read_only = read_only
        self.saved_path = None
        self._bindings = []
        self._combo_values = {}
        self.ui = Ui_PostProfileEditorDlg()
        self.ui.setupUi(self)
        self._normalize_editor_widgets()
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        heading = QLabel(library.name(self.profile, self.profile.get("id", "")), self)
        heading.setTextFormat(Qt.TextFormat.PlainText)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        self.ui.verticalLayout.insertWidget(0, heading)
        self._load_text()
        self._load_checks()
        self._load_combos()
        self._load_axes()
        self._build_words()
        self._disable_empty_tabs()
        self._configure_profile_ui()
        for _path, widget, _kind, _initial in self._bindings:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._validate)
            elif isinstance(widget, QPlainTextEdit):
                widget.textChanged.connect(self._validate)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._validate)
            else:
                widget.textChanged.connect(self._validate)
        self.arcs_current = self.arcs_index()
        self.ui.arcs.setCurrentIndex(self.arcs_current)
        self.ui.arcs.currentIndexChanged.connect(self._validate)
        self._validate()
        if read_only:
            self.set_read_only()

    def set_read_only(self):
        """Keep navigation and copying available for bundled profiles."""
        for widget in self.findChildren(QLineEdit) + self.findChildren(QPlainTextEdit):
            widget.setReadOnly(True)
        for cls in (QComboBox, QCheckBox, QToolButton):
            for widget in self.findChildren(cls):
                widget.setEnabled(False)

    def is_dirty(self):
        if self.read_only:
            return False
        try:
            return self.path is None or self.current_profile() != self._saved_profile
        except (ValueError, TypeError, KeyError):
            return True

    # -- helpers ----------------------------------------------------------
    def _orig(self, path, default=None):
        node = self.profile
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def _has(self, path):
        node = self.profile
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return False
            node = node[key]
        return True

    def _hide(self, name):
        widget = getattr(self.ui, name)
        widget.setVisible(False)
        label = getattr(self.ui, f"{name}Label", None)
        if label is not None:
            label.setVisible(False)

    def _bind(self, path, widget, kind, initial):
        self._bindings.append((path, widget, kind, initial))
        return widget

    def _normalize_editor_widgets(self):
        """Keep fields readable and let long tabs scroll instead of crushing rows."""
        for form in self.findChildren(QFormLayout):
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for widget in (*self.findChildren(QLineEdit), *self.findChildren(QComboBox)):
            height = max(26, widget.sizeHint().height())
            widget.setMinimumSize(0, height)
            widget.setMaximumSize(16777215, height)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for widget in self.findChildren(QPlainTextEdit):
            widget.setMinimumSize(0, 84)
            widget.setMaximumSize(16777215, 132)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _configure_profile_ui(self):
        """Expose only settings implemented by the selected post writer."""
        self.ui.machineCombo.setEnabled(False)
        self.ui.machineCombo.setToolTip(
            QCoreApplication.translate(
                "PostProfileEditorDlg", "Machine type is fixed when the postprocessor profile is created."
            )
        )
        self.ui.cyclesSyntaxCombo.setEnabled(False)
        self.ui.cyclesSyntaxCombo.setToolTip(
            QCoreApplication.translate(
                "PostProfileEditorDlg", "Cycle syntax is fixed by the fields available in this profile."
            )
        )
        self.ui.inverseTimeCheck.setToolTip(
            QCoreApplication.translate("PostProfileEditorDlg", "Allow exporting resolved G93 inverse-time feed.")
        )
        self.ui.supportsMultiTurnArcsCheck.setToolTip(
            QCoreApplication.translate("PostProfileEditorDlg", "Allow one arc block to exceed 360 degrees.")
        )
        self.ui.absoluteArcCentersCheck.setToolTip(
            QCoreApplication.translate("PostProfileEditorDlg", "Allow the Absolute IJK center mode in Arc output.")
        )
        self.ui.tcpCheck.setToolTip(
            QCoreApplication.translate("PostProfileEditorDlg", "Allow TCP output using the TCP on/off commands below.")
        )
        if "multiaxis" not in self.profile:
            self._hide("tcpCheck")
        native = self.profile.get("id") == "heidanhain_itnc530"
        if not native:
            return
        for axis in _AXES:
            getattr(self.ui, f"axis{axis}Check").setEnabled(False)
        native_motion_labels = {
            "rapidMoveEditLabel": "Linear block",
            "linearMoveEditLabel": "Rapid feed",
            "circularMoveCWEditLabel": "Circle center",
            "circularMoveCCWEditLabel": "Circle",
            "planeXYEditLabel": "Polar circle",
            "planeXZEditLabel": "Radius address",
            "planeYZEditLabel": "Clockwise direction",
            "threadMoveEditLabel": "Counterclockwise direction",
            "absoluteEditLabel": "Compensation off",
            "incrementalEditLabel": "Machine coordinates",
        }
        for name, text in native_motion_labels.items():
            getattr(self.ui, name).setText(QCoreApplication.translate("PostProfileEditorDlg", text))
        self.ui.coordinates.setItemText(
            0, QCoreApplication.translate("PostProfileEditorDlg", "Absolute coordinates (X/Y/Z; CC absolute)")
        )
        self.ui.coordinates.setItemText(
            1, QCoreApplication.translate("PostProfileEditorDlg", "Incremental coordinates (IX/IY/IZ; CC absolute)")
        )
        self.ui.coordinates.setToolTip(
            QCoreApplication.translate(
                "PostProfileEditorDlg",
                "Incremental Heidenhain positions use IX, IY and IZ. Circle centers in CC remain absolute.",
            )
        )
        self.ui.arcs.setItemText(0, "CC + C/CP")
        self.ui.arcs.setItemText(2, "R")
        self.ui.arcs.model().item(1).setEnabled(False)
        self.ui.arcs.view().setRowHidden(1, True)
        for name in (
            "multiTurn",
            "spaces",
            "leadingZero",
            "inverseTimeCheck",
            "supportsMultiTurnArcsCheck",
            "absoluteArcCentersCheck",
            "tcpCheck",
            "referenceRapidEdit",
            "referenceLinearEdit",
            "cyclesCancelEdit",
            "spindleCSSOnEdit",
            "spindleCSSOffEdit",
            "spindleMaxSpeedEdit",
            "feedPerMinuteEdit",
            "feedPerRevEdit",
            "feedInverseTimeEdit",
            "unitsInchEdit",
            "unitsMetricEdit",
            "dwellAddressCombo",
            "dwellScaleEdit",
            "commentTemplateEdit",
            "preambleEdit",
            "safetyEdit",
        ):
            self._hide(name)
        self.ui.homeTab.setEnabled(False)
        index = self.ui.tabs.indexOf(self.ui.supportsTab)
        self.ui.tabs.setTabEnabled(index, False)
        self.ui.tabs.setTabToolTip(
            index,
            QCoreApplication.translate(
                "PostProfileEditorDlg", "Capabilities are fixed by the native Heidenhain writer."
            ),
        )

    # -- loading ----------------------------------------------------------
    def _load_text(self):
        bindings = dict(_LINES)
        if self.profile.get("id") == "heidanhain_itnc530":
            bindings.update(
                {
                    "rapidMoveEdit": ("native", "linear"),
                    "linearMoveEdit": ("native", "rapidFeed"),
                    "circularMoveCWEdit": ("native", "circleCenter"),
                    "circularMoveCCWEdit": ("native", "circle"),
                    "planeXYEdit": ("native", "polarCircle"),
                    "planeXZEdit": ("native", "radiusCircle"),
                    "planeYZEdit": ("native", "clockwise"),
                    "threadMoveEdit": ("native", "counterclockwise"),
                    "absoluteEdit": ("native", "compensationOff"),
                    "incrementalEdit": ("native", "machineCoordinates"),
                }
            )
        for name, path in bindings.items():
            widget = getattr(self.ui, name)
            if not self._has(path) and name != "nameEdit":
                self._hide(name)
                continue
            value = self._orig(path, self.library.name(self.profile, self.profile.get("id", "")))
            widget.setPlainText(str(value)) if isinstance(widget, QPlainTextEdit) else widget.setText(str(value))
            self._bind(path, widget, "text", value)
        for name, path in _LISTS:
            widget = getattr(self.ui, name)
            if not self._has(path):
                self._hide(name)
                continue
            value = self._orig(path)
            widget.setPlainText("\n".join(str(item) for item in value))
            self._bind(path, widget, "list", tuple(value))
        for name, path in (("idLabel", ("id",)),):
            if self._has(path):
                self.ui.idLabel.setText(str(self._orig(path)))
            else:
                self._hide(name)

    def _load_checks(self):
        for name, path in _CHECKS:
            widget = getattr(self.ui, name)
            if not self._has(path):
                self._hide(name)
                continue
            value = bool(self._orig(path))
            widget.setChecked(value)
            self._bind(path, widget, "check", value)

    def _load_combos(self):
        defaults = {"centerSplit": 180, "radiusSplit": 90}
        for name, path, values in _COMBOS:
            widget = getattr(self.ui, name)
            if not self._has(path) and name not in _ALWAYS:
                self._hide(name)
                continue
            value = self._orig(path, defaults.get(name, values[0]))
            if name in {"centerSplit", "radiusSplit"} and value not in values:
                values = (*values, value)
                widget.addItem(f"{value:g}\N{DEGREE SIGN}")
            index = next((i for i, candidate in enumerate(values) if candidate == value), 0)
            widget.setCurrentIndex(index)
            self._combo_values[widget] = values
            self._bind(path, widget, "combo", values[index])

    def _load_axes(self):
        path = ("supports", "axes")
        if not self._has(path):
            self._hide("axesLayout")
            return
        axes = self._orig(path)
        for axis in _AXES:
            getattr(self.ui, f"axis{axis}Check").setChecked(axis in axes)

    # -- per-address settings --------------------------------------------
    def _build_words(self):
        words = self.profile["format"].get("words") or {}
        self._word_specs = copy.deepcopy(words)
        self._word_order = sorted(words, key=lambda key: words[key]["order"])
        self._selected_address = None
        self._address_tiles = {}
        self._address_flow = _FlowLayout(self.ui.addressOrder)
        self.ui.addressOrder.setAcceptDrops(True)
        self.ui.addressOrder.installEventFilter(self)
        self._drop_indicator = QFrame(self.ui.addressOrder)
        self._drop_indicator.setFrameShape(QFrame.Shape.VLine)
        self._drop_indicator.setLineWidth(2)
        self._drop_indicator.setStyleSheet("background: palette(highlight);")
        self._drop_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._drop_indicator.hide()
        for address in self._word_order:
            title = (
                QCoreApplication.translate("PostProfileEditorDlg", "Motion command") if address == "motion" else address
            )
            tile = _AddressTile(address, title, self.ui.addressOrder)
            tile.clicked.connect(lambda _checked=False, value=address: self._select_address(value))
            self._address_tiles[address] = tile
            self._address_flow.addWidget(tile)
        for index, value in enumerate([None, *range(13)]):
            self.ui.addressPrecision.setItemData(index, value)
        for index, value in enumerate((None, "auto", "always", "never")):
            self.ui.addressSign.setItemData(index, value)
        for index, value in enumerate((False, True)):
            self.ui.addressRequired.setItemData(index, value)
        if self._word_order:
            self._select_address(self._word_order[0])
        else:
            self.ui.addressOrder.setEnabled(False)
            self.ui.selectedAddressLabel.setEnabled(False)
            for widget in (self.ui.addressPrecision, self.ui.addressSign, self.ui.addressRequired):
                widget.setEnabled(False)

    def eventFilter(self, watched, event):
        if watched is self.ui.addressOrder:
            if event.type() == QEvent.Type.DragEnter and event.mimeData().hasFormat(_ADDRESS_MIME):
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.Type.DragMove and event.mimeData().hasFormat(_ADDRESS_MIME):
                self._show_drop_indicator(self._insertion_index(event.position().toPoint()))
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.Type.DragLeave:
                self._drop_indicator.hide()
                return True
            if event.type() == QEvent.Type.Drop and event.mimeData().hasFormat(_ADDRESS_MIME):
                address = bytes(event.mimeData().data(_ADDRESS_MIME)).decode("utf-8")
                self._move_address(address, self._insertion_index(event.position().toPoint()))
                self._drop_indicator.hide()
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _insertion_slots(self):
        tiles = [self._address_tiles[address] for address in self._word_order]
        if not tiles:
            return [(QPoint(0, 0), QRect())]
        slots = [(QPoint(tiles[0].geometry().left(), tiles[0].geometry().center().y()), tiles[0].geometry())]
        for previous, current in zip(tiles, tiles[1:]):
            before, after = previous.geometry(), current.geometry()
            same_row = abs(before.center().y() - after.center().y()) < max(before.height(), after.height()) // 2
            x = (before.right() + after.left()) // 2 if same_row else after.left()
            slots.append((QPoint(x, after.center().y()), after))
        last = tiles[-1].geometry()
        slots.append((QPoint(last.right() + 1, last.center().y()), last))
        return slots

    def _insertion_index(self, position):
        slots = self._insertion_slots()
        return min(
            range(len(slots)),
            key=lambda index: (position.x() - slots[index][0].x()) ** 2 + (position.y() - slots[index][0].y()) ** 2,
        )

    def _show_drop_indicator(self, index):
        point, tile_rect = self._insertion_slots()[index]
        self._drop_indicator.setGeometry(point.x() - 1, tile_rect.top(), 3, tile_rect.height())
        self._drop_indicator.raise_()
        self._drop_indicator.show()

    def _rebuild_address_flow(self):
        while self._address_flow.count():
            self._address_flow.takeAt(0)
        for address in self._word_order:
            self._address_flow.addWidget(self._address_tiles[address])
        self._address_flow.invalidate()
        self.ui.addressOrder.updateGeometry()

    def _store_address(self):
        if self._selected_address is None:
            return
        spec = self._word_specs[self._selected_address]
        if self._selected_address != "motion":
            for key, widget in (("decimals", self.ui.addressPrecision), ("sign", self.ui.addressSign)):
                value = widget.currentData()
                if value is None:
                    spec.pop(key, None)
                else:
                    spec[key] = value
        spec["required"] = self.ui.addressRequired.currentData()

    def _select_address(self, address):
        self._store_address()
        self._selected_address = address
        if address is None:
            return
        for value, tile in self._address_tiles.items():
            tile.setChecked(value == address)
        spec = self._word_specs[address]
        title = QCoreApplication.translate("PostProfileEditorDlg", "Motion command") if address == "motion" else address
        self.ui.selectedAddressLabel.setText(self.tr("Address settings: {0}").format(title))
        for widget, value in (
            (self.ui.addressPrecision, spec.get("decimals")),
            (self.ui.addressSign, spec.get("sign")),
            (self.ui.addressRequired, spec["required"]),
        ):
            widget.blockSignals(True)
            widget.setCurrentIndex(widget.findData(value))
            widget.blockSignals(False)
        self.ui.addressPrecision.setEnabled(address != "motion")
        self.ui.addressSign.setEnabled(address != "motion")

    def _move_address(self, address, index):
        if address not in self._word_order or index < 0:
            return
        source = self._word_order.index(address)
        self._word_order.pop(source)
        if index > source:
            index -= 1
        self._word_order.insert(min(index, len(self._word_order)), address)
        self._rebuild_address_flow()
        self._select_address(address)

    def _disable_empty_tabs(self):
        for name, section in (("homeTab", "home"), ("cyclesTab", "cycles"), ("supportsTab", "supports")):
            value = self.profile.get(section)
            has_content = any(bool(item) for item in value.values()) if isinstance(value, dict) else bool(value)
            self.ui.tabs.setTabEnabled(self.ui.tabs.indexOf(getattr(self.ui, name)), has_content)

    # -- arcs -------------------------------------------------------------
    def arcs_index(self):
        arc = self.profile["format"]
        if self.profile.get("id") == "heidanhain_itnc530" and arc["outputArcs"] and arc["arcMode"] == "IJK":
            return 0
        return 3 if not arc["outputArcs"] else 2 if arc["arcMode"] == "R" else int(arc["arcCenter"] == "absolute")

    # -- profile ----------------------------------------------------------
    def current_profile(self):
        profile = copy.deepcopy(self.profile)
        self._apply_bindings(profile)
        self._apply_axes(profile)
        self._apply_arcs(profile)
        self._apply_word_order(profile)
        return profile

    def _apply_bindings(self, profile):
        for path, widget, kind, initial in self._bindings:
            value = self._value(path, widget, kind)
            if value == initial:
                continue
            node = profile
            for key in path[:-1]:
                node = node.setdefault(key, {})
            if value is None:
                node.pop(path[-1], None)
            else:
                node[path[-1]] = value

    def _apply_axes(self, profile):
        if self._has(("supports", "axes")):
            profile["supports"]["axes"] = [axis for axis in _AXES if getattr(self.ui, f"axis{axis}Check").isChecked()]

    def _apply_arcs(self, profile):
        index = self.ui.arcs.currentIndex()
        if index != self.arcs_current:
            profile["format"]["outputArcs"] = index != 3
            if index != 3:
                profile["format"]["arcMode"] = "R" if index == 2 else "IJK"
                profile["format"]["arcCenter"] = (
                    "absolute" if index == 1 or self.profile.get("id") == "heidanhain_itnc530" else "incremental"
                )

    def _apply_word_order(self, profile):
        self._store_address()
        words = profile["format"].get("words") or {}
        if words:
            for address in words:
                words[address] = copy.deepcopy(self._word_specs[address])
            orders = sorted(spec["order"] for spec in words.values())
            for address, order in zip(self._word_order, orders):
                words[address]["order"] = order

    def _value(self, path, widget, kind):
        if kind == "check":
            return widget.isChecked()
        if kind == "combo":
            values = self._combo_values.get(widget)
            return values[widget.currentIndex()] if values else widget.currentData()
        if kind == "list":
            return [line for line in widget.toPlainText().splitlines() if line.strip()]
        text = widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()
        return _coerce(text, self._orig(path))

    def _checked_profile(self):
        profile = self.current_profile()
        native = self.profile.get("id") == "heidanhain_itnc530"
        if native and self._word_order and self._word_order[0] != "motion":
            raise ValueError(
                QCoreApplication.translate(
                    "PostProfileEditorDlg", "The movement command must be the first Heidenhain address."
                )
            )
        supports = profile.get("supports") or {}
        if not native and self.ui.arcs.currentIndex() == 1 and not supports.get("absoluteArcCenters", True):
            raise ValueError(
                QCoreApplication.translate(
                    "PostProfileEditorDlg", "This postprocessor does not support absolute arc centers."
                )
            )
        if not native and profile["format"]["multiTurnArcs"] and not supports.get("multiTurnArcs", True):
            raise ValueError(
                QCoreApplication.translate(
                    "PostProfileEditorDlg", "This postprocessor does not support multi-turn arcs."
                )
            )
        return self.library.validate(profile)

    def _validate(self):
        native = self.profile.get("id") == "heidanhain_itnc530"
        self.ui.arcs.model().item(0).setEnabled(True)
        self.ui.arcs.setItemText(
            2, "R" if native else QCoreApplication.translate("PostProfileEditorDlg", "Radius (R / CR)")
        )
        self.ui.arcs.model().item(1).setEnabled(
            not native and (self.profile.get("supports") or {}).get("absoluteArcCenters", True)
        )
        if native and self.ui.arcs.currentIndex() == 1:
            self.ui.arcs.blockSignals(True)
            self.ui.arcs.setCurrentIndex(0)
            self.ui.arcs.blockSignals(False)
        self.ui.multiTurn.setEnabled(not native and self.ui.arcs.currentIndex() < 2)
        self.ui.centerSplit.setEnabled(self.ui.arcs.currentIndex() < 2 and not self.ui.multiTurn.isChecked())
        self.ui.radiusSplit.setEnabled(self.ui.arcs.currentIndex() == 2)
        if native:
            self.ui.spaces.blockSignals(True)
            self.ui.spaces.setChecked(True)
            self.ui.spaces.blockSignals(False)
        self.ui.spaces.setEnabled(not native)
        self.ui.leadingZero.setEnabled(not native)

    def save(self):
        """Validate and persist a user profile, keeping failed edits available."""
        if self.read_only:
            raise ValueError("Built-in profiles are read-only")
        profile = self._checked_profile()
        self.saved_path = self.library.save(profile, self.path)
        self.path = self.saved_path
        self._saved_profile = copy.deepcopy(profile)
        return self.saved_path
