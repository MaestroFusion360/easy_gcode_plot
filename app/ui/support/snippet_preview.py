"""Compact parameter entry, resolved text and a SQLite-backed illustration."""

import re
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QCoreApplication, QEvent, QIODevice, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QImageReader, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)


def error_text(error):
    messages = {
        "Invalid placeholder": QCoreApplication.translate("SnippetPreview", "Invalid placeholder"),
        "Unknown placeholder": QCoreApplication.translate("SnippetPreview", "Unknown placeholder"),
        "Conflicting parameter": QCoreApplication.translate("SnippetPreview", "Conflicting parameter declarations"),
        "Missing value": QCoreApplication.translate("SnippetPreview", "Enter a value"),
        "Invalid number": QCoreApplication.translate("SnippetPreview", "Enter a valid number"),
        "Integer required": QCoreApplication.translate("SnippetPreview", "Enter an integer"),
        "Value out of range": QCoreApplication.translate("SnippetPreview", "Value is outside the allowed range"),
        "Invalid choice": QCoreApplication.translate("SnippetPreview", "Select an allowed value"),
        "Invalid contour": QCoreApplication.translate("SnippetPreview", "Enter contour labels as START:END"),
        "Invalid formula": QCoreApplication.translate("SnippetPreview", "Invalid formula"),
        "Unknown function": QCoreApplication.translate("SnippetPreview", "Unknown function"),
        "Formula is too complex": QCoreApplication.translate("SnippetPreview", "Formula is too complex"),
        "Math error": QCoreApplication.translate("SnippetPreview", "Math error: check arguments and division by zero"),
        "Invalid precision": QCoreApplication.translate("SnippetPreview", "Decimals must be between 0 and 12"),
        "Save the document first": QCoreApplication.translate(
            "SnippetPreview", "Save the document to use its file name or path"
        ),
        "File no longer exists": QCoreApplication.translate("SnippetPreview", "The document file no longer exists"),
        "Only one cursor marker is allowed": QCoreApplication.translate("SnippetPreview", "Use only one cursor marker"),
    }
    message = messages.get(error.code, error.code)
    return f"{message}: {error.detail}" if error.detail else message


def _cycle_parameter_labels():
    return {
        "X": QCoreApplication.translate("SnippetPreview", "X coordinate, mm"),
        "Y": QCoreApplication.translate("SnippetPreview", "Y coordinate, mm"),
        "Z": QCoreApplication.translate("SnippetPreview", "Z endpoint, mm"),
        "SafeX": QCoreApplication.translate("SnippetPreview", "Safe X coordinate, mm"),
        "SafeZ": QCoreApplication.translate("SnippetPreview", "Safe Z coordinate, mm"),
        "SpindleDirection": QCoreApplication.translate("SnippetPreview", "Spindle direction (M3/M4)"),
        "LengthOffset": QCoreApplication.translate("SnippetPreview", "H - length offset register"),
        "ToolOffset": QCoreApplication.translate("SnippetPreview", "Tool offset number"),
        "CuttingEdge": QCoreApplication.translate("SnippetPreview", "D - cutting edge number"),
        "MinX": QCoreApplication.translate("SnippetPreview", "Stock minimum X, mm"),
        "MinY": QCoreApplication.translate("SnippetPreview", "Stock minimum Y, mm"),
        "MinZ": QCoreApplication.translate("SnippetPreview", "Stock minimum Z, mm"),
        "MaxX": QCoreApplication.translate("SnippetPreview", "Stock maximum X, mm"),
        "MaxY": QCoreApplication.translate("SnippetPreview", "Stock maximum Y, mm"),
        "MaxZ": QCoreApplication.translate("SnippetPreview", "Stock maximum Z, mm"),
        "ReturnMode": QCoreApplication.translate("SnippetPreview", "Return level (G98/G99)"),
        "ReturnZ": QCoreApplication.translate("SnippetPreview", "R - return plane Z, mm"),
        "Retract": QCoreApplication.translate("SnippetPreview", "R - retract distance, mm"),
        "PeckMicrons": QCoreApplication.translate("SnippetPreview", "Q - Z peck, 0.001 mm"),
        "StepMicrons": QCoreApplication.translate("SnippetPreview", "P - X step, 0.001 mm"),
        "EndRelief": QCoreApplication.translate("SnippetPreview", "R - end relief, mm"),
        "CutDepth": QCoreApplication.translate("SnippetPreview", "U - roughing depth, mm"),
        "StartBlock": QCoreApplication.translate("SnippetPreview", "P - first contour block"),
        "EndBlock": QCoreApplication.translate("SnippetPreview", "Q - last contour block"),
        "FinishX": QCoreApplication.translate("SnippetPreview", "U - X finishing allowance, mm"),
        "FinishZ": QCoreApplication.translate("SnippetPreview", "W - Z finishing allowance, mm"),
        "FinishPasses": QCoreApplication.translate("SnippetPreview", "P (1-2) - finishing passes"),
        "Chamfer": QCoreApplication.translate("SnippetPreview", "P (3-4) - pull-out, 0.1 pitch"),
        "ToolAngle": QCoreApplication.translate("SnippetPreview", "P (5-6) - tool angle, deg"),
        "MinCutMicrons": QCoreApplication.translate("SnippetPreview", "Q - minimum cut, 0.001 mm"),
        "FirstCutMicrons": QCoreApplication.translate("SnippetPreview", "Q - first cut, 0.001 mm"),
        "HeightMicrons": QCoreApplication.translate("SnippetPreview", "P - thread height, 0.001 mm"),
        "FinishAllowance": QCoreApplication.translate("SnippetPreview", "R - finishing allowance, mm"),
        "Pitch": QCoreApplication.translate("SnippetPreview", "Thread pitch, mm"),
        "Taper": QCoreApplication.translate("SnippetPreview", "R - thread taper, mm"),
        "RTP": QCoreApplication.translate("SnippetPreview", "RTP - return plane, mm"),
        "RFP": QCoreApplication.translate("SnippetPreview", "RFP - reference plane, mm"),
        "SDIS": QCoreApplication.translate("SnippetPreview", "SDIS - safety clearance, mm"),
        "DP": QCoreApplication.translate("SnippetPreview", "DP - absolute depth, mm"),
        "DPR": QCoreApplication.translate("SnippetPreview", "DPR - relative depth, mm"),
        "FDEP": QCoreApplication.translate("SnippetPreview", "FDEP - first absolute depth, mm"),
        "FDPR": QCoreApplication.translate("SnippetPreview", "FDPR - first relative depth, mm"),
        "DAM": QCoreApplication.translate("SnippetPreview", "DAM - decrement, mm"),
        "DTB": QCoreApplication.translate("SnippetPreview", "DTB - bottom dwell, s"),
        "DTS": QCoreApplication.translate("SnippetPreview", "DTS - top dwell, s"),
        "FRF": QCoreApplication.translate("SnippetPreview", "FRF - first infeed factor"),
        "VARI": QCoreApplication.translate("SnippetPreview", "VARI - cycle variant"),
        "Contour": QCoreApplication.translate("SnippetPreview", "Contour (START:END)"),
        "MID": QCoreApplication.translate("SnippetPreview", "MID - maximum infeed, mm"),
        "FALZ": QCoreApplication.translate("SnippetPreview", "FALZ - Z finishing allowance, mm"),
        "FALX": QCoreApplication.translate("SnippetPreview", "FALX - X finishing allowance, mm"),
        "FAL": QCoreApplication.translate("SnippetPreview", "FAL - finishing allowance, mm"),
        "FF1": QCoreApplication.translate("SnippetPreview", "FF1 - roughing feed"),
        "FF2": QCoreApplication.translate("SnippetPreview", "FF2 - plunge feed"),
        "FF3": QCoreApplication.translate("SnippetPreview", "FF3 - finishing feed"),
        "DT": QCoreApplication.translate("SnippetPreview", "DT - dwell, s"),
        "VRT": QCoreApplication.translate("SnippetPreview", "VRT - retract distance, mm"),
        "MPIT": QCoreApplication.translate("SnippetPreview", "MPIT - nominal thread size"),
        "SPL": QCoreApplication.translate("SnippetPreview", "SPL - thread start Z, mm"),
        "FPL": QCoreApplication.translate("SnippetPreview", "FPL - thread end Z, mm"),
        "DM1": QCoreApplication.translate("SnippetPreview", "DM1 - start diameter, mm"),
        "DM2": QCoreApplication.translate("SnippetPreview", "DM2 - end diameter, mm"),
        "APP": QCoreApplication.translate("SnippetPreview", "APP - approach length, mm"),
        "ROP": QCoreApplication.translate("SnippetPreview", "ROP - run-out length, mm"),
        "TDEP": QCoreApplication.translate("SnippetPreview", "TDEP - thread depth, mm"),
        "IANG": QCoreApplication.translate("SnippetPreview", "IANG - infeed angle, deg"),
        "NSP": QCoreApplication.translate("SnippetPreview", "NSP - start angle, deg"),
        "NRC": QCoreApplication.translate("SnippetPreview", "NRC - cutting passes"),
        "NID": QCoreApplication.translate("SnippetPreview", "NID - spring passes"),
        "NUMT": QCoreApplication.translate("SnippetPreview", "NUMT - thread starts"),
        "Q200": QCoreApplication.translate("SnippetPreview", "Q200 - set-up clearance, mm"),
        "Q201": QCoreApplication.translate("SnippetPreview", "Q201 - relative depth, mm"),
        "Q206": QCoreApplication.translate("SnippetPreview", "Q206 - plunging feed, mm/min"),
        "Q202": QCoreApplication.translate("SnippetPreview", "Q202 - plunging depth, mm"),
        "Q210": QCoreApplication.translate("SnippetPreview", "Q210 - top dwell, s"),
        "Q203": QCoreApplication.translate("SnippetPreview", "Q203 - surface coordinate, mm"),
        "Q204": QCoreApplication.translate("SnippetPreview", "Q204 - second clearance, mm"),
        "Q212": QCoreApplication.translate("SnippetPreview", "Q212 - decrement, mm"),
        "Q213": QCoreApplication.translate("SnippetPreview", "Q213 - breaks before retracting"),
        "Q205": QCoreApplication.translate("SnippetPreview", "Q205 - minimum infeed, mm"),
        "Q211": QCoreApplication.translate("SnippetPreview", "Q211 - bottom dwell, s"),
        "Q208": QCoreApplication.translate("SnippetPreview", "Q208 - retract feed, mm/min"),
        "Q256": QCoreApplication.translate("SnippetPreview", "Q256 - chip-breaking distance, mm"),
    }


def parameter_label(parameter):
    labels = {
        "Program": QCoreApplication.translate("SnippetPreview", "Program"),
        "Tool": QCoreApplication.translate("SnippetPreview", "Tool"),
        "ToolType": QCoreApplication.translate("SnippetPreview", "Tool type"),
        "Diameter": QCoreApplication.translate("SnippetPreview", "Tool diameter, mm"),
        "NoseRadius": QCoreApplication.translate("SnippetPreview", "Insert nose radius, mm"),
        "InsertType": QCoreApplication.translate("SnippetPreview", "Insert type"),
        "PointAngle": QCoreApplication.translate("SnippetPreview", "Drill point angle, deg"),
        "RPM": QCoreApplication.translate("SnippetPreview", "Spindle speed, rpm"),
        "Angle": QCoreApplication.translate("SnippetPreview", "Angle, deg"),
        "Depth": QCoreApplication.translate("SnippetPreview", "Depth, mm"),
        "Peck": QCoreApplication.translate("SnippetPreview", "Peck, mm"),
        "Feed": QCoreApplication.translate("SnippetPreview", "Feed"),
        "Text": QCoreApplication.translate("SnippetPreview", "Text"),
        "Length": QCoreApplication.translate("SnippetPreview", "Length, mm"),
        "Inches": QCoreApplication.translate("SnippetPreview", "Length, inch"),
        "Vc": "Vc, m/min",
        "D": "D, mm",
        "R": "R, mm",
    }
    labels.update(_cycle_parameter_labels())
    text = labels.get(parameter.name, parameter.label) if parameter.label == parameter.name else parameter.label
    return text + QCoreApplication.translate("SnippetPreview", " (optional)") if parameter.optional else text


def picture_image(data):
    if len(data) > 10 * 1024 * 1024:
        raise ValueError(
            QCoreApplication.translate("SnippetPreview", "Picture must be at most 10 MB and 4096 × 4096 pixels")
        )
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if size.width() > 4096 or size.height() > 4096:
        raise ValueError(
            QCoreApplication.translate("SnippetPreview", "Picture must be at most 10 MB and 4096 × 4096 pixels")
        )
    image = reader.read()
    if image.isNull():
        # Explicit import also makes the SVG renderer available in frozen builds.
        svg = QSvgRenderer(QByteArray(data))
        if svg.isValid():
            from PyQt6.QtGui import QPainter  # pylint: disable=import-outside-toplevel

            if svg.defaultSize().width() > 4096 or svg.defaultSize().height() > 4096:
                raise ValueError(
                    QCoreApplication.translate("SnippetPreview", "Picture must be at most 10 MB and 4096 × 4096 pixels")
                )
            image = QImage(svg.defaultSize(), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            svg.render(painter)
            painter.end()
    if image.isNull():
        raise ValueError(QCoreApplication.translate("SnippetPreview", "Cannot read this picture"))
    return image


def png_bytes(image):
    if image.width() > 4096 or image.height() > 4096 or image.isNull():
        raise ValueError(
            QCoreApplication.translate("SnippetPreview", "Picture must be at most 10 MB and 4096 × 4096 pixels")
        )
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(buffer.data())
    if len(data) > 10 * 1024 * 1024:
        raise ValueError(
            QCoreApplication.translate("SnippetPreview", "Picture must be at most 10 MB and 4096 × 4096 pixels")
        )
    return data


def _svg_for_palette(data, palette):
    base = palette.color(QPalette.ColorRole.Base)
    text = palette.color(QPalette.ColorRole.Text).name()
    colors = {"white": base.name(), "#202832": base.name(), "#eef4fa": text}
    if base.lightness() < 128:
        colors.update(
            {
                "#222": text,
                "#333": text,
                "#555": "#b0b0b0",
                "#777": "#999999",
                "#aaa": "#888888",
                "#b8b8b8": "#626262",
                "#eee": "#343438",
                "#9a5b08": "#ffb65c",
                "#b36b10": "#ffb65c",
            }
        )
    else:
        colors.update(
            {
                "#a8b8c8": "#555555",
                "#718092": "#777777",
                "#2b444d": "#e5eeee",
                "#ffb65c": "#a56210",
                "#ffc66d": "#a56210",
                "#4ed8c5": "#127d70",
            }
        )
    return re.sub(
        rb'(fill|stroke)="([^"]+)"',
        lambda match: match[1] + b'="' + colors.get(match[2].decode(), match[2].decode()).encode() + b'"',
        data,
    )


class PictureLabel(QLabel):
    """Drop a picture, paste from clipboard, or click to open a zoomable view."""

    dropped = pyqtSignal(bytes)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self._data = None
        self._render_key = None
        self._rendered_image = QImage()
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 100)
        self.setMaximumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setToolTip(QCoreApplication.translate("SnippetPreview", "Drop a picture here. Click to enlarge."))

    def set_picture(self, data):
        self.image = picture_image(data) if data else QImage()
        self._data = data
        self._render_key = None
        self._resize_picture()

    def _display_image(self):
        if not self._data or b"<svg" not in self._data[:1024]:
            return self.image
        palette = self.palette()
        key = (palette.color(QPalette.ColorRole.Base).rgba(), palette.color(QPalette.ColorRole.Text).rgba())
        if key != self._render_key:
            self._rendered_image = picture_image(_svg_for_palette(self._data, palette))
            self._render_key = key
        return self._rendered_image

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._resize_picture()

    def _resize_picture(self):
        if self.image.isNull():
            self.setPixmap(QPixmap())
            self.setText(QCoreApplication.translate("SnippetPreview", "Drop a picture or use Picture"))
        else:
            self.setPixmap(
                QPixmap.fromImage(self._display_image()).scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )

    def resizeEvent(self, event):
        self._resize_picture()
        super().resizeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasImage() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            mime = event.mimeData()
            if mime.hasImage():
                data = png_bytes(mime.imageData())
            else:
                path = Path(mime.urls()[0].toLocalFile())
                if path.stat().st_size > 10 * 1024 * 1024:
                    raise ValueError(
                        QCoreApplication.translate(
                            "SnippetPreview", "Picture must be at most 10 MB and 4096 × 4096 pixels"
                        )
                    )
                data = png_bytes(picture_image(path.read_bytes()))
            self.dropped.emit(data)
            event.acceptProposedAction()
        except (OSError, ValueError, IndexError) as exc:
            self.failed.emit(str(exc))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.image.isNull():
            self._show_picture()
        super().mouseReleaseEvent(event)

    def _show_picture(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("SnippetPreview", "Picture"))
        dialog.resize(640, 480)
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        label = QLabel()
        scroll.setWidget(label)
        layout.addWidget(scroll)
        buttons = QHBoxLayout()
        scale = [1.0]

        def zoom(factor):
            scale[0] = min(4.0, max(0.1, scale[0] * factor))
            pixmap = QPixmap.fromImage(self._display_image()).scaled(
                self.image.size() * scale[0],
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pixmap)
            label.resize(pixmap.size())

        for title, factor in (("−", 0.8), ("+", 1.25)):
            button = QPushButton(title)
            button.clicked.connect(lambda _checked=False, value=factor: zoom(value))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        zoom(1.0)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
