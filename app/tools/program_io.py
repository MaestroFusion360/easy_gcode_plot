"""Lossless JSON exchange of program-local tool assignments, independent of SQLite."""

import json
import math
from copy import deepcopy
from pathlib import Path

from app.gcode.file_io import atomic_write_text
from app.tools.validation import normalized_program_milling_tools, normalized_tools


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _validate_dimensions(key, spec, normalized):
    for field, value in normalized.items():
        if field not in spec or not isinstance(value, (int, float)):
            continue
        raw = spec[field]
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or not math.isfinite(raw):
            raise ValueError(f"Invalid {field}: {key}")
        if field == "cornerRadius" and not 0 <= raw <= spec.get("diameter", 0) / 2:
            raise ValueError(f"Invalid {field}: {key}")
        if field != "cornerRadius" and raw != value:
            raise ValueError(f"Invalid {field}: {key}")


def _validated_tools(kind, tools):
    if kind not in {"milling", "turning"} or not isinstance(tools, dict):
        raise ValueError("Expected milling or turning program tools")
    normalize = normalized_tools if kind == "turning" else normalized_program_milling_tools
    result = {}
    for key, spec in tools.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(spec, dict) or "type" not in spec:
            raise ValueError(f"Invalid tool record: {key}")
        validated = normalize({key: spec})
        if len(validated) != 1:
            raise ValueError(f"Invalid tool geometry: {key}")
        canonical = next(iter(validated))
        _validate_dimensions(key, spec, validated[canonical])
        if kind == "milling" and key.upper().startswith("T") and key[1:].isdigit():
            canonical = f"T{int(key[1:])}"
        if canonical in result:
            raise ValueError(f"Duplicate tool number: {canonical}")
        result[canonical] = deepcopy(spec)
    return result


def read_program_tools(path, kind):
    """Validate the entire file before allowing any program assignment to change."""
    payload = json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        object_pairs_hook=_unique_fields,
        parse_constant=_invalid_constant,
    )
    json.dumps(payload, allow_nan=False)
    if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("kind") != kind:
        raise ValueError(f"Expected version 1 {kind} program tools")
    return _validated_tools(kind, payload.get("tools"))


def write_program_tools(path, kind, tools):
    """Write a deterministic snapshot, retaining all geometry, offsets and metadata."""
    if Path(path).suffix.lower() != ".json":
        raise ValueError("Program tools must be exported to a .json file")
    _validated_tools(kind, tools)
    payload = {"version": 1, "kind": kind, "tools": tools}
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    atomic_write_text(path, text)
