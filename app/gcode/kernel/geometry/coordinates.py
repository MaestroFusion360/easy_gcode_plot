"""Normalization helpers at the public coordinate-system boundary."""

from __future__ import annotations

WcsOffset = tuple[float, float] | tuple[float, float, float]
WcsOffsets = dict[int, WcsOffset]


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


def published_wcs_offsets(
    offsets: dict[int, tuple[float, float] | tuple[float, float, float]],
) -> tuple[tuple[int, tuple[float, float, float]], ...]:
    """Return a deterministic XYZ representation for ``ExecutionResult``."""
    normalized = []
    for code, values in sorted(offsets.items()):
        normalized.append((int(code), _xyz_offset(values)))
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
