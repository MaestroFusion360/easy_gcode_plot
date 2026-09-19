"""Canonical tool types, applicability and safe default geometries."""

TURNING_TOOL_LABELS = {
    "diamond_80": "Diamond 80",
    "diamond_35": "Diamond 35",
    "square": "Square",
    "round": "Round",
    "triangle": "Triangle",
    "groove": "Groove",
    "thread": "Thread",
    "drill": "Drill",
    "tap": "Tap",
}
TURNING_TOOL_TYPES = frozenset(TURNING_TOOL_LABELS)
TURNING_INSERT_TYPES = frozenset({"diamond_80", "diamond_35", "square", "round", "triangle"})
TURNING_APPLICATIONS = ("od", "id", "face")

DEFAULT_TURNING_TOOL = {
    "type": "diamond_80",
    "applications": ["od"],
    "noseRadius": 0.4,
    "tipOrientation": 3,
    "insertLength": 12.0,
}
DEFAULT_MILLING_TOOL = {"type": "mill_flat", "diameter": 10.0, "cornerRadius": 0.0, "length": 50.0}

MILLING_TOOL_LABELS = {
    "mill_flat": "Flat Mill",
    "mill_bull": "Bull Mill",
    "mill_ball": "Ball Mill",
    "face_mill": "Face Mill",
    "slot_mill": "Slot Mill",
    "chamfer_mill": "Chamfer Mill",
    "drill": "Drill",
    "tap": "Tap",
}
MILLING_TOOL_TYPES = frozenset(MILLING_TOOL_LABELS)

AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION = {
    "diamond_80": {"od": (3, 4), "id": (1, 2)},
    "diamond_35": {"od": (3, 4, 7, 8), "id": (1, 2, 6, 7)},
    "square": {"od": (3,), "id": (2,)},
    "round": {"od": (8,), "id": (7,)},
    "triangle": {"od": (3,), "id": (2,)},
    "groove": {"od": (3, 4), "id": (1, 2), "face": (2, 3)},
    "thread": {"od": (8,), "id": (6,)},
}
AUTO_TIP_ORIENTATIONS = {
    tool_type: tuple(sorted({value for values in by_direction.values() for value in values}))
    for tool_type, by_direction in AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.items()
}
DEFAULT_AUTO_TIP_ORIENTATION = {
    "diamond_80": 3,
    "diamond_35": 3,
    "square": 3,
    "round": 8,
    "triangle": 3,
    "groove": 3,
    "thread": 8,
}
DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION = {
    tool_type: {application: orientations[0] for application, orientations in by_direction.items()}
    for tool_type, by_direction in AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.items()
}
# Preserve the established right-hand defaults when a family offers two edges.
DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION["diamond_80"].update(od=3, id=2)
DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION["diamond_35"].update(od=3, id=2)
DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION["groove"].update(od=3, id=2, face=3)


def normalized_applications(value: object) -> tuple[str, ...]:
    """Return stable, unique OD/ID/Face values from persisted data."""
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = value
    else:
        values = ()
    selected = {str(item).strip().lower() for item in values}
    return tuple(item for item in TURNING_APPLICATIONS if item in selected)


def applications_for_orientation(tool_type: str, orientation: int) -> tuple[str, ...]:
    """Infer applicability for records created before flags were persisted."""
    by_direction = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(tool_type, {})
    matches = tuple(
        application for application in TURNING_APPLICATIONS if orientation in by_direction.get(application, ())
    )
    return matches or (("od",) if by_direction else ())


def tool_applications(spec: dict[str, object]) -> tuple[str, ...]:
    """Read canonical applicability, with an orientation fallback."""
    applications = normalized_applications(spec.get("applications"))
    if applications:
        return applications
    try:
        orientation = int(spec.get("tipOrientation", 0))
    except (TypeError, ValueError):
        orientation = 0
    return applications_for_orientation(str(spec.get("type", "")), orientation)


def tool_application(spec: dict[str, object], preferred: str | None = None) -> str:
    """Resolve one application context for geometry or stock behavior."""
    applications = tool_applications(spec)
    if preferred in applications:
        return str(preferred)
    try:
        orientation = int(spec.get("tipOrientation", 0))
    except (TypeError, ValueError):
        orientation = 0
    by_direction = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(str(spec.get("type", "")), {})
    oriented = tuple(item for item in applications if orientation in by_direction.get(item, ()))
    return (oriented or applications or (preferred or "od",))[0]


_TURNING_TOOL_GROUPS = (
    (1, "diamond_80", ("od",)),
    (2, "diamond_35", ("od",)),
    (3, "diamond_80", ("id",)),
    (4, "diamond_35", ("id",)),
    (5, "square", ("od", "id")),
    (6, "round", ("od", "id")),
    (7, "triangle", ("od", "id")),
    (8, "groove", ("face",)),
    (9, "groove", ("od",)),
    (10, "groove", ("id",)),
    (11, "thread", ("od", "id")),
)


def _turning_spec(tool_type: str, application: str, orientation: int) -> dict:
    common = {
        "type": tool_type,
        "applications": [application],
        "tipOrientation": orientation,
        "description": f"{TURNING_TOOL_LABELS[tool_type]} {application.upper()} P{orientation}",
    }
    if tool_type == "groove":
        return {**common, "width": 3.0, "noseRadius": 0.0}
    if tool_type == "thread":
        return {
            **common,
            "insertLength": 12.0,
            "threadAngle": 60.0,
            "threadTipWidth": 0.8,
            "threadCornerRadius": 0.1,
        }
    return {
        **common,
        "noseRadius": 0.4,
        "insertLength": 16.0 if tool_type == "diamond_35" else 12.0,
    }


def default_turning_library() -> dict[str, dict]:
    """Return every turning tool and tracing point supported by auto mode."""
    tools = {}
    for group, tool_type, applications in _TURNING_TOOL_GROUPS:
        for application in applications:
            orientations = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION[tool_type][application]
            for orientation in orientations:
                tools[f"T{group:02d}{orientation:02d}"] = _turning_spec(tool_type, application, orientation)
    tools["T1201"] = {
        "type": "drill",
        "diameter": 10.0,
        "length": 50.0,
        "tipAngle": 118.0,
        "description": "Drill",
    }
    tools["T1301"] = {
        "type": "tap",
        "diameter": 10.0,
        "length": 50.0,
        "tipAngle": 60.0,
        "description": "Tap",
    }
    return tools
