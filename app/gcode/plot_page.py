"""Page layout and line styles shared by Print and HTML projections."""


def fit_plot_bounds(bounds, drawing):
    """Return scale and translation fitting geometry into a page rectangle."""
    left, right, top, bottom = bounds
    x, y, width, height = drawing
    scale = min(width / max(right - left, 1e-9), height / max(bottom - top, 1e-9))
    return scale, x + width / 2 - (left + right) * scale / 2, y + height / 2 - (top + bottom) * scale / 2


def print_line_style(move):
    """Return Print's color and physical pen width in millimetres."""
    color = "#b94a4a" if move == 0 else "#176e54" if move in (2, 3) else "#172d49"
    return color, 0.22 if move == 0 else 0.32
