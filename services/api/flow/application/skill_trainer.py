"""SkillOpt ReflACT — 6-stage skill training orchestrator.

Treats skill documents as trainable state via bounded structured text edits,
without touching model weights. Implements the ReflACT optimization pipeline
from Microsoft's SkillOpt paper.

Pipeline stages:
  1. Rollout   — run agent on golden items, identify failures
  2. Reflect   — LLM analyzes failures, proposes targeted patches
  3. Aggregate — deduplicate patches (keep highest impact per target)
  4. Select    — cap to edit_budget patches (the "learning rate")
  5. Update    — apply patches to skill body
  6. Evaluate  — score candidate skill, accept if improvement > threshold
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg
from openai import AsyncOpenAI

from flow.application.golden_evaluator import evaluate_golden_set, judge_single, run_agent_on_item
from flow.application.skill_rewriter import _bump_version_in_frontmatter, _split_frontmatter

from flow.infrastructure.observability.logging import get_logger
log = get_logger("flow.training")


async def _emit(
    pool: asyncpg.Pool,
    run_id: UUID,
    stage: str,
    kind: str,
    message: str,
    data: dict | None = None,
) -> None:
    """Insert a training event row; swallows errors so training is never blocked."""
    try:
        await pool.execute(
            """INSERT INTO skill_training_events (run_id, stage, kind, message, data)
               VALUES ($1, $2, $3, $4, $5)""",
            run_id,
            stage,
            kind,
            message,
            data,  # pool codec handles jsonb serialization; don't double-encode
        )
    except Exception as exc:
        log.warning("training.emit_failed", error=str(exc))


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class RawPatch:
    op: str            # "append" | "insert" | "replace" | "delete"
    target: str        # section heading anchor (e.g., "## Output Format")
    content: str       # replacement/new text (max ~125 chars)
    impact_score: float  # 0.0-1.0


@dataclass
class TrainingConfig:
    edit_budget: int = 5          # max edits per epoch (the "learning rate")
    max_epochs: int = 3
    min_val_improvement: float = 0.02
    mini_batch_size: int = 10
    slow_update_ema: float = 0.1  # for EMA-blended protected sections (Phase 3 stub)


# ── System prompt ─────────────────────────────────────────────────────────────

_REFLECT_SYSTEM = """\
You are an expert AI skill engineer. A "skill" is a SKILL.md file used as a system prompt for an AI agent.

Your task: Analyze failures and propose TARGETED EDITS (patches) to fix them.

## Rules
1. Output patches ONLY — never rewrite the whole document.
2. Each patch targets a specific section heading (e.g., "## Output Format").
3. Surgical changes only — fix the root cause, don't restructure.
4. Max 125 characters per content field.
5. Use op="append" to add text at end of a section, "replace" to change existing content,
   "insert" to add before a section, "delete" to remove content.

## Output Format
Return ONLY valid JSON:
{
  "failure_analysis": "Root cause in 2-3 sentences",
  "patches": [
    {"op": "replace", "target": "## Instructions", "content": "...", "impact_score": 0.85},
    {"op": "append", "target": "## Output Format", "content": "...", "impact_score": 0.6}
  ]
}
"""


# ── Main class ────────────────────────────────────────────────────────────────


class SkillTrainer:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Stage 1: Rollout ──────────────────────────────────────────────────────

    async def _stage_rollout(
        self,
        skill_content_md: str,
        items: list[dict],
        *,
        langsmith_extra: dict | None = None,
    ) -> list[dict]:
        """Run agent on golden items; return scored results.

        Returns list of dicts with keys:
          input_text, expected_output, actual_output, score, rationale
        """
        results = []
        for item in items:
            actual = await run_agent_on_item(
                input_text=item["input_text"],
                system_prompt=skill_content_md,
                llm_config={"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3},
                langsmith_extra=langsmith_extra,
            )
            judgment = await judge_single(
                input_text=item["input_text"],
                expected_output=item["expected_output"],
                actual_output=actual,
                scoring_criteria=item.get("scoring_criteria"),
            )
            results.append(
                {
                    "input_text": item["input_text"],
                    "expected_output": item["expected_output"],
                    "actual_output": actual,
                    "score": judgment["score"],
                    "rationale": judgment["rationale"],
                }
            )
        return results

    # ── Stage 2: Reflect ──────────────────────────────────────────────────────

    async def _stage_reflect(
        self,
        body: str,
        failures: list[dict],
        rejected_patches: list[dict],
        *,
        client: AsyncOpenAI | None = None,
    ) -> tuple[list[RawPatch], str]:
        """Analyze failures and propose targeted patches via LLM.

        Returns (patches, failure_analysis) tuple; patches=[] on JSON parse failure.
        """
        if client is None:
            api_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            client = AsyncOpenAI(api_key=api_key)

        failures_text = "\n\n".join(
            f"--- FAILURE {i + 1} (score: {f['score']:.2f}) ---\n"
            f"Input: {f['input_text'][:500]}\n"
            f"Expected: {f['expected_output'][:500]}\n"
            f"Actual: {f['actual_output'][:500]}\n"
            f"Rationale: {f['rationale']}"
            for i, f in enumerate(failures)
        )

        user_content = f"""\
## Current Skill Body
{body or "(empty body)"}

## Failures to Fix
{failures_text}
"""

        if rejected_patches:
            rejected_lines = "\n".join(
                f'- op: {r["op"]}, target: "{r["target"]}"' for r in rejected_patches
            )
            user_content += f"""
## Previously rejected edits — do NOT re-propose these:
{rejected_lines}
"""

        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _REFLECT_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            raw = resp.choices[0].message.content or "{}"

            json_str = raw.strip()
            if json_str.startswith("```"):
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str

            data = json.loads(json_str)
            analysis: str = data.get("failure_analysis", "")
            patches = []
            for p in data.get("patches", []):
                try:
                    patches.append(
                        RawPatch(
                            op=str(p["op"]),
                            target=str(p["target"]),
                            content=str(p.get("content", "")),
                            impact_score=float(p.get("impact_score", 0.5)),
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    log.warning("training.patch.malformed", error=str(exc))
            return patches, analysis

        except json.JSONDecodeError as exc:
            log.warning("training.reflect.json_parse_failed", error=str(exc))
            return [], ""
        except Exception as exc:
            log.error("training.reflect.failed", error=str(exc))
            return [], ""

    # ── Stage 3: Aggregate ────────────────────────────────────────────────────

    def _stage_aggregate(self, patches: list[RawPatch]) -> list[RawPatch]:
        """Deduplicate patches — keep highest impact_score per target heading."""
        best: dict[str, RawPatch] = {}
        for patch in patches:
            key = patch.target
            if key not in best or patch.impact_score > best[key].impact_score:
                best[key] = patch
        return list(best.values())

    # ── Stage 4: Select ───────────────────────────────────────────────────────

    def _stage_select(self, patches: list[RawPatch], budget: int) -> list[RawPatch]:
        """Sort by impact_score descending; return top `budget` patches."""
        sorted_patches = sorted(patches, key=lambda p: p.impact_score, reverse=True)
        return sorted_patches[:budget]

    # ── Stage 5: Update ───────────────────────────────────────────────────────

    def _stage_update(self, body: str, patches: list[RawPatch]) -> str:
        """Apply patches to skill body string. Returns modified body."""
        current = body
        for patch in patches:
            current = self._apply_patch(current, patch)
        return current

    def _apply_patch(self, body: str, patch: RawPatch) -> str:
        """Apply a single patch to the body. Returns modified body."""
        target = patch.target
        op = patch.op
        content = patch.content

        # Skip protected sections (Phase 3 EMA placeholder)
        slow_pattern = re.compile(
            r"<!-- SLOW_UPDATE_START -->.*?<!-- SLOW_UPDATE_END -->",
            re.DOTALL,
        )
        for match in slow_pattern.finditer(body):
            protected_block = match.group(0)
            if target in protected_block:
                log.debug("training.patch.protected_section_skipped", target=target)
                return body

        # Find the target heading line
        heading_pattern = re.compile(r"^" + re.escape(target) + r"\s*$", re.MULTILINE)
        heading_match = heading_pattern.search(body)

        if heading_match is None:
            # Heading not found
            if op in ("append", "replace"):
                # Append a new section at end of body
                separator = "\n\n" if not body.endswith("\n\n") else ""
                return body.rstrip("\n") + "\n\n" + target + "\n" + content + "\n"
            elif op == "insert":
                # Insert at beginning of body
                return content + "\n\n" + body
            elif op == "delete":
                # Nothing to delete
                return body
            return body

        heading_start = heading_match.start()
        heading_end = heading_match.end()

        # Find where the section content ends (next ## heading or end of string)
        after_heading = body[heading_end:]
        next_heading_match = re.search(r"^##", after_heading, re.MULTILINE)
        if next_heading_match:
            section_content_end = heading_end + next_heading_match.start()
        else:
            section_content_end = len(body)

        if op == "replace":
            # Replace heading + section content with heading + new content
            new_section = target + "\n" + content + "\n"
            return body[:heading_start] + new_section + body[section_content_end:].lstrip("\n")

        elif op == "append":
            # Insert content before the next heading (end of section)
            insert_pos = section_content_end
            # Strip trailing newlines from section, add content, then newlines
            section_body = body[heading_end:section_content_end].rstrip("\n")
            new_section_body = section_body + "\n" + content + "\n"
            return body[:heading_end] + new_section_body + "\n" + body[section_content_end:].lstrip("\n")

        elif op == "insert":
            # Insert content as a new line before the heading
            return body[:heading_start] + content + "\n\n" + body[heading_start:]

        elif op == "delete":
            # Remove heading + section content
            deleted = body[:heading_start].rstrip("\n")
            remainder = body[section_content_end:].lstrip("\n")
            if deleted and remainder:
                return deleted + "\n\n" + remainder
            return (deleted or remainder).strip("\n") + "\n"

        return body

    # ── Stage 6: Evaluate (called via evaluate_golden_set) ────────────────────
    # Evaluation is driven by run_training_epoch; no separate method needed.

    # ── Orchestrator ─────────────────────────────────────────────────────────

    async def run_training_epoch(
        self,
        run_id: UUID,
        skill_id: UUID,
        agent_id: UUID,
        workspace_id: UUID,
        config: TrainingConfig,
        *,
        golden_set_id: UUID | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> dict:
        """One full ReflACT epoch: Rollout→Reflect→Aggregate→Select→Update→Evaluate.

        Returns dict with keys: accepted (bool), eval_score (float),
        baseline_score (float), candidate_skill_id (UUID|None),
        patches_applied (int), patches_rejected (int).
        """
        _pool = pool or self._pool

        # 1. Fetch current skill from DB
        skill_row = await _pool.fetchrow(
            "SELECT id, content_md, name FROM agent_skills WHERE id = $1",
            skill_id,
        )
        if skill_row is None:
            log.warning("training.skill_not_found", skill_id=str(skill_id))
            return {
                "accepted": False,
                "eval_score": 0.0,
                "baseline_score": 0.0,
                "candidate_skill_id": None,
                "patches_applied": 0,
                "patches_rejected": 0,
            }

        frontmatter, body = _split_frontmatter(skill_row["content_md"])

        # 2. Get baseline score (last golden eval for this skill, or 0.0 if none)
        baseline_row = await _pool.fetchrow(
            """
            SELECT AVG(score) AS avg
            FROM (SELECT score FROM golden_results WHERE agent_id = $1
                  ORDER BY created_at DESC LIMIT 50) recent
            """,
            agent_id,
        )
        baseline_score = float(baseline_row["avg"] or 0.0) if baseline_row else 0.0

        # 3. Get golden set — linked to skill or fallback to workspace's first set
        effective_golden_set_id = golden_set_id
        if effective_golden_set_id is None:
            gs_row = await _pool.fetchrow(
                "SELECT id FROM golden_sets WHERE workspace_id = $1 ORDER BY created_at LIMIT 1",
                workspace_id,
            )
            effective_golden_set_id = gs_row["id"] if gs_row else None

        if effective_golden_set_id is None:
            await _emit(_pool, run_id, "epoch", "error", "No golden set found — add golden examples first.")
            return {
                "accepted": False,
                "eval_score": 0.0,
                "baseline_score": baseline_score,
                "candidate_skill_id": None,
                "patches_applied": 0,
                "patches_rejected": 0,
            }

        await _emit(_pool, run_id, "epoch", "stage_start",
            f"Epoch starting — baseline score: {baseline_score:.3f}",
            {"baseline_score": baseline_score, "skill_name": skill_row["name"]})

        # 4. Get rejected patches (cross-epoch buffer)
        rejected = await _pool.fetch(
            """SELECT patch_json FROM skill_raw_patches srp
               JOIN skill_training_runs str ON srp.run_id = str.id
               WHERE str.skill_id = $1 AND srp.rejected = true""",
            skill_id,
        )
        rejected_targets = [
            {"op": r["patch_json"]["op"], "target": r["patch_json"]["target"]}
            for r in rejected
        ]

        # 5. Rollout — fetch items and run agent
        await _emit(_pool, run_id, "rollout", "stage_start", "Running agent on golden items…")
        items = await _pool.fetch(
            "SELECT input_text, expected_output, scoring_criteria FROM golden_items WHERE set_id = $1 LIMIT $2",
            effective_golden_set_id,
            config.mini_batch_size,
        )
        skill_name = skill_row["name"] or str(skill_id)
        rollout_results = await self._stage_rollout(
            skill_row["content_md"],
            list(items),
            langsmith_extra={
                "run_name": f"train/{skill_name}/rollout",
                "tags": ["skill_training", f"skill:{str(skill_id)[:8]}"],
                "kind": "skill_training",
                "run_id": str(run_id),
                "skill_id": str(skill_id),
                "agent_id": str(agent_id),
                "workspace_id": str(workspace_id),
            },
        )
        for r in rollout_results:
            passed = r["score"] >= 0.7
            await _emit(_pool, run_id, "rollout", "item_result",
                f"{'✓' if passed else '✗'} Score {r['score']:.3f} — {r['input_text'][:80]}",
                {"score": r["score"], "input": r["input_text"][:150],
                 "actual": r["actual_output"][:300], "rationale": r.get("rationale", "")})
        failures = [r for r in rollout_results if r["score"] < 0.7]
        await _emit(_pool, run_id, "rollout", "summary",
            f"{len(failures)}/{len(rollout_results)} items failed (score < 0.7)",
            {"total": len(rollout_results), "failures": len(failures)})

        if not failures:
            await _emit(_pool, run_id, "epoch", "stage_start",
                "Skill already performing well — no patches needed.")
            return {
                "accepted": False,
                "eval_score": baseline_score,
                "baseline_score": baseline_score,
                "candidate_skill_id": None,
                "patches_applied": 0,
                "patches_rejected": 0,
            }

        # 6. Reflect — propose patches
        await _emit(_pool, run_id, "reflect", "stage_start",
            f"Analyzing {len(failures)} failure(s) with LLM — proposing patches…")
        patches, failure_analysis = await self._stage_reflect(body, failures[:3], rejected_targets)
        if failure_analysis:
            await _emit(_pool, run_id, "reflect", "analysis", failure_analysis)
        for p in patches:
            await _emit(_pool, run_id, "reflect", "patch_proposed",
                f"{p.op.upper()} `{p.target}` (impact: {p.impact_score:.2f})",
                {"op": p.op, "target": p.target,
                 "content": p.content[:200], "impact_score": p.impact_score})

        # 7. Aggregate + Select — track count before capping for patches_rejected
        raw_patch_count = len(patches)
        patches = self._stage_aggregate(patches)
        patches = self._stage_select(patches, config.edit_budget)
        patches_rejected = raw_patch_count - len(patches)
        await _emit(_pool, run_id, "select", "summary",
            f"{len(patches)} patch{'es' if len(patches) != 1 else ''} selected, {patches_rejected} rejected",
            {"selected": len(patches), "rejected": patches_rejected})

        if not patches:
            await _emit(_pool, run_id, "select", "error",
                "No patches passed selection — try adding more golden examples.")
            return {
                "accepted": False,
                "eval_score": baseline_score,
                "baseline_score": baseline_score,
                "candidate_skill_id": None,
                "patches_applied": 0,
                "patches_rejected": patches_rejected,
            }

        # 8. Update — produce candidate skill body
        await _emit(_pool, run_id, "update", "stage_start",
            f"Applying {len(patches)} patch{'es' if len(patches) != 1 else ''} to skill…")
        new_body = self._stage_update(body, patches)
        bumped_front = _bump_version_in_frontmatter(frontmatter) if frontmatter else frontmatter
        candidate_md = (bumped_front + "\n\n" + new_body) if bumped_front else new_body

        # 9. Persist candidate as inactive skill version
        candidate_skill_id = await _pool.fetchval(
            """INSERT INTO agent_skills (agent_id, workspace_id, name, content_md, active, version, category)
               SELECT agent_id, workspace_id, name, $2, false, version + 1, category
               FROM agent_skills WHERE id = $1
               RETURNING id""",
            skill_id,
            candidate_md,
        )

        # 10. Evaluate candidate
        await _emit(_pool, run_id, "evaluate", "stage_start",
            "Evaluating candidate skill on golden set…")
        eval_result = await evaluate_golden_set(
            pool=_pool,
            golden_set_id=effective_golden_set_id,
            agent_id=agent_id,
            agent_version_label=f"reflact-candidate-{run_id}",
            workspace_id=workspace_id,
            system_prompt=candidate_md,
        )
        eval_score = eval_result.get("avg_score", 0.0)

        accepted = eval_score > baseline_score + config.min_val_improvement
        await _emit(_pool, run_id, "evaluate", "score",
            f"{'✓ Accepted' if accepted else '✗ Rejected'} — score {eval_score:.3f} "
            f"(baseline {baseline_score:.3f}, delta {eval_score - baseline_score:+.3f})",
            {"eval_score": eval_score, "baseline_score": baseline_score, "accepted": accepted})

        return {
            "accepted": accepted,
            "eval_score": eval_score,
            "baseline_score": baseline_score,
            "candidate_skill_id": candidate_skill_id,
            "patches_applied": len(patches),
            "patches_rejected": patches_rejected,
        }
