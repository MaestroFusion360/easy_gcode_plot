"""Orientation-only indexed rotary kinematics for FANUC milling.

Matrices act on column vectors. Joints in each branch compose in configured
order, so the second joint's matrix multiplies the first on the left.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]
IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
CATALOG_PATH = Path(__file__).with_name("rotary_profiles.json")


class InvalidKinematicsProfile(ValueError):
    """A catalog or selected profile does not satisfy the rotary schema."""


@dataclass(frozen=True, slots=True)
class RotaryAxis:
    address: str
    axis: Vector


@dataclass(frozen=True, slots=True)
class MachineKinematics:
    id: str
    name: str
    table_rotary_axes: tuple[RotaryAxis, ...]
    head_rotary_axes: tuple[RotaryAxis, ...]
    enabled: bool = False

    @property
    def addresses(self) -> frozenset[str]:
        return frozenset(j.address for j in self.table_rotary_axes + self.head_rotary_axes)


def _multiply(a: Matrix, b: Matrix) -> Matrix:
    rows = (tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return tuple(rows)  # type: ignore[return-value]


def _transpose(a: Matrix) -> Matrix:
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _rotation(axis: Vector, degrees: float) -> Matrix:
    x, y, z = axis
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    t = 1.0 - c
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def _branch(joints: tuple[RotaryAxis, ...], angles: dict[str, float]) -> Matrix:
    result = IDENTITY
    for joint in joints:
        result = _multiply(_rotation(joint.axis, angles.get(joint.address, 0.0)), result)
    return result


def effective_orientation(profile: MachineKinematics, angles: dict[str, float]) -> Matrix:
    """Tool orientation using the profile's signed rotary-axis convention."""
    return _multiply(
        _transpose(_branch(profile.head_rotary_axes, angles)),
        _branch(profile.table_rotary_axes, angles),
    )


def point_orientation(profile: MachineKinematics, angles: dict[str, float]) -> Matrix:
    """Map a machine-frame tool-tip point using the table's signed rotation."""
    return _branch(profile.table_rotary_axes, angles)


def transform_vector(orientation: Matrix, vector: Vector) -> Vector:
    return tuple(sum(row[i] * vector[i] for i in range(3)) for row in orientation)  # type: ignore[return-value]


def transform_point(orientation: Matrix, point: Vector) -> Vector:
    return transform_vector(orientation, point)


def _parse_axis(entry: object) -> RotaryAxis:
    address, raw_axis = entry["address"], entry["axis"]
    if address not in ("A", "B", "C") or not isinstance(raw_axis, list) or len(raw_axis) != 3:
        raise ValueError("invalid rotary address or axis vector")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw_axis):
        raise ValueError("axis vector must contain three finite numbers")
    magnitude = math.hypot(*raw_axis)
    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError("axis vector must be normalizable and nonzero")
    return RotaryAxis(address, tuple(float(v / magnitude) for v in raw_axis))


def _parse_profile(item: object) -> MachineKinematics:
    if not isinstance(item, dict):
        raise ValueError("profile must be an object")
    profile_id, name = item["id"], item["name"]
    if not isinstance(profile_id, str) or not profile_id.strip() or not isinstance(name, str) or not name.strip():
        raise ValueError("id and name must be nonempty strings")
    enabled = item["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    branches = []
    for branch in ("table", "head"):
        source = item[branch]
        if not isinstance(source, list):
            raise ValueError(f"{branch} must be an array")
        branches.append(tuple(_parse_axis(entry) for entry in source))
    table, head = branches[0], branches[1]
    addresses = [axis.address for axis in table + head]
    if not 1 <= len(addresses) <= 2 or len(set(addresses)) != len(addresses):
        raise ValueError("a profile requires one or two distinct rotary addresses")
    return MachineKinematics(profile_id, name, table, head, enabled)


def parse_catalog(document: object) -> Mapping[str, MachineKinematics]:
    """Validate an in-memory catalog and return immutable profiles by id."""
    try:
        if (
            not isinstance(document, dict)
            or not isinstance(document.get("schema_version"), int)
            or isinstance(document.get("schema_version"), bool)
            or document["schema_version"] != 1
        ):
            raise ValueError("unsupported schema_version")
        items = document["profiles"]
        if not isinstance(items, list):
            raise ValueError("profiles must be an array")
        registry: dict[str, MachineKinematics] = {}
        for item in items:
            profile = _parse_profile(item)
            if profile.id in registry:
                raise ValueError(f"duplicate profile id: {profile.id}")
            registry[profile.id] = profile
        return MappingProxyType(registry)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise InvalidKinematicsProfile(str(exc)) from exc


def load_catalog() -> Mapping[str, MachineKinematics]:
    try:
        return parse_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidKinematicsProfile(str(exc)) from exc
