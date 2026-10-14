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
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True, slots=True)
class MachineKinematics:
    id: str
    name: str
    table_rotary_axes: tuple[RotaryAxis, ...]
    head_rotary_axes: tuple[RotaryAxis, ...]
    enabled: bool = False

    @property
    def continuous_c_table(self) -> bool:
        """The planar interpolator supports a single signed vertical C joint."""
        return (
            not self.head_rotary_axes
            and len(self.table_rotary_axes) == 1
            and self.table_rotary_axes[0].address == "C"
            and math.hypot(*self.table_rotary_axes[0].axis[:2]) < 1e-12
            and abs(abs(self.table_rotary_axes[0].axis[2]) - 1) < 1e-12
        )

    @property
    def tcp_table_supported(self) -> bool:
        """TCP requires a tilt followed by a vertical C spin on the table."""
        if self.head_rotary_axes or len(self.table_rotary_axes) != 2:
            return False
        tilt, spin = self.table_rotary_axes
        return (
            tilt.address in ("A", "B")
            and spin.address == "C"
            and math.hypot(*spin.axis[:2]) < 1e-12
            and abs(abs(spin.axis[2]) - 1) < 1e-12
            and math.hypot(*tilt.axis[:2]) > 1e-8
        )

    @property
    def horizontal_b_table(self) -> bool:
        """Preserve the horizontal camera for a single signed Y-axis B table."""
        return (
            not self.head_rotary_axes
            and len(self.table_rotary_axes) == 1
            and self.table_rotary_axes[0].address == "B"
            and math.hypot(self.table_rotary_axes[0].axis[0], self.table_rotary_axes[0].axis[2]) < 1e-12
        )

    @property
    def dmg_bc_frame_supported(self) -> bool:
        if not self.tcp_table_supported:
            return False
        tilt, spin = self.table_rotary_axes
        return tilt.address == "B" and math.dist(tilt.axis, (0, 2**-0.5, -(2**-0.5))) < 1e-6 and spin.axis[2] > 0

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


def _axis_limits(entry: dict) -> tuple[float | None, float | None]:
    if "min" not in entry and "max" not in entry:
        return None, None
    if "min" not in entry or "max" not in entry:
        raise ValueError("rotary limits require both min and max")
    values = entry["min"], entry["max"]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("rotary limits must be finite numbers")
    minimum, maximum = map(float, values)
    if minimum > maximum:
        raise ValueError("rotary min must not exceed max")
    return minimum, maximum


def rotary_limit_violations(profile, angles) -> tuple[tuple[str, float, float, float], ...]:
    """Compare executed angles directly, without wrapping or changing geometry."""
    if profile is None:
        return ()
    return tuple(
        (joint.address, angles.get(joint.address, 0.0), joint.minimum, joint.maximum)
        for joint in profile.table_rotary_axes + profile.head_rotary_axes
        if joint.minimum is not None
        and joint.maximum is not None
        and not joint.minimum <= angles.get(joint.address, 0.0) <= joint.maximum
    )


def _parse_axis(entry: object) -> RotaryAxis:
    address, raw_axis = entry["address"], entry["axis"]
    if address not in ("A", "B", "C") or not isinstance(raw_axis, list) or len(raw_axis) != 3:
        raise ValueError("invalid rotary address or axis vector")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw_axis):
        raise ValueError("axis vector must contain three finite numbers")
    magnitude = math.hypot(*raw_axis)
    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError("axis vector must be normalizable and nonzero")
    return RotaryAxis(address, tuple(float(v / magnitude) for v in raw_axis), *_axis_limits(entry))


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
                raise ValueError(f"duplicate profile identifier for {profile.name}")
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


def builtin_profile_ids() -> frozenset[str]:
    return frozenset(item["id"] for item in _builtin_document()["profiles"])


def legacy_profile_id(profile_id: str) -> str:
    """Stable namespace for old overrides, including saved GUI selections."""
    return "legacy_" + profile_id


def migrate_saved_profile_id(profile_id: str) -> str:
    users, _ = _read_user_document(ignore_errors=True)
    return next((item["id"] for item in users["profiles"] if item.get("legacy_source_id") == profile_id), profile_id)


def _read_user_document(*, ignore_errors: bool) -> tuple[dict, bool]:
    """Recover valid entries independently; leave original bytes untouched on read."""
    path = user_catalog_path()
    empty = {"schema_version": 1, "profiles": []}
    if not path.exists():
        return empty, False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(document, dict)
            or not isinstance(document.get("schema_version"), int)
            or document.get("schema_version") != 1
            or isinstance(document.get("schema_version"), bool)
        ):
            raise InvalidKinematicsProfile("unsupported schema_version")
        if not isinstance(document.get("profiles"), list):
            raise InvalidKinematicsProfile("profiles must be an array")
    except (OSError, UnicodeError, ValueError) as exc:
        if not ignore_errors:
            raise InvalidKinematicsProfile(str(exc)) from exc
        LOGGER.warning("rotary_profile_override_invalid path=%s error=%s", path, exc)
        return empty, True
    return _recover_user_entries(document)


def _recover_user_entries(document: dict) -> tuple[dict, bool]:
    builtins = builtin_profile_ids()
    # Reserve explicit IDs before translating legacy ones, so neither is lost.
    reserved = {
        item.get("id") for item in document["profiles"] if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    entries, seen = [], set()
    changed = False
    for item in document["profiles"]:
        try:
            profile = _parse_profile(item)
            if profile.id in seen:
                raise ValueError(f"duplicate profile identifier for {profile.name}")
            seen.add(profile.id)
            if profile.id in builtins:
                item = dict(item)
                candidate = legacy_profile_id(profile.id)
                while candidate in reserved:
                    candidate = "legacy_" + candidate
                item["legacy_source_id"] = profile.id
                item["id"] = candidate
                reserved.add(candidate)
                changed = True
            entries.append(item)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            LOGGER.warning("rotary_profile_entry_invalid error=%s", exc)
            changed = True
    return {"schema_version": 1, "profiles": entries}, changed


def load_catalog(*, ignore_user_errors: bool = True) -> Mapping[str, MachineKinematics]:
    document = _builtin_document()
    users, _ = _read_user_document(ignore_errors=ignore_user_errors)
    document["profiles"].extend(users["profiles"])
    return parse_catalog(document)


def profile_document(profile_id: str) -> dict:
    document = _builtin_document()
    users, _ = _read_user_document(ignore_errors=True)
    for item in document["profiles"] + users["profiles"]:
        if item["id"] == profile_id:
            return item
    raise InvalidKinematicsProfile("The selected kinematics profile is missing.")


def profile_from_snapshot(definition: str | None) -> MachineKinematics | None:
    """Use the executed definition for export, without rereading mutable settings."""
    if not definition:
        return None
    item = json.loads(definition)
    for branch in ("table_rotary_axes", "head_rotary_axes"):
        for joint in item[branch]:
            if joint.get("minimum") is not None:
                joint.update(min=joint["minimum"], max=joint["maximum"])
    return _parse_profile(
        {
            "id": item["id"],
            "name": item["name"],
            "enabled": item["enabled"],
            "table": item["table_rotary_axes"],
            "head": item["head_rotary_axes"],
        }
    )


def _backup_invalid_override(path: Path) -> None:
    """Keep exact original bytes before migration or damaged-file recovery."""
    contents = path.read_bytes()
    fd, name = tempfile.mkstemp(prefix=path.name + ".invalid-", suffix=".bak", dir=path.parent)
    with os.fdopen(fd, "wb") as stream:
        stream.write(contents)
    LOGGER.warning("rotary_profile_override_recovered path=%s backup=%s", path, name)


def save_user_profiles(profiles: list[dict]) -> None:
    """Validate the complete user catalog, then replace it atomically."""
    document = {"schema_version": 1, "profiles": profiles}
    parsed = parse_catalog(document)
    if parsed.keys() & builtin_profile_ids():
        raise InvalidKinematicsProfile("Built-in profiles are read-only")
    path = user_catalog_path()
    _, needs_backup = _read_user_document(ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="rotary-profiles-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if needs_backup:
            _backup_invalid_override(path)
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def save_profile_override(profile_id: str, edited: dict) -> None:
    """Save a user copy while protecting all installed definitions."""
    if edited.get("id") != profile_id:
        raise InvalidKinematicsProfile("Profile id cannot be changed")
    if profile_id in builtin_profile_ids():
        raise InvalidKinematicsProfile("Built-in profiles are read-only")
    users, _ = _read_user_document(ignore_errors=True)
    entries = [item for item in users["profiles"] if item["id"] != profile_id]
    save_user_profiles([*entries, edited])
