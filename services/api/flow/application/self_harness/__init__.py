"""Self-Harness — evidence-gated autonomous harness improvement.

Implements the loop from Zhang et al. (2026) on top of Flow's existing genome
machinery:

  1. Weakness Mining   (weakness_miner.py) — cluster failures into ranked patterns
  2. Harness Proposal  (proposer.py)       — K bounded edits across declared surfaces
  3. Proposal Validation (validator.py)    — held-in/held-out non-regression gate
  4. Orchestration     (orchestrator.py)   — mine -> propose -> validate -> merge -> promote

Shared types and the deterministic accept rule live in types.py; the pure
config-edit application lives in mutations.py.
"""
