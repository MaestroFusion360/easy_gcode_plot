"""Small helpers for dialogs that display metric values in inches on demand."""

from PyQt6.QtCore import QCoreApplication

MM_PER_INCH = 25.4


def _translated_suffix(inches: bool, context: str | None) -> str:
    source = " in" if inches else " mm"
    return QCoreApplication.translate(context, source) if context else source


def register_length_spinboxes(spinboxes) -> None:
    for spin in spinboxes:
        if hasattr(spin, "_metric_display_spec"):
            continue
        setattr(
            spin,
            "_metric_display_spec",
            (spin.minimum(), spin.maximum(), spin.singleStep(), spin.decimals()),
        )
        setattr(spin, "_display_inches", False)


def metric_value(spin) -> float:
    value = float(spin.value())
    return value * MM_PER_INCH if getattr(spin, "_display_inches", False) else value


def set_metric_value(spin, value: float) -> None:
    display_value = float(value) / MM_PER_INCH if getattr(spin, "_display_inches", False) else float(value)
    spin.setValue(display_value)


def set_length_units(spinboxes, inches: bool, *, suffix: bool = False, context: str | None = None) -> None:
    for spin in spinboxes:
        metric = metric_value(spin)
        minimum, maximum, step, decimals = getattr(spin, "_metric_display_spec")
        blocked = spin.blockSignals(True)
        if inches:
            spin.setDecimals(max(5, decimals))
            spin.setMinimum(minimum / MM_PER_INCH)
            spin.setMaximum(maximum / MM_PER_INCH)
            spin.setSingleStep(step / MM_PER_INCH)
            setattr(spin, "_display_inches", True)
            if suffix:
                spin.setSuffix(_translated_suffix(True, context))
            spin.setValue(metric / MM_PER_INCH)
        else:
            spin.setDecimals(decimals)
            spin.setMinimum(minimum)
            spin.setMaximum(maximum)
            spin.setSingleStep(step)
            setattr(spin, "_display_inches", False)
            if suffix:
                spin.setSuffix(_translated_suffix(False, context))
            spin.setValue(metric)
        spin.blockSignals(blocked)
