"""Orientation-only indexed rotary kinematics for FANUC milling.

Matrices act on column vectors. Joints in each branch compose in configured
order, so the second joint's matrix multiplies the first on the left.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app import paths

from ..geometry import matrix

# Preserve the established imports while sharing one geometry implementation.
IDENTITY = matrix.IDENTITY
Matrix = matrix.Matrix
Vector = matrix.Vector
_multiply = matrix.multiply
_rotation = matrix.rotation
_transpose = matrix.transpose
transform_point = matrix.transform_point
transform_vector = matrix.transform_vector

TCP_TABLE_PROFILES = frozenset({"5ax_table_ac", "5ax_table_bc", "5ax_table_ac_angled", "5ax_table_bc_angled"})
CATALOG_PATH = Path(__file__).with_name("rotary_profiles.json")
LOGGER = logging.getLogger(__name__)


def user_catalog_path() -> Path:
    """Keep edited profiles beside per-user settings, outside the installation."""
    return Path(paths.config_dir()) / "rotary_profiles.json"


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


def kinematics_snapshot(profile: MachineKinematics | None) -> tuple[str | None, str | None]:
    """Capture the effective definition once, without rereading user overrides."""
    if profile is None:
        return None, None
    definition = json.dumps(asdict(profile), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return definition, hashlib.sha256(definition.encode("utf-8")).hexdigest()


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


def _builtin_document() -> dict:
    """Read and validate installed profiles; never recover installation errors."""
    try:
        document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidKinematicsProfile(str(exc)) from exc
    parse_catalog(document)
    return document


def _read_user_overrides(path: Path, known_ids: set[str], *, ignore_errors: bool) -> dict | None:
    """Return valid overrides or an explicit damaged-file marker for the editor."""
    if not path.exists():
        return {"schema_version": 1, "profiles": []}
    try:
        overrides = json.loads(path.read_text(encoding="utf-8"))
        parse_catalog(overrides)
        unknown = {item["id"] for item in overrides["profiles"]} - known_ids
        if unknown:
            raise InvalidKinematicsProfile(f"Unknown profile override: {', '.join(sorted(unknown))}")
        return overrides
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidKinematicsProfile) as exc:
        if ignore_errors:
            LOGGER.warning("rotary_profile_override_invalid path=%s error=%s", path, exc)
            return None
        if isinstance(exc, InvalidKinematicsProfile):
            raise
        raise InvalidKinematicsProfile(str(exc)) from exc


def load_catalog(*, ignore_user_errors: bool = False) -> Mapping[str, MachineKinematics]:
    """Load overrides strictly by default; startup may explicitly use built-ins."""
    document = _builtin_document()
    overrides = _read_user_overrides(
        user_catalog_path(), {item["id"] for item in document["profiles"]}, ignore_errors=ignore_user_errors
    )
    if overrides is not None:
        replacements = {item["id"]: item for item in overrides["profiles"]}
        document["profiles"] = [replacements.get(item["id"], item) for item in document["profiles"]]
    return parse_catalog(document)


def profile_document(profile_id: str) -> dict:
    """Open valid overrides, or the built-in profile when the override is damaged."""
    document = _builtin_document()
    known = {item["id"] for item in document["profiles"]}
    if profile_id not in known:
        raise InvalidKinematicsProfile(f"Unknown profile: {profile_id}")
    overrides = _read_user_overrides(user_catalog_path(), known, ignore_errors=True)
    if overrides is not None:
        for item in overrides["profiles"]:
            if item["id"] == profile_id:
                return item
    return next(item for item in document["profiles"] if item["id"] == profile_id)


def _backup_invalid_override(path: Path) -> None:
    """Keep the exact damaged bytes before replacing the user's override file."""
    contents = path.read_bytes()
    fd, name = tempfile.mkstemp(prefix=path.name + ".invalid-", suffix=".bak", dir=path.parent)
    with os.fdopen(fd, "wb") as stream:
        stream.write(contents)
    LOGGER.warning("rotary_profile_override_recovered path=%s backup=%s", path, name)


def save_profile_override(profile_id: str, edited: dict) -> None:
    """Validate and atomically save; recover damaged overrides with a backup."""
    if edited.get("id") != profile_id:
        raise InvalidKinematicsProfile("Profile id cannot be changed")
    built_in = _builtin_document()
    known = {item["id"] for item in built_in["profiles"]}
    if profile_id not in known:
        raise InvalidKinematicsProfile(f"Unknown profile: {profile_id}")
    path = user_catalog_path()
    overrides = _read_user_overrides(path, known, ignore_errors=True)
    entries = [] if overrides is None else [item for item in overrides["profiles"] if item["id"] != profile_id]
    entries.append(edited)
    document = {"schema_version": 1, "profiles": entries}
    parse_catalog(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="rotary-profiles-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if overrides is None:
            _backup_invalid_override(path)
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
