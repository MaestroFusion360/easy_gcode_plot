"""Shared numeric display formatting."""


def format_gcode_number(value: float | int | None) -> str:
    """Format a numeric value exactly as the application emits G-code numbers."""
    if value is None:
        return ""
    if value == 0:
        return "0"
    return f"{value:.3f}".rstrip("0").rstrip(".")
