"""Shared compensation contracts."""

from __future__ import annotations

EPS = 1e-9


class CompensationError(ValueError):
    """Base error for deterministic compensation failures."""


class ToolCompensationError(CompensationError):
    """Raised when an active turning compensation run cannot be constructed exactly."""
