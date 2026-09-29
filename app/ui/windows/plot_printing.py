"""Vector printing of the complete toolpath."""

from math import isfinite

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPagedPaintDevice, QPainter, QPen, QVector4D
from PyQt6.QtPrintSupport import QPrinter

from app.ui.plot.toolpath_vbo import tool_color


def project_toolpath(segments, view_matrix, *, show_rapid=True):
    """Project every sampled segment into the current camera plane."""
    projected = []
    for segment in segments:
        if segment.move == 0 and not show_rapid:
            continue
        start = view_matrix * QVector4D(*segment.start, 1.0)
        end = view_matrix * QVector4D(*segment.end, 1.0)
        coords = (start.x(), -start.y(), end.x(), -end.y())
        if all(isfinite(value) for value in coords):
            projected.append((*coords, segment.move, segment.tool))
    return projected


def print_segment_color(move, tool, *, color_by_tool=False):
    """Use one tool color for both its rapid and cutting moves."""
    assigned = tool_color(tool) if color_by_tool else None
    if assigned:
        return assigned
    return "#b94a4a" if move == 0 else "#176e54" if move in (2, 3) else "#172d49"


def paint_plot_page(printer: QPagedPaintDevice, segments, *, dashed_rapid=False, color_by_tool=False) -> None:
    """Fit and draw the whole trajectory as resolution-independent page lines."""
    painter = QPainter(printer)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if hasattr(printer, "pageRect"):
            page = QRectF(printer.pageRect(QPrinter.Unit.DevicePixel))
        else:
            page = QRectF(printer.pageLayout().paintRectPixels(printer.resolution()))
        unit = printer.resolution() / 25.4
        margin = 12 * unit
        drawing = page.adjusted(margin, margin, -margin, -margin)
        if not segments or drawing.isEmpty():
            return

        xs = [value for x1, _, x2, _, _, _ in segments for value in (x1, x2)]
        ys = [value for _, y1, _, y2, _, _ in segments for value in (y1, y2)]
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        span_x, span_y = max(right - left, 1e-9), max(bottom - top, 1e-9)
        scale = min(drawing.width() / span_x, drawing.height() / span_y)
        offset_x = drawing.center().x() - (left + right) * scale / 2
        offset_y = drawing.center().y() - (top + bottom) * scale / 2
        painter.setClipRect(drawing)
        for x1, y1, x2, y2, move, tool in segments:
            color = print_segment_color(move, tool, color_by_tool=color_by_tool)
            style = Qt.PenStyle.DashLine if move == 0 and dashed_rapid else Qt.PenStyle.SolidLine
            width = 0.22 if move == 0 else 0.32
            painter.setPen(QPen(QColor(color), width * unit, style, Qt.PenCapStyle.RoundCap))
            painter.drawLine(
                QPointF(offset_x + x1 * scale, offset_y + y1 * scale),
                QPointF(offset_x + x2 * scale, offset_y + y2 * scale),
            )
        painter.setClipping(False)
    finally:
        painter.end()
