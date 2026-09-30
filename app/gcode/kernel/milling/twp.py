"""FANUC G68.2 three-plus-two tilted working-plane frame."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..api.resources import SemanticError
from .kinematics import (
    IDENTITY,
    MachineKinematics,
    Matrix,
    Vector,
    _multiply,
    _rotation,
    _transpose,
    effective_orientation,
    transform_vector,
)


def supports_twp_kinematics(profile: MachineKinematics) -> bool:
    """Whether the profile has two distinct rotary joints for tool-axis control."""
    joints = profile.table_rotary_axes + profile.head_rotary_axes
    return len(joints) == 2 and len({joint.address for joint in joints}) == 2


def euler_zxz(i: float, j: float, k: float) -> Matrix:
    """Map local column vectors into WCS with intrinsic Z-X-Z Euler angles."""
    return _multiply(
        _multiply(_rotation((0.0, 0.0, 1.0), i), _rotation((1.0, 0.0, 0.0), j)), _rotation((0.0, 0.0, 1.0), k)
    )


def solve_table_orientation(
    profile: MachineKinematics, orientation: Matrix, current: dict[str, float]
) -> dict[str, float]:
    """Solve two rotary joint angles so the physical tool axis follows +Z."""
    if not supports_twp_kinematics(profile):
        raise SemanticError("TWP_KINEMATICS_REQUIRED", "G68.2 requires two distinct rotary axes", "unsupported")
    target = transform_vector(orientation, (0.0, 0.0, 1.0))
    joints = profile.table_rotary_axes + profile.head_rotary_axes
    addresses = [joint.address for joint in joints]

    def error_at(values: tuple[float, float]) -> float:
        candidate = dict(current)
        candidate.update(zip(addresses, values))
        achieved = transform_vector(effective_orientation(profile, candidate), (0.0, 0.0, 1.0))
        return math.dist(achieved, target)

    # Damped finite-difference least squares, seeded around the current position.
    # Multiple starts avoid common local minima in mixed and head-head layouts.
    starts = [tuple(current[address] for address in addresses)]
    starts.extend((a, b) for a in (-90.0, 0.0, 90.0, 180.0) for b in (-90.0, 0.0, 90.0, 180.0))
    candidates = []
    for start in starts:
        values = list(start)
        for _ in range(120):
            residual_error = error_at(tuple(values))
            if residual_error < 1e-9:
                break
            eps = 1e-4
            base = dict(current)
            base.update(zip(addresses, values))
            achieved = transform_vector(effective_orientation(profile, base), (0.0, 0.0, 1.0))
            columns = []
            for index in range(2):
                shifted = values.copy()
                shifted[index] += eps
                probe = dict(current)
                probe.update(zip(addresses, shifted))
                vector = transform_vector(effective_orientation(profile, probe), (0.0, 0.0, 1.0))
                columns.append(tuple((vector[i] - achieved[i]) / eps for i in range(3)))
            residual = tuple(target[i] - achieved[i] for i in range(3))
            aa = sum(v * v for v in columns[0]) + 1e-8
            bb = sum(v * v for v in columns[1]) + 1e-8
            ab = sum(columns[0][i] * columns[1][i] for i in range(3))
            ar = sum(columns[0][i] * residual[i] for i in range(3))
            br = sum(columns[1][i] * residual[i] for i in range(3))
            determinant = aa * bb - ab * ab
            if abs(determinant) < 1e-14:
                break
            delta = ((ar * bb - br * ab) / determinant, (br * aa - ar * ab) / determinant)
            scale = min(1.0, 30.0 / max(abs(delta[0]), abs(delta[1]), 1e-12))
            trial = [values[i] + delta[i] * scale for i in range(2)]
            if error_at(tuple(trial)) < residual_error:
                values = trial
            else:
                break
        candidate = dict(current)
        for address, angle in zip(addresses, values):
            candidate[address] = angle + 360.0 * round((current[address] - angle) / 360.0)
        candidates.append(
            (
                error_at(tuple(candidate[address] for address in addresses)),
                sum(abs(candidate[a] - current[a]) for a in addresses),
                candidate,
            )
        )
    error, _, solved = min(candidates, key=lambda item: (round(item[0], 7), item[1]))
    if error > 1e-5:
        raise SemanticError(
            "TWP_ORIENTATION_UNREACHABLE", "G53.1 tool axis is unreachable by the selected kinematics", "unsupported"
        )
    return solved


@dataclass
class TiltedWorkPlane:
    active: bool = False
    origin: Vector = (0.0, 0.0, 0.0)
    angles: Vector = (0.0, 0.0, 0.0)
    orientation: Matrix = IDENTITY
    tool_axis_control: bool = False
    start_block: int | None = None

    def apply(self, point: Vector) -> Vector:
        rotated = transform_vector(self.orientation, point)
        return tuple(rotated[index] + self.origin[index] for index in range(3))  # type: ignore[return-value]

    def inverse(self, point: Vector) -> Vector:
        shifted = tuple(point[index] - self.origin[index] for index in range(3))
        return transform_vector(_transpose(self.orientation), shifted)

    def vector(self, value: Vector) -> Vector:
        return transform_vector(self.orientation, value)

    def configure(self, origin: Vector, angles: Vector, block_index: int) -> None:
        if not all(math.isfinite(value) for value in origin + angles):
            raise ValueError("G68.2 requires finite origin and Euler angles")
        self.active = True
        self.origin = origin
        self.angles = angles
        self.orientation = euler_zxz(*angles)
        self.tool_axis_control = False
        self.start_block = block_index

    def clear(self) -> None:
        self.active = False
        self.origin = (0.0, 0.0, 0.0)
        self.angles = (0.0, 0.0, 0.0)
        self.orientation = IDENTITY
        self.tool_axis_control = False
        self.start_block = None
