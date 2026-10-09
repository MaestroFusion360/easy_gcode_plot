"""Target milling tool numbers, independent of source tool identities."""

import re

from ..kernel.runtime.events import TOOL_CHANGE
from ..post_profiles import _render
from .common import ExportLimitation


def named_tools(result):
    """Find names through the controller AST, including names resembling T codes."""
    if result.program is None:
        return set()
    return {
        node.native_syntax.named_tool
        for node in result.program.ast.nodes
        if node.native_syntax is not None and node.native_syntax.named_tool is not None
    }


def _is_tool_number(number):
    return isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= 99


def target_tool_numbers(result, profile, requested=None):
    """Keep numeric tools; allocate unused FANUC slots to named selections."""
    if result.language != "fanuc_mill" or not profile["id"].startswith("fanuc"):
        return {}
    names = named_tools(result)
    selected = list(dict.fromkeys(e.tool for e in result.events if e.kind == TOOL_CHANGE and e.tool))
    used = {int(tool[1:]) for tool in selected if tool not in names and re.fullmatch(r"T\d+", tool)}
    mapping = {}
    requested = requested or {}
    reserved = {number for name, number in requested.items() if name in names and _is_tool_number(number)}
    for name in selected:
        if name not in names:
            continue
        number = requested.get(name)
        if number is None:
            number = next((slot for slot in range(1, 100) if slot not in used | reserved), None)
        if not _is_tool_number(number) or number in used:
            raise ExportLimitation(
                "Named milling tools require distinct available FANUC numbers T1-T99",
                code="UNSUPPORTED_TOOL_MAPPING_EXPANDED_EXPORT",
            )
        used.add(number)
        mapping[name] = f"T{number}"
    return mapping


def tool_mapping_lines(mapping, profile):
    """Always disclose generated tool-table assignments in the output program."""
    return [
        _render(profile["comment"]["template"], text=f"{target} = {re.sub(r'[^\w .-]', '_', name)}")
        for name, target in mapping.items()
    ]


class MillingLengthOutput:
    """Ordinary tool-length selection on the non-TCP portions of a program."""

    def __init__(self, result, profile, mapping):
        self.enabled = result.language == "fanuc_mill"
        self.tcp_active = False
        self.native = result.source_dialect == "sinumerik"
        self.fanuc = profile["id"].startswith("fanuc")
        self.mapping = mapping
        self.tool = None

    def _update_state(self, step):
        """Follow the active tool and TCP mode in execution order."""
        changed = [event for event in step.events if event.kind == TOOL_CHANGE]
        if changed:
            self.tool = self.mapping.get(changed[-1].tool, changed[-1].tool)
        for event in step.events:
            if event.kind == "TCP_CONTROL_ON":
                self.tcp_active = True
            elif event.kind == "TCP_CONTROL_OFF":
                self.tcp_active = False
        return changed

    def lines(self, step):
        """Emit offset selections before the associated tip motion."""
        if not self.enabled:
            return []
        changed = self._update_state(step)
        if self.tcp_active:
            return []
        words = dict(step.words)
        if self.native:
            return self._native_lines(words.get("D", 1 if changed and self.tool else None))
        return self._fanuc_lines(step, words)

    def _native_lines(self, edge):
        """Translate a native cutting-edge selection to the target offset."""
        if edge is None:
            return []
        if not self.fanuc:
            return [f"D{int(edge)}"]
        if edge == 0:
            return ["G49"]
        return [f"G43 H{int(self.tool[1:])}"] if self.tool else []

    def _fanuc_lines(self, step, words):
        """Translate ordinary FANUC length activation and cancellation."""
        codes = [value for letter, value in step.words if letter == "G"]
        if 49 in codes:
            return ["G49" if self.fanuc else "D0"]
        if 43 in codes:
            if not self.fanuc:
                return ["D1"]
            offset = words.get("H")
            return ["G43" + (f" H{int(offset)}" if offset is not None else "")]
        return []
