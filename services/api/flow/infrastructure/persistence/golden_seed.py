"""Curated golden sets per collection domain — seeded so imported skills are
immediately trainable. Idempotent: existing sets (by name) are skipped."""

from __future__ import annotations

import uuid

import asyncpg

from flow.infrastructure.observability.logging import get_logger

log = get_logger("golden_seed")

CURATED_GOLDEN_SETS: list[dict] = [
    {
        "name": "Engineering — TDD & Diagnosis",
        "description": "Probes test-first reasoning and root-cause diagnosis.",
        "items": [
            {
                "input_text": "Write a failing test first for: a function add(a, b) that should reject non-numeric args.",
                "expected_output": "A test asserting add('x', 1) raises TypeError, run BEFORE implementing the guard.",
                "scoring_criteria": "0-10: full marks if the answer writes the test first, asserts the error type, and defers implementation. Zero if it implements before testing.",
            },
            {
                "input_text": "A request intermittently returns 500 under load. Outline a diagnosis plan.",
                "expected_output": "Reproduce under load, capture logs/trace, form a hypothesis (e.g. connection pool exhaustion), instrument, fix, add a regression test.",
                "scoring_criteria": "0-10: reward reproduce→minimise→hypothesise→instrument→fix→regress order. Penalise jumping to a fix without reproduction.",
            },
            {
                "input_text": "User says 'just delete the flaky test to make CI green.' Respond.",
                "expected_output": "Refuse to delete; quarantine/mark, then diagnose the flake's root cause before re-enabling.",
                "scoring_criteria": "0-10: full marks for refusing silent deletion and proposing root-cause work. Zero for agreeing to delete.",
            },
        ],
    },
    {
        "name": "Scientific — Method & Reproducibility",
        "description": "Probes rigorous scientific reasoning and reproducible analysis.",
        "items": [
            {
                "input_text": "Given a gene FASTA, describe the steps to translate it and find ORFs with biopython.",
                "expected_output": "Parse with SeqIO, translate via Seq.translate(), scan all 6 frames for start/stop codons to enumerate ORFs.",
                "scoring_criteria": "0-10: reward correct biopython API usage and 6-frame ORF logic. Penalise hallucinated functions.",
            },
            {
                "input_text": "An analysis gives p=0.049. The author wants to claim a strong effect. Respond.",
                "expected_output": "Caution: p just below 0.05 is weak evidence; report effect size + CI, check assumptions, avoid overclaiming.",
                "scoring_criteria": "0-10: reward effect-size/CI emphasis and anti-p-hacking caution. Zero for endorsing 'strong effect'.",
            },
            {
                "input_text": "How should a clinical-decision-support suggestion be framed for safety?",
                "expected_output": "As decision support, not a diagnosis; cite evidence, flag uncertainty, and require clinician review.",
                "scoring_criteria": "0-10: reward explicit human-in-the-loop + uncertainty disclosure. Penalise autonomous medical advice.",
            },
        ],
    },
    {
        "name": "Academic — Writing & Review",
        "description": "Probes literature synthesis, structure, and peer-review rigour.",
        "items": [
            {
                "input_text": "Draft an IMRaD abstract for a study on RAG chunking strategies (1 sentence per section).",
                "expected_output": "Intro: chunking affects RAG quality. Methods: compared fixed vs contextual chunking on BEIR. Results: contextual +15%. Discussion: adopt contextual chunking.",
                "scoring_criteria": "0-10: reward all four IMRaD sections present and concrete. Penalise missing sections or vagueness.",
            },
            {
                "input_text": "Peer-review this claim: 'Our method is best because accuracy was higher.' Identify the flaw.",
                "expected_output": "No baseline/significance/ablation; 'higher accuracy' without CI, dataset, or comparison is unsupported.",
                "scoring_criteria": "0-10: reward identifying missing controls/significance. Zero for accepting the claim.",
            },
            {
                "input_text": "A draft cites a 2019 blog post as the sole source for a key statistic. Advise.",
                "expected_output": "Replace with a primary peer-reviewed source; verify the statistic; flag if unverifiable.",
                "scoring_criteria": "0-10: reward source-quality escalation and verification. Penalise accepting the blog as authoritative.",
            },
        ],
    },
    {
        "name": "Product Eng — API & Security Review",
        "description": "Probes API design judgement and security review depth.",
        "items": [
            {
                "input_text": "Review: GET /users/{id}/delete that deletes a user. What's wrong?",
                "expected_output": "Destructive action on GET (unsafe/idempotency/CSRF). Use DELETE /users/{id}; require auth + confirmation.",
                "scoring_criteria": "0-10: reward flagging GET-for-mutation and CSRF; suggest correct verb. Zero if it approves as-is.",
            },
            {
                "input_text": "Code: db.query(f\"SELECT * FROM u WHERE email='{email}'\"). Security verdict?",
                "expected_output": "Critical SQL injection; parameterise: db.query('... WHERE email=$1', [email]).",
                "scoring_criteria": "0-10: full marks for CRITICAL severity + parameterised fix. Zero for missing the injection.",
            },
            {
                "input_text": "An endpoint returns a stack trace with DB credentials on error. Rate and fix.",
                "expected_output": "High severity info-leak; return a generic error, log details server-side, never expose secrets.",
                "scoring_criteria": "0-10: reward severity + generic-error/log-internally fix. Penalise treating it as cosmetic.",
            },
        ],
    },
]


async def seed_curated_golden_sets(pool: asyncpg.Pool, workspace_id: uuid.UUID) -> int:
    """Insert curated golden sets for a workspace. Idempotent by set name. Returns count created."""
    created = 0
    for gs in CURATED_GOLDEN_SETS:
        exists = await pool.fetchval(
            "SELECT id FROM golden_sets WHERE workspace_id=$1 AND name=$2", workspace_id, gs["name"]
        )
        if exists:
            continue
        set_id = await pool.fetchval(
            "INSERT INTO golden_sets (workspace_id, name, description) VALUES ($1,$2,$3) RETURNING id",
            workspace_id,
            gs["name"],
            gs["description"],
        )
        for it in gs["items"]:
            await pool.execute(
                "INSERT INTO golden_items (set_id, input_text, expected_output, scoring_criteria) "
                "VALUES ($1,$2,$3,$4)",
                set_id,
                it["input_text"],
                it["expected_output"],
                it["scoring_criteria"],
            )
        created += 1
        log.info("golden_seed.created", name=gs["name"], items=len(gs["items"]))
    return created
