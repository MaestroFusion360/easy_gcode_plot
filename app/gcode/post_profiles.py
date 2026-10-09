"""Load and validate controller post profiles independently of NC serialization.

Post templates contain data placeholders only. Validation neither interprets
a source program nor serializes resolved geometry.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from string import Formatter

WORD_SIGNS = frozenset({"auto", "always", "never"})


POST_TARGETS = (
    "fanuc_mill",
    "fanuc_mill_multiaxis",
    "fanuc_lathe_a",
    "fanuc_lathe_b",
    "sinumerik_iso",
    "sinumerik_840d",
    "sinumerik_840d_multiaxis",
)
MILLING_TARGETS = ("fanuc_mill", "sinumerik_iso", "sinumerik_840d")


def target_post_for_index(target: int, *, turning: bool) -> str | None:
    """Resolve the shared GUI target selector; zero selects the source controller."""
    return {
        1: "fanuc_lathe_a" if turning else "fanuc_mill",
        2: "fanuc_lathe_b" if turning else "sinumerik_iso",
        3: "sinumerik_840d",
        4: "fanuc_mill_multiaxis",
        5: "sinumerik_840d_multiaxis",
    }.get(target)


def export_file_suffix(source_path, *, target: str | None = None, dxf: bool = False) -> str:
    """Choose a post's extension, preserving MPF/SPF containers in Auto mode."""
    if dxf:
        return ".dxf"
    if target:
        return "." + load_post_profile(target)["extension"]
    suffix = Path(source_path).suffix.casefold() if source_path else ""
    return suffix if suffix in {".mpf", ".spf"} else ".nc"


def load_post_profile(target):
    """Load a bundled controller or a user-supplied JSON post profile."""
    path = Path(__file__).parent / "export" / "posts" / f"{target}.json" if target in POST_TARGETS else Path(target)
    try:
        with path.open(encoding="utf-8-sig") as stream:
            profile = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load post profile {target}: {error}") from error
    if not isinstance(profile, dict) or profile.get("machine") not in {"mill", "lathe"}:
        raise ValueError("Post profile must specify mill or lathe")
    required = {
        "options": (
            "incrementalMode",
            "delimiter",
            "leadingZero",
            "decimalPlaces",
            "forceDecimal",
            "plusOutput",
            "units",
        ),
        "format": ("outputArcs", "arcMode", "arcCenter", "absoluteCenterSyntax", "radiusAddress", "multiTurnArcs"),
        "motion": (
            "rapidMove",
            "linearMove",
            "circularMoveCW",
            "circularMoveCCW",
            "planeXY",
            "planeXZ",
            "planeYZ",
            "threadMove",
        ),
        "positioning": ("absolute", "incremental", "incrementalAxes"),
        "home": ("G28", "G53"),
        "tool": ("toolChange",),
        "spindle": ("cw", "ccw", "stop", "cssOn", "cssOff", "maxSpeed"),
        "coolant": ("mist", "flood", "off"),
        "feed": ("perMinute", "perRev", "inverseTime"),
        "units": ("inch", "metric"),
        "dwell": ("command", "address", "scale"),
        "program": ("start", "preamble", "stop", "optionalStop", "end"),
    }
    for section, keys in required.items():
        if not isinstance(profile.get(section), dict) or any(key not in profile[section] for key in keys):
            raise ValueError(f"Missing post profile fields in {section}")
    if not _valid_decimal_places(profile["options"]["decimalPlaces"]):
        raise ValueError("Post decimalPlaces must be an integer from 0 to 12")
    if profile["format"]["arcMode"] not in {"IJK", "R"} or profile["format"]["arcCenter"] not in {
        "absolute",
        "incremental",
    }:
        raise ValueError("Unsupported post arc format")
    if profile["options"]["units"] not in {"mm", "inch"}:
        raise ValueError("Post units must be mm or inch")
    _validate_post_commands(profile)
    return profile


def _validate_post_safety(program) -> None:
    safety = program.get("safety")
    if safety is None:
        return
    if not isinstance(safety, list) or any(not isinstance(line, str) for line in safety):
        raise ValueError("Post program.safety must be a list of command strings")
    for line in safety:
        _render(line, programName="", units="")


def _validate_post_commands(profile):
    if not isinstance(profile.get("extension"), str) or not re.fullmatch(r"[a-zA-Z0-9]+", profile["extension"]):
        raise ValueError("Post extension must be a plain file suffix")
    _validate_post_options(profile["options"])
    if not isinstance(profile["program"]["preamble"], list):
        raise ValueError("Post program.preamble must be a list of command strings")
    _validate_post_safety(profile["program"])
    fields = {
        "motion": {"coord": "", "feed": ""},
        "tool": {"tool": "", "code": ""},
        "spindle": {"speed": "", "value": ""},
        "dwell": {"dwell": ""},
        "program": {"programName": "", "units": ""},
        "feed": {},
        "coolant": {},
        "units": {},
    }
    for section, values in fields.items():
        commands = [
            command
            for key, command in profile[section].items()
            if key not in {"scale", "address", "preamble", "safety"}
        ]
        if section == "program":
            commands.extend(profile[section]["preamble"])
        for command in commands:
            _render(command, **values)
    comment = profile.get("comment")
    if comment is not None:
        if not isinstance(comment, dict) or not isinstance(comment.get("template"), str):
            raise ValueError("Post comment.template must be a string")
        _render(comment["template"], text="")
    _validate_post_geometry(profile)
    _validate_post_extras(profile)


def _validate_post_extras(profile):
    _validate_cycles(profile.get("cycles"))
    _validate_cycle_profiles(profile.get("cycleProfiles"))
    _validate_post_arc_extras(profile["format"])
    _validate_supports(profile.get("supports"))
    _validate_multiaxis(profile)
    _validate_format_words(profile["format"].get("words"), profile.get("supports"))


def _validate_cycle_profiles(profiles):
    if profiles is None:
        return
    if not isinstance(profiles, dict) or set(profiles) != {"classic_0108", "sl_0309"}:
        raise ValueError("Post cycleProfiles requires classic_0108 and sl_0309")
    for config in profiles.values():
        _validate_cycles(config)
        if config is None or config["syntax"] != "native":
            raise ValueError("SINUMERIK cycleProfiles must use native syntax")


def select_cycle_profile(profile, solution_line):
    """Choose a declared target interface without changing the loaded JSON."""
    profiles = profile.get("cycleProfiles")
    if profiles is None or not profile.get("cycles"):
        return profile
    return dict(profile, cycles=profiles["sl_0309" if solution_line else "classic_0108"])


def _validate_cycles(config):
    if config is None:
        return
    kinds = {"drill", "drillDwell", "peckDrill", "highSpeedPeck", "tap", "boreFeed", "boreStop"}
    controls = {"cancel", "rigidTap", "returnInitial", "returnSafety"}
    if not isinstance(config, dict) or config.get("syntax") not in {"iso", "native"}:
        raise ValueError("Post cycles requires iso or native syntax")
    if any(key not in kinds | controls | {"syntax"} for key in config):
        raise ValueError("Unknown post cycles field")
    required = {"cancel"} | ({"returnInitial", "returnSafety"} if config["syntax"] == "iso" else set())
    if any(not isinstance(config.get(key), str) or not config[key].strip() for key in required):
        raise ValueError("Post cycles requires cancel and ISO return commands")
    fields = {
        "x",
        "y",
        "clearance",
        "referenceHeight",
        "secondClearance",
        "depth",
        "retractHeight",
        "peckFirst",
        "peckReduction",
        "peckMinimum",
        "firstDepth",
        "dwellBottom",
        "dwellTop",
        "reentryClearance",
        "retractDistance",
        "firstFeedFactor",
        "fullRetract",
        "spindleSpeedTap",
        "spindleSpeedReturn",
        "feed",
        "threadPitch",
        "dwellWord",
    }
    for key, template in config.items():
        if key != "syntax":
            if not isinstance(template, str) or not template.strip():
                raise ValueError("Post cycle templates must be nonempty strings")
            _render(
                template, **dict.fromkeys(fields if key not in {"cancel", "returnInitial", "returnSafety"} else (), "0")
            )


def _validate_post_arc_extras(arc):
    if "turnsWord" in arc:
        _render(str(arc["turnsWord"]), turns=0)
    for key in ("radiusSplitAngle", "arcSplitAngle"):
        if key in arc and (not isinstance(arc[key], (int, float)) or not math.isfinite(arc[key]) or arc[key] <= 0):
            raise ValueError(f"Post format.{key} must be a positive finite angle")
    if "fullCircle" in arc and arc["fullCircle"] != "two_half":
        raise ValueError("Post format.fullCircle must be two_half")


_FORMAT_WORD_TOKENS = {
    "motion": "motion",
    "X": "x",
    "Y": "y",
    "Z": "z",
    "A": "a",
    "B": "b",
    "C": "c",
    "I": "i",
    "J": "j",
    "K": "k",
    "R": "r",
}
_AXIS_WORD_KEYS = frozenset({"X", "Y", "Z", "A", "B", "C"})


def _valid_decimal_places(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 12


def _validate_format_word_format(spec):
    if "decimals" in spec and not _valid_decimal_places(spec["decimals"]):
        raise ValueError("Post format.words decimals must be an integer from 0 to 12")
    if "sign" in spec and spec["sign"] not in WORD_SIGNS:
        raise ValueError("Post format.words sign must be auto, always or never")


def _validate_format_word_entry(key, spec, axes, orders):
    if key not in _FORMAT_WORD_TOKENS:
        raise ValueError(f"Post format.words has unsupported token: {key}")
    if not isinstance(spec, dict) or any(name not in {"order", "required", "decimals", "sign"} for name in spec):
        raise ValueError("Post format.words entries accept order, required, decimals and sign")
    order = spec.get("order")
    if not isinstance(order, int) or isinstance(order, bool):
        raise ValueError("Post format.words order must be an integer")
    if order in orders:
        raise ValueError("Post format.words order values must be unique")
    orders.add(order)
    if not isinstance(spec.get("required"), bool):
        raise ValueError("Post format.words required must be a boolean")
    _validate_format_word_format(spec)
    if key in _AXIS_WORD_KEYS and key not in axes:
        raise ValueError(f"Post format.words axis {key} requires it in supports.axes")


def _validate_format_words(words, supports):
    if words is None:
        return
    if not isinstance(words, dict) or not words:
        raise ValueError("Post format.words must be a non-empty object")
    if "motion" not in words:
        raise ValueError("Post format.words must define motion")
    axes = set((supports or {}).get("axes", ["X", "Y", "Z"]))
    orders: set[int] = set()
    for key, spec in words.items():
        _validate_format_word_entry(key, spec, axes, orders)


def _validate_supports(supports):
    if supports is None:
        return
    if not isinstance(supports, dict):
        raise ValueError("Post supports must be an object")
    axes = supports.get("axes", ["X", "Y", "Z"])
    if not isinstance(axes, list) or not axes or any(axis not in {"X", "Y", "Z", "A", "B", "C"} for axis in axes):
        raise ValueError("Post supports.axes must be a non-empty list of X/Y/Z/A/B/C")
    for key in ("inverseTime", "multiTurnArcs", "absoluteArcCenters", "tcp"):
        if key in supports and not isinstance(supports[key], bool):
            raise ValueError(f"Post supports.{key} must be boolean")


def _validate_multiaxis(profile):
    _validate_reference_post(profile)
    config = profile.get("multiaxis")
    supports_tcp = bool((profile.get("supports") or {}).get("tcp"))
    if config is None:
        if supports_tcp:
            raise ValueError("Post supports.tcp requires a multiaxis section")
        return
    if not isinstance(config, dict) or any(key not in {"tcpOn", "tcpOff"} for key in config):
        raise ValueError("Post multiaxis accepts tcpOn and tcpOff")
    if supports_tcp and any(
        not isinstance(config.get(key), str) or not config[key].strip() for key in ("tcpOn", "tcpOff")
    ):
        raise ValueError("TCP-capable post requires non-empty multiaxis.tcpOn/tcpOff")
    for key in ("tcpOn", "tcpOff"):
        if key in config:
            _render(config[key])


def _validate_post_options(defaults):
    for key in ("incrementalMode", "delimiter", "leadingZero", "forceDecimal", "plusOutput"):
        if not isinstance(defaults[key], bool):
            raise ValueError(f"Post options.{key} must be boolean")


def _validate_post_geometry(profile):
    arc = profile["format"]
    if arc["absoluteCenterSyntax"] not in {"AC", "words"} or arc["radiusAddress"] not in {"R", "CR="}:
        raise ValueError("Unsupported post center/radius syntax")
    if not all(isinstance(arc[key], bool) for key in ("outputArcs", "multiTurnArcs")):
        raise ValueError("Post arc output flags must be boolean")
    scale = profile["dwell"]["scale"]
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("Post dwell scale must be positive and finite")
    if profile["dwell"]["address"] not in {"P", "F", "X"}:
        raise ValueError("Unsupported post dwell address")
    positioning = profile["positioning"]
    _render(positioning["absolute"])
    _render(positioning["incremental"])
    _validate_axis_commands(positioning["incrementalAxes"])
    for commands in profile["home"].values():
        _validate_axis_commands(commands, home=True)


def _validate_axis_commands(commands, *, home=False):
    allowed = {"X", "Y", "Z", "all"} if home else {"X", "Y", "Z"}
    if not isinstance(commands, dict) or any(axis not in allowed for axis in commands):
        raise ValueError("Post axis commands must map X/Y/Z or a combined home template")
    for axis, command in commands.items():
        _render(command, **({"axes": "Z0"} if axis == "all" else {}))


def _render(template, **values):
    """Data-only templates: no expressions, attribute access or clock values."""
    try:
        for _, field, spec, conversion in Formatter().parse(template):
            if field is not None and (field not in values or spec or conversion):
                raise ValueError(f"Unsupported post placeholder: {field}")
        return template.format(**values).strip()
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"Invalid post template: {template}") from error


def _validate_reference_post(profile):
    config = profile.get("reference")
    if config is None:
        return
    if not isinstance(config, dict) or any(key not in {"rapid", "linear"} for key in config):
        raise ValueError("Post reference accepts rapid and linear templates")
    for key, template in config.items():
        if not isinstance(template, str) or not template.strip():
            raise ValueError("Post reference templates must be nonempty strings")
        try:
            if any(
                field is not None and (field not in {"axes", "feed"} or spec or conversion)
                for _, field, spec, conversion in Formatter().parse(template)
            ):
                raise ValueError("Unsupported reference placeholder")
            template.format(axes="Z0", feed="F100")
        except (KeyError, ValueError, AttributeError) as exc:
            raise ValueError("Post reference templates accept axes and feed only") from exc
        if "{axes}" not in template:
            raise ValueError("Post reference templates must contain {axes}")
        if key == "linear" and "{feed}" not in template:
            raise ValueError("Post linear reference must contain {feed}")
