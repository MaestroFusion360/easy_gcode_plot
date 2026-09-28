"""Print a snapshot of the current OpenGL plot view."""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtPrintSupport import QPrinter


def paint_plot_page(printer: QPrinter, image: QImage) -> None:
    """Center the captured plot within the printable page without distortion."""
    if image.isNull():
        return
    painter = QPainter(printer)
    try:
        page = QRectF(printer.pageRect(QPrinter.Unit.DevicePixel))
        scale = min(page.width() / image.width(), page.height() / image.height())
        width = image.width() * scale
        height = image.height() * scale
        target = QRectF(page.x() + (page.width() - width) / 2, page.y() + (page.height() - height) / 2, width, height)
        painter.drawImage(target, image)
    finally:
        painter.end()
