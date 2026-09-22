"""Normalization helpers at the public coordinate-system boundary."""

from __future__ import annotations

WcsOffset = tuple[float, float] | tuple[float, float, float]
WcsOffsets = dict[int, WcsOffset]
EXTENDED_WCS_BASE = 1000


def is_extended_wcs_gcode(value: int | float | None) -> bool:
    """Return whether an evaluated G word selects FANUC G54.1."""
    return value is not None and abs(float(value) - 54.1) <= 1e-9


def extended_wcs_id(p_number: int) -> int:
    """Map G54.1 P1-P99 to an internal WCS identifier."""
    if not float(p_number).is_integer() or not 1 <= int(p_number) <= 99:
        raise ValueError("G54.1 P must be an integer from 1 to 99")
    return EXTENDED_WCS_BASE + int(p_number)


def extended_wcs_from_gcode(gcode: int | float | None, words) -> int | None:
    """Resolve an evaluated G54.1 P selection to its internal identifier."""
    if not is_extended_wcs_gcode(gcode):
        return None
    if "P" not in words or not float(words["P"]).is_integer():
        raise ValueError("G54.1 requires an integer P from 1 to 99")
    return extended_wcs_id(int(words["P"]))


def programmed_wcs_id(words) -> int:
    """Resolve the supported FANUC G10 L2/L20 work-offset target."""
    if "L" not in words or "P" not in words:
        raise ValueError("G10 work-offset programming requires integer L and P values")
    l_value = float(words["L"])
    p_value = float(words["P"])
    if not l_value.is_integer() or not p_value.is_integer():
        raise ValueError("G10 work-offset programming requires integer L and P values")
    l_number = int(l_value)
    p_number = int(p_value)
    if l_number == 2 and 1 <= p_number <= 6:
        return 53 + p_number
    if l_number == 20 and 1 <= p_number <= 99:
        return EXTENDED_WCS_BASE + p_number
    raise ValueError("G10 supports L2 P1-P6 and L20 P1-P99 work-offset programming")


def _xyz_offset(values: WcsOffset) -> tuple[float, float, float]:
    if len(values) == 2:
        x, z = values
        return float(x), 0.0, float(z)
    x, y, z = values
    return float(x), float(y), float(z)


def milling_wcs_offsets(
    wcs_offsets: WcsOffsets | None,
) -> dict[int, tuple[float, float, float]]:
    """Normalize public WCS values to XYZ for the milling kernel."""
    return {code: _xyz_offset(values) for code, values in (wcs_offsets or {}).items()}


def turning_wcs_offsets(wcs_offsets: WcsOffsets | None) -> dict[int, tuple[float, float]]:
    """Normalize public WCS values to XZ for the turning kernel."""
    return {code: (xyz[0], xyz[2]) for code, values in (wcs_offsets or {}).items() if (xyz := _xyz_offset(values))}


def milling_extended_wcs_offsets(wcs_offsets: WcsOffsets | None) -> dict[int, tuple[float, float, float]]:
    """Normalize public G54.1 P1-P99 offsets to internal WCS identifiers."""
    return {extended_wcs_id(p_number): _xyz_offset(values) for p_number, values in (wcs_offsets or {}).items()}


def turning_extended_wcs_offsets(wcs_offsets: WcsOffsets | None) -> dict[int, tuple[float, float]]:
    """Normalize public turning G54.1 offsets to internal XZ coordinates."""
    return {
        extended_wcs_id(p_number): (xyz[0], xyz[2])
        for p_number, values in (wcs_offsets or {}).items()
        if (xyz := _xyz_offset(values))
    }


def published_wcs_offsets(
    offsets: dict[int, tuple[float, float] | tuple[float, float, float]],
) -> tuple[tuple[int, tuple[float, float, float]], ...]:
    """Return a deterministic XYZ representation for ``ExecutionResult``."""
    normalized = []
    for code, values in sorted(offsets.items()):
        if int(code) >= EXTENDED_WCS_BASE:
            continue
        normalized.append((int(code), _xyz_offset(values)))
    return tuple(normalized)


def published_extended_wcs_offsets(
    offsets: dict[int, tuple[float, float] | tuple[float, float, float]],
) -> tuple[tuple[int, tuple[float, float, float]], ...]:
    """Return deterministic public P-number mappings for G54.1 offsets."""
    normalized = []
    for code, values in sorted(offsets.items()):
        if EXTENDED_WCS_BASE < int(code) <= EXTENDED_WCS_BASE + 99:
            normalized.append((int(code) - EXTENDED_WCS_BASE, _xyz_offset(values)))
    return tuple(normalized)


def rebase_work_position(
    position: tuple[float, ...],
    old_offset: tuple[float, ...],
    new_offset: tuple[float, ...],
) -> tuple[float, ...]:
    """Preserve machine position while switching from one WCS offset to another."""
    if not len(position) == len(old_offset) == len(new_offset):
        raise ValueError("WCS position and offsets must have the same dimensionality")
    return tuple(value + old - new for value, old, new in zip(position, old_offset, new_offset, strict=True))
