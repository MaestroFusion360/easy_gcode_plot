"""Native FANUC CNC kernel public API.

Implementation lives in subject packages (``api``, ``frontend``, ``geometry``,
``runtime``, ``milling``). The historical flat module paths are registered as
in-process aliases below so existing ``app.gcode.kernel.<name>`` imports keep
resolving without compatibility files cluttering the package root.
"""

from __future__ import annotations

import sys

from . import geometry as _geometry
from .api import conversion as _api_conversion
from .api import execute
from .api import resources as _api_resources
from .api import types as _api_types
from .api.types import (
    Diagnostic,
    ExecutionEvent,
    ExecutionResult,
    ExecutionStep,
    MachineSignal,
    SemanticInstruction,
    TraceMotion,
)
from .compensation import milling as _compensation_milling
from .compensation import turning as _compensation_turning
from .frontend import ast as _ast
from .frontend import io as _io
from .frontend import lang as _lang
from .frontend import model as _model
from .frontend import program as _program
from .frontend.ast import (
    AstNode,
    AstWord,
    ControlAstNode,
    CycleAstNode,
    FlowAstNode,
    MetaAstNode,
    MotionAstNode,
    ProgramAst,
)
from .frontend.model import Motion, Point2, Program
from .geometry import arcs as _geometry_arcs
from .geometry import coordinates as _coordinates
from .runtime import diagnostics as _diagnostics
from .runtime import events as _events
from .runtime import execution as _execution
from .runtime import interpreter as _interpreter
from .runtime import signals as _signals
from .runtime import trace as _trace
from .runtime import trace_metadata as _trace_metadata
from .runtime.interpreter import types as _interpreter_types

__all__ = [
    "AstNode",
    "AstWord",
    "ControlAstNode",
    "CycleAstNode",
    "Diagnostic",
    "ExecutionEvent",
    "ExecutionResult",
    "ExecutionStep",
    "FlowAstNode",
    "MachineSignal",
    "MetaAstNode",
    "Motion",
    "MotionAstNode",
    "Point2",
    "Program",
    "ProgramAst",
    "SemanticInstruction",
    "TraceMotion",
    "execute",
]

# Historical flat module paths -> canonical implementation modules.
_COMPAT_MODULES = {
    "api_types": _api_types,
    "api_conversion": _api_conversion,
    "resources": _api_resources,
    "lang": _lang,
    "ast": _ast,
    "model": _model,
    "program": _program,
    "io": _io,
    "geometry": _geometry_arcs,
    "profile": _geometry,
    "coordinates": _coordinates,
    "execution": _execution,
    "events": _events,
    "signals": _signals,
    "diagnostics": _diagnostics,
    "trace": _trace,
    "trace_metadata": _trace_metadata,
    "interpreter": _interpreter,
    "interpreter_types": _interpreter_types,
    "milling_compensation": _compensation_milling,
    "tool_compensation": _compensation_turning,
}

for _name, _module in _COMPAT_MODULES.items():
    sys.modules.setdefault(f"{__name__}.{_name}", _module)
    setattr(sys.modules[__name__], _name, _module)
