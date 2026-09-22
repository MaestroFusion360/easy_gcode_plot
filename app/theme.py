"""Application theming: Qt palette/style and theme-aware UI colors."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPalette, QPolygon
from PyQt6.QtWidgets import QAbstractSpinBox, QProxyStyle, QStyle, QStyleFactory

THEMES = ("light", "dark")
DEFAULT_THEME = "light"

# Prefer the native platform QStyle.  Qt 6.7+ provides a Windows 11 style with
# native dark-mode support, but Windows 10 still defaults to the legacy
# ``windowsvista`` style.  That style is backed by the native theme engine and
# does not reliably honor an application QPalette in dark mode.  On that one
# compatibility path we mirror Qt's own ``windows:darkmode=2`` strategy: switch
# to the palette-aware ``windows`` style and apply our dark palette.  Windows 11
# keeps its native style unchanged.


_EDITOR_COLORS = {
    "light": {
        "paper": "#ffffff",
        "default_text": "#000000",
        "rapid": "#ff0000",
        "linear": "#2ecc71",
        "circular": "#0000ff",
        "caret_line": "#e8e8ff",
        "caret_foreground": "#000000",
        "margin_foreground": "#808080",
        "margin_background": "#f0f0f0",
        "selection_background": "#cce8ff",
    },
    "dark": {
        "paper": "#1e1e1e",
        "default_text": "#d4d4d4",
        "rapid": "#f48771",
        "linear": "#89d185",
        "circular": "#569cd6",
        "caret_line": "#2a2d2e",
        "caret_foreground": "#e6e6e6",
        "margin_foreground": "#9a9a9a",
        "margin_background": "#252526",
        "selection_background": "#264f78",
    },
}

PLOT_DEFAULTS = {
    "light": {
        "background": "#ffffff",
        "grid": "#808080",
        "rapid": "#d02020",
        "linear": "#0000ff",
        "arc": "#008000",
        "current": "#00b7ff",
        "tool": "#4d99ff",
        "stl": "#b0b0b0",
    },
    "dark": {
        "background": "#1e1e1e",
        "grid": "#4a4a4a",
        "rapid": "#ff6b6b",
        "linear": "#6fa8ff",
        "arc": "#5fd38a",
        "current": "#4fd2ff",
        "tool": "#7fb2ff",
        "stl": "#9aa0a6",
    },
}

PLOT_COLOR_ATTRIBUTES = {
    "background": "plotBackground",
    "grid": "plotGridColor",
    "rapid": "plotRapidColor",
    "linear": "plotLineColor",
    "arc": "plotArcColor",
    "current": "plotCurrentColor",
    "tool": "plotToolColor",
    "stl": "stlColor",
}

_STATE = {
    "palette": None,
    "style_name": None,
    "applied": None,
    "palette_fallback": False,
    "style_fallback": False,
}

# The legacy ``windows`` style hard-codes dark spin-box arrows even when the
# application palette is dark.  Styling QAbstractSpinBox with an application
# stylesheet is tempting, but on Windows 10 QStyleSheetStyle then owns the
# spin-box subcontrols and can suppress the proxy-style arrow primitives.
# Keep the native control geometry and paint only the two arrow glyphs after
# the base style has rendered the spin box.


class _DarkSpinBoxArrowStyle(QProxyStyle):
    """Overlay visible spin-box arrows on the legacy Windows dark fallback."""

    _ARROWS = (
        (QStyle.SubControl.SC_SpinBoxUp, True),
        (QStyle.SubControl.SC_SpinBoxDown, False),
    )

    def drawComplexControl(self, control, option, painter, widget=None):  # noqa: N802 - Qt API
        super().drawComplexControl(control, option, painter, widget)
        if control != QStyle.ComplexControl.CC_SpinBox or not isinstance(widget, QAbstractSpinBox):
            return
        if option.buttonSymbols == QAbstractSpinBox.ButtonSymbols.NoButtons:
            return

        group = (
            QPalette.ColorGroup.Active
            if option.state & QStyle.StateFlag.State_Enabled
            else QPalette.ColorGroup.Disabled
        )
        color = option.palette.color(group, QPalette.ColorRole.ButtonText)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for subcontrol, points_up in self._ARROWS:
            if not option.subControls & subcontrol:
                continue
            rect = self.subControlRect(control, option, subcontrol, widget)
            if rect.width() < 3 or rect.height() < 3:
                continue
            center = rect.center()
            half_width = max(2, min(4, (rect.width() - 4) // 2))
            half_height = max(2, min(3, (rect.height() - 2) // 2))
            if points_up:
                points = QPolygon(
                    [
                        QPoint(center.x() - half_width, center.y() + half_height // 2),
                        QPoint(center.x() + half_width, center.y() + half_height // 2),
                        QPoint(center.x(), center.y() - half_height),
                    ]
                )
            else:
                points = QPolygon(
                    [
                        QPoint(center.x() - half_width, center.y() - half_height // 2),
                        QPoint(center.x() + half_width, center.y() - half_height // 2),
                        QPoint(center.x(), center.y() + half_height),
                    ]
                )
            painter.drawPolygon(points)
        painter.restore()


def reset_theme_state() -> None:
    """Forget the applied theme so the next call re-applies its colors."""
    _STATE["applied"] = None


def current_theme() -> str | None:
    """Return the theme currently applied to the application, if any."""
    return _STATE["applied"]


def normalize_theme(value) -> str:
    """Return a supported theme name, defaulting to light."""
    text = str(value or "").strip().lower()
    return text if text in THEMES else DEFAULT_THEME


def editor_colors(theme) -> dict[str, str]:
    """Return the editor/lexer color table for *theme*."""
    return dict(_EDITOR_COLORS[normalize_theme(theme)])


def plot_defaults(theme) -> dict[str, str]:
    """Return the standard plot color defaults for *theme*."""
    return dict(PLOT_DEFAULTS[normalize_theme(theme)])


def themed_plot_value(current, key: str, theme) -> str:
    """Return the theme default unless *current* is a user-customized color."""
    known = {PLOT_DEFAULTS["light"][key].lower(), PLOT_DEFAULTS["dark"][key].lower()}
    if str(current).strip().lower() not in known:
        return current
    return PLOT_DEFAULTS[normalize_theme(theme)][key]


def apply_application_theme(app, theme) -> None:
    """Apply *theme* with a Windows 10 compatibility path for native widgets."""
    target = normalize_theme(theme)
    if _STATE["applied"] == target:
        return

    _remember_platform_appearance(app)

    if target == "light":
        # Restore a legacy Windows style first: changing QStyle can reset the
        # application palette, so the startup palette is restored last.
        _restore_platform_style(app)
        _set_color_scheme(app, target)
        if _STATE["palette_fallback"]:
            app.setPalette(QPalette(_STATE["palette"]))
            _STATE["palette_fallback"] = False
        _STATE["applied"] = target
        return

    scheme_applied = _set_color_scheme(app, target)
    windows_compat = _needs_windows_dark_compatibility(sys.platform, _style_name(app))
    if windows_compat:
        _enable_windows_dark_compatibility(app)

    if windows_compat or not scheme_applied:
        # ``QStyleHints.setColorScheme(Dark)`` is only a platform hint.  On
        # Windows 10 the legacy Windows Vista style can report the requested
        # scheme while still painting menus, toolbars and input controls with the
        # light native theme.  A palette-aware Windows style plus this palette
        # gives Win10 a complete dark UI; Win11 remains on its native style.
        app.setPalette(_dark_palette())
        _STATE["palette_fallback"] = True

    _STATE["applied"] = target


def _remember_platform_appearance(app) -> None:
    """Snapshot startup palette/style so compatibility changes can be undone."""
    if _STATE["palette"] is None:
        _STATE["palette"] = QPalette(app.palette())
    if _STATE["style_name"] is None:
        _STATE["style_name"] = _style_name(app)


def _style_name(app) -> str:
    """Return the current Qt style key in normalized form."""
    return str(app.style().objectName() or "").strip().lower()


def _needs_windows_dark_compatibility(platform_name: str, style_name: str) -> bool:
    """Return whether a Windows style needs the palette-based dark fallback."""
    return platform_name == "win32" and style_name in {"windows", "windowsvista"}


def _enable_windows_dark_compatibility(app) -> None:
    """Use a palette-aware Windows base plus explicit dark spin-box arrows."""
    if _style_name(app) == "windowsvista":
        fallback = QStyleFactory.create("windows")
        if fallback is not None:
            app.setStyle(fallback)

    if not isinstance(app.style(), _DarkSpinBoxArrowStyle):
        style_name = _style_name(app)
        base_style = QStyleFactory.create(style_name) if style_name else None
        if base_style is not None:
            proxy = _DarkSpinBoxArrowStyle(base_style)
            proxy.setObjectName(style_name)
            app.setStyle(proxy)
            # Light mode restores the exact startup platform style.  This flag
            # covers both Vista->Windows and the temporary arrow proxy.
            _STATE["style_fallback"] = True


def _restore_platform_style(app) -> None:
    """Restore the startup platform style after leaving the dark fallback."""
    if not _STATE["style_fallback"]:
        return
    style_name = _STATE["style_name"]
    restored = QStyleFactory.create(style_name) if style_name else None
    if restored is not None:
        app.setStyle(restored)
        _STATE["style_fallback"] = False


def _set_color_scheme(app, target: str) -> bool:
    """Request a native Qt color scheme and report whether it became effective."""
    hints = app.styleHints()
    setter = getattr(hints, "setColorScheme", None)
    color_scheme = getattr(Qt, "ColorScheme", None)
    if setter is None or color_scheme is None:
        return False

    requested = color_scheme.Dark if target == "dark" else color_scheme.Light
    setter(requested)
    return hints.colorScheme() == requested


def apply_editor_theme(editor, lexer, theme) -> None:
    """Apply paper, caret, margin, selection, and lexer colors for *theme*."""
    colors = editor_colors(theme)
    paper = QColor(colors["paper"])
    editor.setPaper(paper)
    editor.setColor(QColor(colors["default_text"]))
    editor.setCaretLineBackgroundColor(QColor(colors["caret_line"]))
    editor.setCaretForegroundColor(QColor(colors["caret_foreground"]))
    editor.setMarginsBackgroundColor(QColor(colors["margin_background"]))
    editor.setMarginsForegroundColor(QColor(colors["margin_foreground"]))
    editor.setSelectionBackgroundColor(QColor(colors["selection_background"]))
    if lexer is not None:
        # A lexer overrides the editor's default style, so the paper must also be
        # set on the lexer and the document re-coloured for the change to show.
        lexer.apply_theme(colors)
    editor.recolor()


def apply_dialog_theme(dialog) -> None:
    """Give transient dialogs a complete palette on native Windows dark mode."""
    if current_theme() != "dark":
        return
    dialog.setPalette(_dark_palette())
    dialog.setAutoFillBackground(True)
    dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dialog.setStyleSheet(
        "QDialog#ExecutionDialog { background-color: #1f1f1f; color: #e6e6e6; }"
        "QDialog#ExecutionDialog QLabel { color: #e6e6e6; }"
        "QDialog#ExecutionDialog QPushButton {"
        " background-color: #333337; color: #e6e6e6; border: 1px solid #4a4a4a;"
        " border-radius: 3px; padding: 5px 14px; }"
        "QDialog#ExecutionDialog QPushButton:disabled { color: #7a7a7a; }"
    )


def _dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor("#1f1f1f")
    base = QColor("#252526")
    alt_base = QColor("#2d2d30")
    text = QColor("#e6e6e6")
    disabled_text = QColor("#7a7a7a")
    button = QColor("#333337")
    highlight = QColor("#2a6ea6")

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5555"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#4fa3ff"))
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_text)
    return palette
