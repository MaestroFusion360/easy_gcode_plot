"""Orientation-only indexed rotary kinematics for FANUC milling.

Matrices act on column vectors. Joints in each branch compose in configured
order, so the second joint's matrix multiplies the first on the left.
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app import settings as app_settings

Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]
IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
CATALOG_PATH = Path(__file__).with_name("rotary_profiles.json")
LOGGER = logging.getLogger(__name__)


def user_catalog_path() -> Path:
    """Keep edited profiles beside per-user settings, outside the installation."""
    return Path(app_settings.config_path()).with_name("rotary_profiles.json")


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


def load_catalog(*, ignore_user_errors: bool = False) -> Mapping[str, MachineKinematics]:
    """Load built-in profiles and optional per-user overrides.

    Core callers remain strict by default. GUI callers may ignore a malformed
    user override so a damaged configuration cannot prevent application startup.
    """
    try:
        document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidKinematicsProfile(str(exc)) from exc

    built_in = parse_catalog(document)
    overrides_path = user_catalog_path()
    if not overrides_path.exists():
        return built_in

    try:
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        parse_catalog(overrides)
        replacements = {item["id"]: item for item in overrides["profiles"]}
        known = {item["id"] for item in document["profiles"]}
        document["profiles"] = [replacements.pop(item["id"], item) for item in document["profiles"]]
        if replacements:
            raise InvalidKinematicsProfile(f"Unknown profile override: {', '.join(sorted(replacements))}")
        if known != {item["id"] for item in document["profiles"]}:
            raise InvalidKinematicsProfile("Profile overrides must retain the built-in ids")
        return parse_catalog(document)
    except (OSError, json.JSONDecodeError, InvalidKinematicsProfile) as exc:
        if ignore_user_errors:
            LOGGER.warning("rotary_profile_override_invalid path=%s error=%s", overrides_path, exc)
            return built_in
        if isinstance(exc, InvalidKinematicsProfile):
            raise
        raise InvalidKinematicsProfile(str(exc)) from exc


def profile_document(profile_id: str) -> dict:
    """Return the editable JSON entry currently effective for a profile."""
    load_catalog()
    path = user_catalog_path()
    if path.exists():
        overrides = json.loads(path.read_text(encoding="utf-8"))
        for item in overrides["profiles"]:
            if item["id"] == profile_id:
                return item
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return next(item for item in document["profiles"] if item["id"] == profile_id)


def save_profile_override(profile_id: str, edited: dict) -> None:
    """Validate and atomically persist one user profile override."""
    if edited.get("id") != profile_id:
        raise InvalidKinematicsProfile("Profile id cannot be changed")
    current = load_catalog()
    if profile_id not in current:
        raise InvalidKinematicsProfile(f"Unknown profile: {profile_id}")
    path = user_catalog_path()
    overrides = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {
            "schema_version": 1,
            "profiles": [],
        }
    )
    entries = [item for item in overrides["profiles"] if item["id"] != profile_id]
    entries.append(edited)
    document = {"schema_version": 1, "profiles": entries}
    parse_catalog(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="rotary-profiles-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
