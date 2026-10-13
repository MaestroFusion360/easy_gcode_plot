"""Editable comment recognition rules; executable CNC facts remain in discovery."""

import json
import logging
import re
from copy import deepcopy

from app.tools.definitions import MILLING_TOOL_TYPES, TURNING_TOOL_TYPES
from app.tools.discovery_patterns import DEFAULT_TYPE_HINTS, compiled_hints

SETTINGS_KEY = "CNC/TOOL_DISCOVERY"
_CYRILLIC = re.compile(r"[\u0400-\u052f\u2de0-\u2dff\ua640-\ua69f]")
DEFAULT_DIMENSIONS = {
    "nose_radius": "R|NR",
    "groove_width": "H|W|WIDTH",
    "turning_diameter": "D|DIA|DIAMETER",
    "milling_diameter": r"D|DIA\.?|DIAM\.?|DIAMETER|Ø|⌀",
    "corner_radius": r"CR|RE|CORNER[\s_]+RADIUS",
    "taper_angle": r"TAPER[\s_]*ANGLE|TAPER|ANGLE|B",
    "tip_angle": r"TIP[\s_]*ANGLE|POINT[\s_]*ANGLE|TAPER|ANGLE",
    "chamfer_angle": r"CHAMFER[\s_]*ANGLE|TAPER|ANGLE",
    "tip_diameter": r"TIP[\s_]*(?:DIAMETER|DIA|D)|TD",
    "shank_diameter": r"SHANK[\s_]*(?:DIAMETER|DIA|D)|SD",
    "flute_length": r"FL|FLUTELENGTH|FLUTE\s+LENGTH",
    "body_length": r"BL|BODYLENGTH|BODY\s+LENGTH",
    "total_length": "L|LENGTH",
}


def default_profile():
    hints = [list(item) for item in DEFAULT_TYPE_HINTS]
    # Insert shapes had no text heuristic in 2.1.0. Keep them disabled by default.
    hints.extend(["", kind] for kind in sorted(TURNING_TOOL_TYPES - {kind for _, kind in hints}))
    return {"types": hints, "dimensions": dict(DEFAULT_DIMENSIONS)}


def default_settings():
    return default_profile()


def _validate_pattern(pattern, *, dimension=False):
    if not isinstance(pattern, str) or len(pattern) > 2048:
        raise ValueError("Patterns must be strings of at most 2048 characters")
    if _CYRILLIC.search(pattern):
        raise ValueError("Tool recognition patterns must not contain Cyrillic")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid pattern: {exc}") from exc
    if compiled.search("") is not None:
        raise ValueError("Patterns must not match empty text")
    if dimension and compiled.groups:
        raise ValueError("Dimension aliases must use non-capturing groups (?:...)")


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {"types", "dimensions"}:
        raise ValueError("A profile must contain types and dimensions")
    hints = profile["types"]
    if not isinstance(hints, list) or len(hints) != len(MILLING_TOOL_TYPES | TURNING_TOOL_TYPES):
        raise ValueError("Provide one type rule for every supported tool type")
    seen = set()
    for entry in hints:
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError("Each type rule must be [pattern, tool_type]")
        pattern, kind = entry
        if not isinstance(kind, str) or kind not in MILLING_TOOL_TYPES | TURNING_TOOL_TYPES or kind in seen:
            raise ValueError(f"Unknown or duplicate tool type: {kind}")
        seen.add(kind)
        if pattern != "":
            _validate_pattern(pattern)
    dimensions = profile["dimensions"]
    if not isinstance(dimensions, dict) or dimensions.keys() != DEFAULT_DIMENSIONS.keys():
        raise ValueError("Dimension keys must match the existing discovery parameters")
    for pattern in dimensions.values():
        _validate_pattern(pattern, dimension=True)
    compiled_hints(tuple(tuple(entry) for entry in hints))
    return deepcopy(profile)


def validate_settings(document):
    return validate_profile(document)


def load_settings(settings):
    stored = settings.value(SETTINGS_KEY, "")
    if not stored:
        return default_settings()
    try:
        document = json.loads(stored)
        if isinstance(document, dict) and isinstance(document.get("profiles"), dict):
            document = document["profiles"].get("Default", default_profile())
        _remove_legacy_cyrillic(document)
        result = validate_settings(document)
        if json.loads(stored) != result:
            settings.setValue(SETTINGS_KEY, json.dumps(result, ensure_ascii=False))
        return result
    except (TypeError, ValueError) as exc:
        logging.getLogger(__name__).warning("Invalid saved tool discovery rules: %s", exc)
        return default_settings()


def _remove_legacy_cyrillic(document):
    if not isinstance(document, dict) or not isinstance(document.get("types"), list):
        return
    defaults = {kind: pattern for pattern, kind in default_profile()["types"]}
    for entry in document["types"]:
        if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], str):
            continue
        pattern = re.sub(r"\|\\b[\u0400-\u052f]+\\b", "", entry[0])
        entry[0] = defaults.get(entry[1], "") if _CYRILLIC.search(pattern) else pattern
