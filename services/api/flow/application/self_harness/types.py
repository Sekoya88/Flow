"""Shared types + the non-regression accept rule for Self-Harness."""

from __future__ import annotations

from dataclasses import dataclass, field

# Declared editable harness surfaces. The first four are config-only and flow
# through apply_edit -> validate -> auto-promote. "skill" edits change a skill
# body (DB-backed, not agent_config) and are routed to the existing skill flow.
CONFIG_SURFACES: tuple[str, ...] = ("system_prompt", "loops", "tools", "temperature")
ALL_SURFACES: tuple[str, ...] = (*CONFIG_SURFACES, "skill")

_EPS = 1e-9


def accept(delta_in: float, delta_ho: float) -> bool:
    """Paper's promotion rule: improve at least one split, degrade neither.

        ∆in ≥ 0  ∧  ∆ho ≥ 0  ∧  max(∆in, ∆ho) > 0

    Deltas are candidate-minus-current pass rates (or pass counts) on the
    held-in and held-out splits respectively.
    """
    return delta_in >= -_EPS and delta_ho >= -_EPS and max(delta_in, delta_ho) > _EPS


@dataclass
class FailurePattern:
    """A cluster of failures sharing a verifier-grounded signature."""

    cause: str  # terminal verifier-level cause (e.g. "missing required artifact")
    mechanism: str  # reusable agent behavior (e.g. "unbounded tool exploration")
    support: int  # number of failed items in the cluster
    candidate_surface: str  # editable surface most likely to address it
    representative_inputs: list[str] = field(default_factory=list)
    actionability: float = 0.5  # 0..1 — how addressable by a narrow harness edit

    @property
    def signature(self) -> str:
        return f"{self.cause}||{self.mechanism}"

    @property
    def rank(self) -> float:
        """Clusters surfaced to the proposer first by support × actionability."""
        return self.support * self.actionability


@dataclass
class EvidenceBundle:
    """Ranked failure patterns mined from held-in failures. Describes mechanisms;
    does NOT prescribe edits (the proposer does that)."""

    patterns: list[FailurePattern] = field(default_factory=list)

    def ranked(self) -> list[FailurePattern]:
        return sorted(self.patterns, key=lambda p: p.rank, reverse=True)


@dataclass
class HarnessEdit:
    """A bounded, single-surface candidate modification to the harness."""

    surface: str  # one of ALL_SURFACES
    mutation_type: str  # MutationType value or "loops_tune"
    target: str  # "system_prompt" | "loops:max_tool_iters" | "tool:<name>" | "temperature" | "skill:<name>"
    payload: dict  # concrete change, e.g. {"value": 40} | {"system_prompt": "..."} | {"enabled": False}
    rationale: str = ""
    source_pattern: str = ""  # signature of the pattern this edit targets
