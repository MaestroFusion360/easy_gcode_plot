"""Per-execution resource limits shared by flow and cycle expansion."""

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field


class SemanticError(ValueError):
    def __init__(self, code: str, message: str, status: str = "malformed"):
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class ExecutionLimits:
    executed_blocks: int = 500_000
    subprogram_calls: int = 10_000
    generated_motions: int = 200_000
    cycle_iterations: int = 100_000
    macro_iterations: int = 100_000
    call_depth: int = 64

    def __post_init__(self):
        if any(not isinstance(v, int) or v <= 0 for v in self.__dict__.values()):
            raise ValueError("Execution limits must be positive integers")


@dataclass
class ExecutionBudget:
    limits: ExecutionLimits = field(default_factory=ExecutionLimits)
    cancelled: Callable[[], bool] | None = None
    counts: dict[str, int] = field(default_factory=dict)

    def check(self, kind: str | None = None, amount: int = 1):
        if self.cancelled is not None and self.cancelled():
            raise SemanticError("EXECUTION_CANCELLED", "Execution cancelled", "resource_limit")
        if kind is not None:
            count = self.counts.get(kind, 0) + amount
            if count > getattr(self.limits, kind):
                raise SemanticError("RESOURCE_LIMIT", f"Execution budget exceeded: {kind}", "resource_limit")
            self.counts[kind] = count


active_budget: ContextVar[ExecutionBudget | None] = ContextVar("cnc_execution_budget", default=None)


def checkpoint(kind: str | None = None, amount: int = 1):
    budget = active_budget.get()
    if budget is not None:
        budget.check(kind, amount)


def require_progress(before: float, after: float):
    if before == after:
        raise SemanticError("NUMERICAL_PROGRESS", "Cycle step cannot advance at this coordinate", "invalid_geometry")
