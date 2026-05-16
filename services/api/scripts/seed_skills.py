"""Seed Anthropic-style skills for all 11 agents.

Each agent gets 2 skills using YAML frontmatter + XML-sectioned markdown body.
Skills are idempotent: running twice won't duplicate (version bumps but replaces active).

Usage:
  uv run python scripts/seed_skills.py
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg

from flow.config import get_settings
from flow.infrastructure.observability.logging import configure_logging, get_logger

logger = get_logger("seed_skills")

# ── Skill content ─────────────────────────────────────────────────────────────
# Format: YAML frontmatter block + markdown body with <context>, <instructions>, <examples>

SKILLS: dict[str, list[dict]] = {
    "General Assistant": [
        {
            "name": "pdf-structured-extraction",
            "content_md": """\
---
name: pdf-structured-extraction
description: Extract tables, headings, metadata, and structured content from PDF or document text
version: "1.0"
allowed-tools: retrieve
triggers:
  - "extract from this PDF"
  - "parse this document"
  - "structured extraction"
  - "get tables from"
  - "document parsing"
metadata:
  author: flow-team
  domain: documents
  agent: General Assistant
---

# PDF Structured Extraction

<context>
Extract structured content from PDF or document text. Identify sections, tables, metadata, and key entities. Output must be structured JSON that downstream processes can consume without post-processing.
</context>

<instructions>
## Extraction targets
1. **Document metadata** — title, author, date, page count, language
2. **Section headings** — hierarchical structure (H1 → H2 → H3)
3. **Tables** — headers + rows as arrays of objects
4. **Key entities** — PERSON, ORG, DATE, AMOUNT, LOCATION
5. **Key facts** — numbered list of extractable factual claims

## Table extraction rules
- Align columns by header
- Preserve numeric precision
- Mark merged cells as [MERGED]
- Flag illegible cells as [ILLEGIBLE]

## Output schema
{"metadata": {...}, "sections": [{"level": int, "title": str}], "tables": [{"caption": str, "headers": [str], "rows": [[str]]}], "entities": [...], "key_facts": [str]}
</instructions>
""",
        },
        {
            "name": "named-entity-recognition",
            "content_md": """\
---
name: named-entity-recognition
description: Extract PERSON, ORG, LOCATION, MONEY, DATE, and PRODUCT entities from unstructured text
version: "1.0"
allowed-tools: retrieve
triggers:
  - "extract entities"
  - "named entities"
  - "find all people mentioned"
  - "find organizations"
  - "entity extraction"
  - "who and what is mentioned"
metadata:
  author: flow-team
  domain: nlp
  agent: General Assistant
---

# Named Entity Recognition

<context>
Extract structured entities from text. Prioritize precision over recall — only extract entities you are confident about. Provide span information (start/end character) when possible.
</context>

<instructions>
## Entity types
- PERSON — individual human names
- ORG — companies, institutions, government bodies
- LOCATION — cities, countries, geographic features
- MONEY — monetary values with currency
- DATE — specific or relative dates/times
- PRODUCT — named products, models, tools
- EVENT — named events (conferences, incidents)

## Per entity output
{"text": str, "type": str, "start": int|null, "end": int|null, "confidence": float}

## Confidence thresholds
- ≥ 0.9: clear, unambiguous mention
- 0.7-0.9: reasonable inference from context
- < 0.7: flag as UNCERTAIN, include with caveat

## Output
{"entities": [...], "summary": {"total": int, "by_type": {type: count}}}
</instructions>
""",
        },
        {
            "name": "abstractive-summarization",
            "content_md": """\
---
name: abstractive-summarization
description: Produce abstractive summaries of long documents — not extraction, but genuine synthesis and paraphrase
version: "1.0"
allowed-tools: retrieve
triggers:
  - "summarize this"
  - "give me a summary"
  - "TL;DR"
  - "abstract this document"
  - "condense this"
metadata:
  author: flow-team
  domain: nlp
  agent: General Assistant
---

# Abstractive Summarization

<context>
Produce genuine abstractive summaries — paraphrase and synthesize, don't just extract sentences. The summary should read as if written by a human expert who digested the content and re-explained it concisely.
</context>

<instructions>
## Summarization levels
- **Executive** (50-100 words) — what + so what. For senior decision-makers.
- **Standard** (150-250 words) — key findings, methodology, implications.
- **Detailed** (400-600 words) — full synthesis preserving nuance.

Default to Standard unless user specifies.

## Quality rules
1. No lifted verbatim sentences longer than 10 words
2. Preserve all quantitative claims with exact numbers
3. Preserve uncertainty — don't state as fact what the source hedges
4. Lead with the most important point (inverted pyramid)

## Output
{"level": str, "word_count": int, "summary": str, "key_numbers": [str], "caveats": [str]}
</instructions>
""",
        },
        {
            "name": "text-sentiment-classifier",
            "content_md": """\
---
name: text-sentiment-classifier
description: Classify text sentiment (positive/negative/neutral/mixed) and detect emotion with confidence scores
version: "1.0"
allowed-tools: retrieve
triggers:
  - "sentiment analysis"
  - "what is the tone"
  - "positive or negative"
  - "classify this text"
  - "emotion detection"
metadata:
  author: flow-team
  domain: nlp
  agent: General Assistant
---

# Text Sentiment & Emotion Classification

<context>
Classify sentiment and detect emotional tone in text. Use a fine-grained model: report polarity (positive/negative/neutral/mixed) AND dominant emotion. Provide calibrated confidence scores.
</context>

<instructions>
## Sentiment dimensions
1. **Polarity** — positive / negative / neutral / mixed
2. **Intensity** — strong / moderate / weak
3. **Emotion** — joy / anger / sadness / fear / surprise / disgust / anticipation / trust (Plutchik wheel)
4. **Subjectivity** — objective (factual) / subjective (opinion)

## Granularity
- Sentence-level sentiment when text is ≥ 3 sentences (identify which sentences drive the aggregate)
- Document-level aggregate

## Output
{"polarity": str, "intensity": str, "confidence": float, "dominant_emotion": str, "emotion_scores": {emotion: float}, "subjectivity": str, "sentence_breakdown": [{"text": str, "polarity": str}]}
</instructions>
""",
        },
        {
            "name": "table-to-json-converter",
            "content_md": """\
---
name: table-to-json-converter
description: Convert HTML tables, markdown tables, or plain-text tabular data to clean JSON or CSV
version: "1.0"
allowed-tools: retrieve
triggers:
  - "convert this table"
  - "table to JSON"
  - "table to CSV"
  - "parse this table"
  - "structured data from table"
metadata:
  author: flow-team
  domain: data
  agent: General Assistant
---

# Table to JSON/CSV Converter

<context>
Convert tabular data from any text format (HTML, markdown, plain text, pipe-delimited) to clean, consistently typed JSON or CSV. Infer data types and handle messy real-world tables gracefully.
</context>

<instructions>
## Parsing steps
1. Detect table format (HTML / markdown / plain text / pipe-delimited)
2. Extract headers (row 0 or first non-empty row)
3. Infer column types: int, float, date, boolean, string
4. Cast values to inferred type; fallback to string on failure
5. Handle merged cells: repeat value in each spanned cell

## Data cleaning
- Strip whitespace from values
- Normalize date formats to ISO 8601
- Normalize boolean strings: yes/no/true/false/1/0 → true/false
- Replace empty strings with null

## Output format
```json
{
  "format_detected": str,
  "headers": [str],
  "types": {col: str},
  "rows": [{col: value}],
  "row_count": int,
  "warnings": [str]
}
```
</instructions>
""",
        },
        {
            "name": "semantic-text-similarity",
            "content_md": """\
---
name: semantic-text-similarity
description: Compute semantic similarity between a pair of texts and explain what makes them similar or different
version: "1.0"
allowed-tools: retrieve
triggers:
  - "how similar are these"
  - "semantic similarity"
  - "are these the same meaning"
  - "compare these texts"
  - "similarity score"
metadata:
  author: flow-team
  domain: nlp
  agent: General Assistant
---

# Semantic Text Similarity

<context>
Assess the semantic similarity between two texts. Go beyond surface-level lexical overlap to consider meaning, intent, and topic coverage. Provide an interpretable score and explanation.
</context>

<instructions>
## Similarity scale (0.0 – 1.0)
- 0.9-1.0: Near-identical meaning (paraphrases)
- 0.7-0.9: Same topic, highly related
- 0.5-0.7: Related but distinct perspectives
- 0.3-0.5: Loosely related
- 0.0-0.3: Unrelated

## Analysis dimensions
1. **Topic overlap** — shared concepts and entities
2. **Intent alignment** — same communicative goal?
3. **Factual consistency** — do they assert contradictory facts?
4. **Perspective** — same/different viewpoint on shared topics

## Output
{"score": float, "interpretation": str, "shared_concepts": [str], "divergences": [str], "factual_conflict": bool, "recommendation": "use either" | "prefer text_a" | "prefer text_b" | "contradictory"}
</instructions>
""",
        },
        {
            "name": "topic-clustering",
            "content_md": """\
---
name: topic-clustering
description: Cluster a list of documents, sentences, or items by topic and generate descriptive cluster labels
version: "1.0"
allowed-tools: retrieve
triggers:
  - "cluster these documents"
  - "group by topic"
  - "topic modeling"
  - "find themes in"
  - "categorize these items"
metadata:
  author: flow-team
  domain: nlp
  agent: General Assistant
---

# Topic Clustering

<context>
Group a list of texts or items into coherent topic clusters. Generate human-readable cluster labels and provide representative examples. Use semantic meaning, not just keywords.
</context>

<instructions>
## Clustering approach
1. Identify recurring themes, concepts, and entities
2. Group items that share the same primary topic
3. Allow items to belong to a secondary cluster (soft assignment)
4. Generate a 2-5 word label for each cluster
5. Identify singleton outliers (items that don't fit any cluster)

## Cluster quality criteria
- Each cluster should be internally coherent (members are about the same thing)
- Clusters should be mutually distinguishable
- Labels should be specific enough to be useful ("Machine Learning Safety" not "AI")

## Output
{"clusters": [{"id": int, "label": str, "size": int, "members": [int], "representative": str}], "outliers": [int], "summary": str}
</instructions>
""",
        },
        {
            "name": "code-explanation-generator",
            "content_md": """\
---
name: code-explanation-generator
description: Generate plain-English explanations of code snippets at the right level for the target audience
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "explain this code"
  - "what does this code do"
  - "code explanation"
  - "walk me through this"
  - "explain this function"
metadata:
  author: flow-team
  domain: engineering
  agent: General Assistant
---

# Code Explanation Generator

<context>
Explain code in plain English at the appropriate depth for the audience. Default to intermediate level (understands basic programming) unless specified. Never talk down; never over-assume.
</context>

<instructions>
## Explanation levels
- **Beginner** — explain concepts from scratch, use analogies
- **Intermediate** — assume programming basics, explain patterns and intent
- **Expert** — focus on non-obvious choices, tradeoffs, and edge cases

Default: Intermediate.

## Explanation structure
1. **What it does** — 1-2 sentences: overall purpose
2. **How it works** — step-by-step walkthrough of the logic
3. **Key concepts** — any patterns, algorithms, or idioms worth naming
4. **Gotchas** — edge cases, performance concerns, or footguns
5. **Example** — concrete input/output if helpful

## Rules
- Never restate the code line-by-line — synthesize intent
- Use analogies sparingly and only when genuinely clarifying
- Flag any code that looks incorrect or dangerous
</instructions>
""",
        },
        {
            "name": "prompt-engineering-assistant",
            "content_md": """\
---
name: prompt-engineering-assistant
description: Rewrite or improve a user prompt for clearer, more reliable LLM output — adding structure, constraints, and examples
version: "1.0"
allowed-tools: retrieve
triggers:
  - "improve this prompt"
  - "rewrite this prompt"
  - "prompt engineering"
  - "make this prompt better"
  - "optimize my prompt"
metadata:
  author: flow-team
  domain: ai
  agent: General Assistant
---

# Prompt Engineering Assistant

<context>
Improve user prompts to get better, more reliable LLM outputs. Apply prompt engineering best practices: add structure, constraints, output format specifications, and examples. Preserve the user's original intent.
</context>

<instructions>
## Improvement dimensions
1. **Clarity** — remove ambiguity; make the task concrete
2. **Constraints** — add output format, length, and tone requirements
3. **Role** — add a role prefix if it would help ("You are a...")
4. **Examples** — add 1-2 few-shot examples if the task is complex
5. **Chain of thought** — add "Think step by step" if reasoning is needed
6. **Output schema** — specify exact output format (JSON, markdown, list)

## What NOT to change
- The user's core intent and subject matter
- Domain-specific terminology they chose deliberately
- Explicit constraints they've already set

## Output
Provide:
1. **Improved prompt** — the rewritten version
2. **Changes made** — bulleted list of what you changed and why
3. **Confidence** — 0.0-1.0 that the improved prompt will yield better results
</instructions>
""",
        },
        {
            "name": "json-schema-validation",
            "content_md": """\
---
name: json-schema-validation
description: Validate a JSON object against a schema, surface mismatches, and suggest fixes
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "validate this JSON"
  - "JSON schema validation"
  - "check this against schema"
  - "is this valid JSON"
  - "schema mismatch"
metadata:
  author: flow-team
  domain: data
  agent: General Assistant
---

# JSON Schema Validation

<context>
Validate JSON objects against schemas (JSON Schema draft-07 or draft-2020-12). Surface all validation errors with clear explanations and concrete fix suggestions. Handle both schema inference (when no schema is provided) and explicit validation.
</context>

<instructions>
## Validation modes
1. **Explicit validation** — user provides both JSON and schema → validate and report errors
2. **Schema inference** — user provides JSON only → infer the likely schema and validate for consistency
3. **Schema generation** — user provides JSON → generate a JSON Schema that describes it

## Error reporting (per error)
- JSON path to the failing field
- Expected type/value/constraint
- Actual value found
- Suggested fix (concrete, not vague)

## Output
{"valid": bool, "errors": [{"path": str, "rule": str, "expected": str, "actual": str, "fix": str}], "warnings": [str], "mode": str}
</instructions>
""",
        },
        {
            "name": "creative-ideation-generator",
            "content_md": """\
---
name: creative-ideation-generator
description: Brainstorm N diverse, creative ideas around a theme — with scoring, feasibility notes, and a recommended top pick
version: "1.0"
allowed-tools: retrieve
triggers:
  - "brainstorm ideas"
  - "generate ideas"
  - "creative ideation"
  - "give me ideas for"
  - "what could we do about"
metadata:
  author: flow-team
  domain: creativity
  agent: General Assistant
---

# Creative Ideation Generator

<context>
Generate diverse, high-quality ideas on a given theme. Prioritize variety over quantity — ensure ideas span different approaches (incremental, radical, adjacent-domain). Always include a recommendation with reasoning.
</context>

<instructions>
## Ideation process
1. Generate ideas across 4 divergence axes:
   - **Incremental** — improve the existing approach
   - **Adjacent** — borrow from a related domain
   - **Radical** — challenge the core assumption
   - **Combinatorial** — combine two existing ideas

2. Score each idea:
   - **Impact** (1-5): potential value if it works
   - **Feasibility** (1-5): effort/cost to execute
   - **Novelty** (1-5): how fresh/differentiated

3. Pick the top idea with rationale.

## Output
{"theme": str, "ideas": [{"id": int, "title": str, "description": str, "axis": str, "impact": int, "feasibility": int, "novelty": int}], "recommendation": {"id": int, "rationale": str}, "count": int}
</instructions>
""",
        },
        {
            "name": "content-moderation-classifier",
            "content_md": """\
---
name: content-moderation-classifier
description: Classify text for toxicity, harassment, hate speech, or policy violations with confidence scores
version: "1.0"
allowed-tools: retrieve
triggers:
  - "moderate this content"
  - "is this safe"
  - "check for toxicity"
  - "content policy check"
  - "flag this text"
metadata:
  author: flow-team
  domain: trust-safety
  agent: General Assistant
---

# Content Moderation Classifier

<context>
Classify user-generated content against common content policy categories. Provide calibrated confidence scores and actionable decisions (allow / review / block). This is a decision support tool — final moderation decisions should involve human review for borderline cases.
</context>

<instructions>
## Classification categories
- **SAFE** — no policy violation
- **SPAM** — unsolicited commercial content, repetitive noise
- **HATE_SPEECH** — attacks based on race, religion, gender, sexual orientation
- **HARASSMENT** — targeted personal attacks
- **VIOLENCE** — graphic violence or threats
- **SELF_HARM** — self-harm glorification or instructions
- **SEXUALLY_EXPLICIT** — explicit sexual content
- **MISINFORMATION** — demonstrably false claims presented as fact

## Decision thresholds
- confidence ≥ 0.85: auto-decision appropriate
- 0.6-0.85: REVIEW (human moderator)
- < 0.6: ALLOW with low-confidence flag

## Output
{"categories": {category: confidence}, "decision": "allow"|"review"|"block", "primary_concern": str|null, "confidence": float, "explanation": str}
</instructions>
""",
        },
        {
            "name": "fact-check-claim-verifier",
            "content_md": """\
---
name: fact-check-claim-verifier
description: Assess the factual accuracy of a specific claim by identifying it as true, false, mixed, or unverifiable with evidence
version: "1.0"
allowed-tools: tavily_search, retrieve
triggers:
  - "fact check this"
  - "is this true"
  - "verify this claim"
  - "is this accurate"
  - "check this fact"
metadata:
  author: flow-team
  domain: trust-safety
  agent: General Assistant
---

# Fact-Check Claim Verifier

<context>
Assess the accuracy of specific factual claims. Search for corroborating and contradicting evidence. Never fabricate evidence — only report what you find. Distinguish between "false" (evidence against) and "unverifiable" (no reliable evidence either way).
</context>

<instructions>
## Verdict taxonomy
- **TRUE** — multiple reliable sources confirm the claim
- **MOSTLY_TRUE** — core claim correct, minor inaccuracies or missing context
- **MIXED** — partially correct, partially incorrect
- **MOSTLY_FALSE** — core claim incorrect, minor elements accurate
- **FALSE** — reliable sources directly contradict the claim
- **UNVERIFIABLE** — insufficient evidence to assess

## Evidence requirements
- Minimum 2 independent sources for TRUE/FALSE verdict
- Source quality: institutional > peer-reviewed > reputable outlet > general web
- Flag conflicting sources explicitly

## Output
{"claim": str, "verdict": str, "confidence": float, "evidence": [{"source": str, "quote": str, "supports": bool}], "context": str, "caveats": [str]}
</instructions>
""",
        },
        {
            "name": "citation-validity-checker",
            "content_md": """\
---
name: citation-validity-checker
description: Verify that cited URLs exist, are accessible, and that the cited content actually supports the claim being made
version: "1.0"
allowed-tools: fetch_webpage, tavily_search
triggers:
  - "check these citations"
  - "verify this reference"
  - "does this link work"
  - "citation check"
  - "source verification"
metadata:
  author: flow-team
  domain: research
  agent: General Assistant
---

# Citation Validity Checker

<context>
Verify citations for accessibility, relevance, and claim support. A citation that exists but doesn't support the claim it's attached to is worse than no citation — it creates false confidence.
</context>

<instructions>
## Verification steps per citation
1. **Reachability** — does the URL resolve (HTTP 200)?
2. **Content match** — does the page content relate to the claim?
3. **Claim support** — does the source actually assert what the citation claims?
4. **Source quality** — credibility assessment (institutional / peer-reviewed / journalism / blog)
5. **Recency** — is the source current enough for the claim?

## Verdict per citation
- VALID — accessible, relevant, supports claim
- ACCESSIBLE_BUT_UNSUPPORTIVE — URL works but doesn't support the claim
- DEAD_LINK — URL returns error or is unreachable
- PAYWALL — accessible but content gated
- MISLEADING — source actually contradicts the claim

## Output
{"citations": [{"url": str, "verdict": str, "claim": str, "quality": str, "notes": str}], "valid_count": int, "issues": [str]}
</instructions>
""",
        },
    ],

    "Research Analyst": [
        {
            "name": "structured-research-report",
            "content_md": """\
---
name: structured-research-report
description: Activate when the user requests a research report, literature review, or synthesis of academic findings
version: "1.0"
allowed-tools: arxiv_search, tavily_search, retrieve
triggers:
  - "write a report"
  - "research on"
  - "literature review"
  - "summarize findings"
  - "what does research say"
metadata:
  author: flow-team
  domain: research
  agent: Research Analyst
---

# Structured Research Reporting

<context>
You are generating a formal research report. The user expects sourced findings,
identified limitations, cross-referenced evidence, and a concrete conclusion.
Always cite sources with enough detail to locate them (arXiv ID, author, year).
</context>

<instructions>
## Step 1 — Gather sources
Search arXiv for recent papers (last 12 months preferred). Search Tavily for
industry context, blog posts, and complementary perspectives.

## Step 2 — Cross-reference
Identify contradictions between sources. Assign confidence levels (0.0–1.0).
Flag findings that appear in only one source as lower confidence.

## Step 3 — Structure output
Output MUST match this JSON schema:
{
  "title": str,
  "summary": str (2-3 sentences),
  "key_findings": [{"claim": str, "source": str, "confidence": float}],
  "limitations": [str],
  "conclusion": str,
  "recommended_reading": [str]
}

## Step 4 — Quality check
Before returning: verify each finding has a source, confidence sum > 0,
and conclusion logically follows from findings.
</instructions>

<examples>
Input: "What are the latest advances in RAG?"
Output:
{
  "title": "Retrieval-Augmented Generation: 2024-2025 Advances",
  "summary": "RAG has matured rapidly with contextual chunking, hybrid retrieval, and re-ranking becoming standard.",
  "key_findings": [
    {"claim": "Contextual chunking outperforms fixed-size chunking by 15-20%", "source": "arXiv:2312.10997", "confidence": 0.9},
    {"claim": "Hybrid sparse+dense retrieval consistently beats either alone", "source": "Multiple BEIR benchmarks", "confidence": 0.85}
  ],
  "limitations": ["Most benchmarks use synthetic QA pairs", "Latency benchmarks rarely reflect production load"],
  "conclusion": "RAG is production-ready with clear improvement vectors in retrieval quality and chunking strategy.",
  "recommended_reading": ["arXiv:2312.10997", "BEIR benchmark paper"]
}
</examples>
""",
        },
        {
            "name": "source-validation",
            "content_md": """\
---
name: source-validation
description: Activate when evaluating the credibility, recency, or relevance of a source before including it in a report
version: "1.0"
allowed-tools: arxiv_search, fetch_webpage, tavily_search
triggers:
  - "is this source reliable"
  - "verify this paper"
  - "check this claim"
  - "how credible is"
metadata:
  author: flow-team
  domain: research
  agent: Research Analyst
---

# Source Validation Protocol

<context>
Before including a source in a report, validate it for recency, authority, and relevance.
This skill prevents hallucinated citations and low-quality sources from degrading report quality.
</context>

<instructions>
## Validation criteria (score each 0-3)
1. **Recency** — published within 2 years: 3 / within 5 years: 2 / older: 1 / unknown: 0
2. **Authority** — peer-reviewed or institutional: 3 / reputable outlet: 2 / blog/forum: 1 / unknown: 0
3. **Relevance** — directly addresses the claim: 3 / tangentially related: 2 / adjacent domain: 1

Total score ≥ 7: include. 4-6: include with caveat. < 4: exclude.

## Output format
{"source": str, "recency": int, "authority": int, "relevance": int, "total": int, "verdict": "include"|"caveat"|"exclude", "reason": str}
</instructions>

<examples>
Input: Validate "LLaVA paper from 2023 on multimodal LLMs"
Output: {"source": "LLaVA (2023)", "recency": 2, "authority": 3, "relevance": 3, "total": 8, "verdict": "include", "reason": "Peer-reviewed, highly cited, directly relevant"}
</examples>
""",
        },
    ],

    "Code Review Agent": [
        {
            "name": "security-vulnerability-scan",
            "content_md": """\
---
name: security-vulnerability-scan
description: Activate when reviewing code for security vulnerabilities, injection flaws, or unsafe patterns
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "review this code"
  - "security audit"
  - "find vulnerabilities"
  - "is this code safe"
  - "SQL injection"
  - "XSS"
metadata:
  author: flow-team
  domain: security
  agent: Code Review Agent
---

# Security Vulnerability Scan

<context>
You are performing a security-focused code review. Your job is to find exploitable
vulnerabilities, not just style issues. Prioritize: injection flaws, auth bypass,
insecure deserialization, and data exposure.
</context>

<instructions>
## OWASP Top 10 checklist
For each finding, report:
- Vulnerability type (OWASP category)
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Line/location reference
- Exploitation scenario (1 sentence)
- Remediation (concrete code fix)

## Priority order
1. Injection (SQL, command, LDAP, XPath)
2. Broken authentication and session management
3. Sensitive data exposure
4. Security misconfiguration
5. Insecure deserialization

## Output schema
{"vulnerabilities": [{"type": str, "severity": str, "location": str, "scenario": str, "fix": str}], "safe": bool, "summary": str}
</instructions>

<examples>
Input: "def get_user(db, username): return db.execute(f'SELECT * FROM users WHERE name={username}')"
Output:
{
  "vulnerabilities": [
    {
      "type": "SQL Injection (A03:2021)",
      "severity": "CRITICAL",
      "location": "get_user function, line 1",
      "scenario": "Attacker passes \"admin' OR '1'='1\" to bypass authentication",
      "fix": "Use parameterized query: db.execute('SELECT * FROM users WHERE name=$1', username)"
    }
  ],
  "safe": false,
  "summary": "Critical SQL injection vulnerability — parameterize all queries immediately."
}
</examples>
""",
        },
        {
            "name": "code-quality-assessment",
            "content_md": """\
---
name: code-quality-assessment
description: Activate when evaluating code quality, maintainability, complexity, or adherence to best practices
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "code review"
  - "code quality"
  - "refactor suggestions"
  - "is this good code"
  - "review my implementation"
metadata:
  author: flow-team
  domain: engineering
  agent: Code Review Agent
---

# Code Quality Assessment

<context>
You are performing a quality-focused code review. Focus on maintainability,
testability, and correctness — not style preferences. Report only issues
that a senior engineer would flag in a real PR review.
</context>

<instructions>
## Review dimensions (score each 1-5)
1. **Correctness** — Does it do what it claims? Edge cases handled?
2. **Readability** — Can a new engineer understand it in < 2 minutes?
3. **Testability** — Are dependencies injectable? Side effects isolated?
4. **Performance** — Any O(n²) surprises, N+1 queries, or memory leaks?

## For each issue found
- Category: correctness / readability / testability / performance
- Severity: must-fix / should-fix / nice-to-have
- Specific location
- Concrete suggestion

## Output schema
{"scores": {"correctness": int, "readability": int, "testability": int, "performance": int}, "overall": float, "issues": [...], "strengths": [str]}
</instructions>

<examples>
Input: Python function that loads all DB rows into memory to filter in Python
Output: {"scores": {"correctness": 4, "readability": 4, "testability": 3, "performance": 1}, "overall": 3.0, "issues": [{"category": "performance", "severity": "must-fix", "location": "line 12", "suggestion": "Filter in SQL with WHERE clause instead of loading all rows"}], "strengths": ["Clear variable names", "Good docstring"]}
</examples>
""",
        },
    ],

    "Daily AI Briefing": [
        {
            "name": "news-digest-synthesis",
            "content_md": """\
---
name: news-digest-synthesis
description: Activate when compiling a daily or weekly AI news briefing from multiple sources
version: "1.0"
allowed-tools: tavily_search, fetch_webpage, hf_papers
triggers:
  - "daily briefing"
  - "AI news"
  - "what happened in AI"
  - "weekly digest"
  - "summarize today"
metadata:
  author: flow-team
  domain: news
  agent: Daily AI Briefing
---

# News Digest Synthesis

<context>
You compile concise, high-signal AI news briefings. Your audience is technical
practitioners who want signal over noise. Focus on research breakthroughs,
product launches, and policy changes — not hype.
</context>

<instructions>
## Collection phase
Search Tavily for "AI news [today/this week]". Fetch HuggingFace papers for
research highlights. Cross-check: include a story only if 2+ sources confirm.

## Structure (fixed)
1. **Top story** — 3 sentences max, why it matters
2. **Research picks** — 2-3 arXiv/HF papers with 1-sentence summaries
3. **Industry moves** — product launches, partnerships, funding rounds
4. **Worth watching** — 1 trend or debate gaining momentum

## Tone
Concise. No filler phrases ("in a groundbreaking development..."). Direct assertions.
If uncertain, say so. Never fabricate details.
</instructions>

<examples>
Output skeleton:
**Top Story:** [Company] released [model/product]. It achieves [benchmark] on [task], [why it matters in 1 sentence].
**Research:** • [Paper title] — [1 sentence]. • [Paper title] — [1 sentence].
**Industry:** [Company A] acquired [Company B] for $[X]B to strengthen [area].
**Watch:** [Trend] is accelerating — [evidence in 1 sentence].
</examples>
""",
        },
        {
            "name": "relevance-filtering",
            "content_md": """\
---
name: relevance-filtering
description: Activate when filtering a list of news items or papers to select the most relevant for the briefing audience
version: "1.0"
allowed-tools: retrieve
triggers:
  - "filter these stories"
  - "which stories are relevant"
  - "rank by importance"
  - "select top stories"
metadata:
  author: flow-team
  domain: news
  agent: Daily AI Briefing
---

# Relevance Filtering

<context>
Given a list of candidate stories or papers, select the most relevant for a
technical AI practitioner audience. Prioritize genuine novelty over incremental updates.
</context>

<instructions>
## Scoring criteria (each 0-3)
- **Novelty** — new capability / technique not seen before
- **Impact** — affects how practitioners build or deploy AI
- **Evidence quality** — peer-reviewed / reproduced vs press release

Include if total ≥ 5. Flag as "notable but low-evidence" if 3-4. Exclude below 3.

## Output
Sorted list: [{"title": str, "score": int, "reason": str, "include": bool}]
</instructions>

<examples>
Input: ["GPT-5 rumors surface on Twitter", "Anthropic publishes safety evals methodology paper", "Startup raises $10M for AI chatbot"]
Output: [{"title": "Anthropic publishes safety evals methodology", "score": 8, "reason": "Novel methodology, peer-reviewed quality, directly impacts practitioners", "include": true}, {"title": "Startup raises $10M", "score": 4, "reason": "Notable but low evidence of real impact", "include": false}, {"title": "GPT-5 rumors", "score": 2, "reason": "Unverified rumor, no evidence", "include": false}]
</examples>
""",
        },
    ],

    "Knowledge Curator": [
        {
            "name": "knowledge-extraction",
            "content_md": """\
---
name: knowledge-extraction
description: Activate when extracting structured knowledge entities and relationships from unstructured text
version: "1.0"
allowed-tools: retrieve, long_term_memory
triggers:
  - "extract knowledge"
  - "find entities"
  - "identify concepts"
  - "build knowledge graph"
  - "what are the key concepts"
metadata:
  author: flow-team
  domain: knowledge-management
  agent: Knowledge Curator
---

# Knowledge Extraction

<context>
You extract structured knowledge from text to populate a knowledge graph.
Focus on entities (people, organizations, concepts, techniques) and their
relationships. Prefer precision over recall — only extract high-confidence facts.
</context>

<instructions>
## Entity types to extract
- CONCEPT (technique, method, idea)
- PERSON (researcher, practitioner)
- ORGANIZATION (lab, company, institution)
- ARTIFACT (paper, dataset, model, tool)

## Relationship types
- DEVELOPED_BY, USED_IN, RELATED_TO, PART_OF, CONTRADICTS, EXTENDS

## Output schema
{
  "entities": [{"id": str, "type": str, "name": str, "description": str}],
  "relationships": [{"from": str, "to": str, "type": str, "confidence": float}]
}

Only include relationships with confidence ≥ 0.7.
</instructions>

<examples>
Input: "Anthropic's Constitutional AI uses a set of principles to guide RLHF training, extending standard RLHF with an AI feedback step."
Output:
{
  "entities": [
    {"id": "e1", "type": "ORGANIZATION", "name": "Anthropic", "description": "AI safety company"},
    {"id": "e2", "type": "CONCEPT", "name": "Constitutional AI", "description": "RLHF variant using AI-generated feedback"},
    {"id": "e3", "type": "CONCEPT", "name": "RLHF", "description": "Reinforcement Learning from Human Feedback"}
  ],
  "relationships": [
    {"from": "e1", "to": "e2", "type": "DEVELOPED_BY", "confidence": 0.98},
    {"from": "e2", "to": "e3", "type": "EXTENDS", "confidence": 0.95}
  ]
}
</examples>
""",
        },
        {
            "name": "curation-deduplication",
            "content_md": """\
---
name: curation-deduplication
description: Activate when detecting duplicate or overlapping knowledge entries before adding to the knowledge base
version: "1.0"
allowed-tools: retrieve, long_term_memory
triggers:
  - "is this already in the knowledge base"
  - "check for duplicates"
  - "deduplicate"
  - "merge entries"
metadata:
  author: flow-team
  domain: knowledge-management
  agent: Knowledge Curator
---

# Curation & Deduplication

<context>
Before adding new knowledge entries, check for semantic duplicates. Merge
overlapping entries rather than creating redundant ones. Preserve the richer
of two competing entries.
</context>

<instructions>
## Deduplication strategy
1. Retrieve existing entries by entity name + type
2. Compute semantic overlap (shared attributes > 60% = duplicate candidate)
3. For duplicates: merge descriptions, union relationships, keep higher confidence

## Merge rules
- Descriptions: prefer longer/more specific
- Relationships: union with max confidence
- Metadata: merge, prefer newer

## Output
{"action": "add"|"merge"|"skip", "target_id": str|null, "merged_entity": dict|null, "reason": str}
</instructions>

<examples>
Input: New entity "GPT-4" (ARTIFACT), existing "GPT-4 by OpenAI" (ARTIFACT)
Output: {"action": "merge", "target_id": "existing-uuid", "merged_entity": {"name": "GPT-4", "description": "Large multimodal language model by OpenAI (2023)", "organization": "OpenAI"}, "reason": "Same artifact, new entry adds version detail"}
</examples>
""",
        },
    ],

    "Data Analyst": [
        {
            "name": "exploratory-data-analysis",
            "content_md": """\
---
name: exploratory-data-analysis
description: Activate when performing exploratory data analysis, statistical summaries, or dataset profiling
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "analyze this data"
  - "EDA"
  - "exploratory analysis"
  - "describe this dataset"
  - "data profiling"
  - "summary statistics"
metadata:
  author: flow-team
  domain: data-science
  agent: Data Analyst
---

# Exploratory Data Analysis

<context>
You perform structured EDA to understand dataset shape, quality, and distributions
before any modeling or deeper analysis. Surface actionable findings — not just
raw statistics.
</context>

<instructions>
## EDA pipeline
1. **Shape & types** — rows, columns, dtypes, memory usage
2. **Missing values** — count and % per column; flag if > 5%
3. **Distributions** — for numeric: mean/median/std/skew/outliers; for categorical: top-5 values + cardinality
4. **Correlations** — Pearson for numeric pairs; flag |r| > 0.7
5. **Anomalies** — duplicate rows, impossible values, date range issues

## Output schema
{"shape": [int, int], "missing": {col: {count: int, pct: float}}, "distributions": {...}, "correlations": [{col_a, col_b, r}], "anomalies": [str], "recommendations": [str]}
</instructions>

<examples>
Input: CSV with 1000 rows, columns: age (int), salary (float), department (str), hire_date (date)
Output: {"shape": [1000, 4], "missing": {"salary": {"count": 12, "pct": 1.2}}, "distributions": {"age": {"mean": 34.2, "median": 33, "std": 8.1, "skew": 0.3}}, "correlations": [{"col_a": "age", "col_b": "salary", "r": 0.72}], "anomalies": ["3 rows with age=0", "hire_date has 2 future dates"], "recommendations": ["Impute salary with median by department", "Investigate age=0 records"]}
</examples>
""",
        },
        {
            "name": "insight-generation",
            "content_md": """\
---
name: insight-generation
description: Activate when generating business insights, recommendations, or narrative summaries from analyzed data
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "what insights can you find"
  - "generate insights"
  - "business recommendations"
  - "what does this data tell us"
  - "data storytelling"
metadata:
  author: flow-team
  domain: data-science
  agent: Data Analyst
---

# Data Insight Generation

<context>
Transform analytical findings into actionable business insights. Each insight
must be specific, evidence-backed, and include a concrete recommendation.
Avoid vague observations — every insight must answer "so what?"
</context>

<instructions>
## Insight structure (required for each)
1. **Observation** — what the data shows (cite metric)
2. **So what?** — business implication
3. **Recommendation** — concrete action
4. **Confidence** — HIGH / MEDIUM / LOW (based on sample size and signal strength)

## Prioritization
Rank insights by: (potential impact) × (confidence). Lead with highest.

## Output
{"insights": [{"observation": str, "implication": str, "recommendation": str, "confidence": str, "supporting_metrics": [str]}], "executive_summary": str}
</instructions>

<examples>
Input: Sales data showing Q3 drop in APAC region while EMEA grew
Output: {"insights": [{"observation": "APAC revenue declined 18% in Q3 vs Q2", "implication": "Market condition or product-market fit issue in APAC", "recommendation": "Review APAC pricing strategy and compare product adoption vs EMEA", "confidence": "HIGH", "supporting_metrics": ["APAC Q3: $1.2M", "APAC Q2: $1.46M", "EMEA Q3: +12%"]}], "executive_summary": "APAC underperformance is the key risk. Investigate pricing and adoption before Q4 planning."}
</examples>
""",
        },
    ],

    "Legal Document Analyzer": [
        {
            "name": "contract-risk-extraction",
            "content_md": """\
---
name: contract-risk-extraction
description: Activate when reviewing contracts or legal documents to identify risky clauses, obligations, and liabilities
version: "1.0"
allowed-tools: retrieve, long_term_memory
triggers:
  - "review this contract"
  - "find risks in this agreement"
  - "analyze this legal document"
  - "what are the risky clauses"
  - "liability analysis"
metadata:
  author: flow-team
  domain: legal
  agent: Legal Document Analyzer
---

# Contract Risk Extraction

<context>
You extract and assess risk from legal documents. You are NOT providing legal advice —
you flag patterns that warrant attorney review. Always recommend professional legal
counsel for material decisions.
</context>

<instructions>
## Risk categories to scan
1. **Liability caps** — absence or unreasonably low limits
2. **Indemnification** — one-sided or uncapped indemnification clauses
3. **IP ownership** — work-for-hire, assignment, or license ambiguity
4. **Termination** — termination for convenience, auto-renewal traps
5. **Governing law** — unfavorable jurisdiction
6. **Force majeure** — missing or too narrow

## For each finding
- Clause reference (section/page)
- Risk type
- Severity: HIGH / MEDIUM / LOW
- Explanation (plain language, 2 sentences)
- Suggested revision or question for counsel

## Output
{"risks": [{...}], "overall_risk": "HIGH"|"MEDIUM"|"LOW", "recommend_counsel": bool}
</instructions>

<examples>
Input: "Section 12: Vendor shall indemnify Client for any and all claims arising from any use of the Software, without limitation."
Output: {"risks": [{"clause": "Section 12", "type": "Indemnification", "severity": "HIGH", "explanation": "Uncapped, unlimited indemnification exposes vendor to catastrophic liability. 'Any and all' with 'without limitation' is extremely broad.", "suggestion": "Cap indemnification at contract value or 12 months of fees; limit to third-party IP claims only."}], "overall_risk": "HIGH", "recommend_counsel": true}
</examples>
""",
        },
        {
            "name": "obligation-extraction",
            "content_md": """\
---
name: obligation-extraction
description: Activate when extracting party obligations, deadlines, and compliance requirements from legal documents
version: "1.0"
allowed-tools: retrieve
triggers:
  - "what are our obligations"
  - "extract deadlines"
  - "compliance requirements"
  - "what must we do"
  - "deliverable schedule"
metadata:
  author: flow-team
  domain: legal
  agent: Legal Document Analyzer
---

# Obligation Extraction

<context>
Extract all party obligations, deadlines, and compliance requirements from
a legal document. Create a structured checklist that can be used for contract
management and compliance tracking.
</context>

<instructions>
## Extraction targets
- Obligations with deadline (date or relative: "within 30 days of X")
- Recurring obligations (monthly reports, annual audits)
- Conditions precedent ("only if X, then Y")
- Negative obligations ("shall not", "must not")

## Per obligation
{"party": str, "obligation": str, "deadline": str|null, "recurring": bool, "condition": str|null, "source": str}

## Output
{"obligations": [...], "key_dates": [{"date": str, "event": str}], "compliance_checklist": [str]}
</instructions>

<examples>
Input: "Client shall pay invoice within 30 days of receipt. Vendor shall provide monthly usage reports by the 5th of each month."
Output: {"obligations": [{"party": "Client", "obligation": "Pay invoice", "deadline": "30 days from receipt", "recurring": false, "condition": null, "source": "Payment clause"}, {"party": "Vendor", "obligation": "Provide monthly usage report", "deadline": "5th of each month", "recurring": true, "condition": null, "source": "Reporting clause"}], "key_dates": [], "compliance_checklist": ["Track invoice receipt dates to ensure 30-day payment", "Set monthly reminder for Vendor report delivery by 5th"]}
</examples>
""",
        },
    ],

    "Competitive Intelligence": [
        {
            "name": "competitor-profile",
            "content_md": """\
---
name: competitor-profile
description: Activate when building a structured competitive profile for a company or product
version: "1.0"
allowed-tools: tavily_search, fetch_webpage, retrieve
triggers:
  - "competitive analysis"
  - "profile this competitor"
  - "research competitor"
  - "competitive landscape"
  - "analyze this company"
metadata:
  author: flow-team
  domain: strategy
  agent: Competitive Intelligence
---

# Competitor Profile

<context>
Build evidence-based competitive profiles. Focus on verifiable facts from
public sources. Distinguish between confirmed information and inferences.
Never speculate about private company financials without a source.
</context>

<instructions>
## Profile sections
1. **Overview** — company, founding, HQ, stage/size
2. **Products** — core products, positioning, pricing (if public)
3. **Strengths** — defensible advantages (tech, distribution, data, brand)
4. **Weaknesses** — observable gaps or vulnerabilities
5. **Recent moves** — last 90 days: launches, hires, funding, pivots
6. **Threat assessment** — HIGH / MEDIUM / LOW to our position and why

## Source requirements
Each major claim needs a source. Flag inferences explicitly.

## Output
{"company": str, "overview": {...}, "products": [...], "strengths": [...], "weaknesses": [...], "recent_moves": [...], "threat": {"level": str, "rationale": str}}
</instructions>

<examples>
Input: "Profile OpenAI as a competitor"
Output: {"company": "OpenAI", "overview": {"founded": 2015, "stage": "late-stage private", "hq": "San Francisco"}, "products": [{"name": "GPT-4", "positioning": "leading general LLM"}, {"name": "ChatGPT", "positioning": "consumer AI assistant"}], "strengths": ["Brand recognition", "API ecosystem", "Microsoft partnership"], "weaknesses": ["High inference costs", "Limited enterprise security features historically"], "recent_moves": ["GPT-4o launch with native multimodality"], "threat": {"level": "HIGH", "rationale": "Dominant market position and rapid release cadence"}}
</examples>
""",
        },
        {
            "name": "market-signal-detection",
            "content_md": """\
---
name: market-signal-detection
description: Activate when scanning for weak signals, emerging trends, or market shifts in the AI competitive landscape
version: "1.0"
allowed-tools: tavily_search, hf_papers, fetch_webpage
triggers:
  - "market signals"
  - "emerging trends"
  - "what's changing in the market"
  - "competitive shifts"
  - "weak signals"
metadata:
  author: flow-team
  domain: strategy
  agent: Competitive Intelligence
---

# Market Signal Detection

<context>
Identify early-stage market signals before they become obvious trends.
Focus on: hiring patterns, research publication velocity, patent activity,
pricing changes, and partnership announcements.
</context>

<instructions>
## Signal types to scan
1. **Research signals** — surge in papers on a topic (HF papers, arXiv)
2. **Hiring signals** — job postings in new capability areas
3. **Product signals** — beta launches, pricing changes, deprecations
4. **Partnership signals** — new integrations, distribution deals
5. **Funding signals** — rounds in adjacent categories

## Signal assessment
- Signal type + source
- Strength: STRONG / MODERATE / WEAK
- Time horizon: IMMEDIATE (< 3 months) / NEAR (3-12 months) / LONG (> 12 months)
- Strategic implication (1-2 sentences)

## Output
{"signals": [{"type": str, "description": str, "source": str, "strength": str, "horizon": str, "implication": str}], "headline_signal": str}
</instructions>

<examples>
Output item: {"type": "Research", "description": "40% increase in arXiv papers on mixture-of-experts in last 60 days", "source": "HuggingFace papers tracker", "strength": "STRONG", "horizon": "NEAR", "implication": "MoE is becoming standard for efficiency; expect competitor model releases using MoE in 6-9 months"}
</examples>
""",
        },
    ],

    "Meeting Summarizer": [
        {
            "name": "meeting-summary",
            "content_md": """\
---
name: meeting-summary
description: Activate when summarizing meeting transcripts, notes, or recordings into structured action items
version: "1.0"
allowed-tools: retrieve
triggers:
  - "summarize this meeting"
  - "meeting notes"
  - "action items"
  - "decisions made"
  - "who said what"
metadata:
  author: flow-team
  domain: productivity
  agent: Meeting Summarizer
---

# Meeting Summary

<context>
Transform meeting transcripts or notes into structured summaries with clear
action items, owners, and decisions. Prioritize accuracy over brevity —
misattributing a decision or action item is worse than being verbose.
</context>

<instructions>
## Summary structure
1. **TL;DR** — 2-3 sentences: what was decided, what's next
2. **Context** — meeting type, participants, date/duration
3. **Key decisions** — list, each with rationale if stated
4. **Action items** — owner, description, deadline
5. **Parking lot** — items raised but not resolved
6. **Next meeting** — date, agenda items if mentioned

## Attribution rules
- Only attribute statements you can trace to a specific speaker
- Use "The team agreed..." when consensus was implied but not explicitly stated
- Flag ambiguous ownership as "TBD"

## Output
{"tldr": str, "decisions": [{...}], "action_items": [{"owner": str, "action": str, "deadline": str|null}], "parking_lot": [str], "next_meeting": str|null}
</instructions>

<examples>
Input: "Alice: We'll go with option B for the API design. Bob: I'll update the spec by Friday. Carol: What about backward compat? — deferred."
Output: {"tldr": "Team chose Option B for API design. Bob owns spec update by Friday.", "decisions": [{"decision": "Option B for API design", "rationale": "Not stated", "owner": "Team"}], "action_items": [{"owner": "Bob", "action": "Update API spec", "deadline": "Friday"}], "parking_lot": ["Backward compatibility — deferred"], "next_meeting": null}
</examples>
""",
        },
        {
            "name": "sentiment-tone-analysis",
            "content_md": """\
---
name: sentiment-tone-analysis
description: Activate when analyzing the tone, sentiment, or interpersonal dynamics of a meeting transcript
version: "1.0"
allowed-tools: retrieve
triggers:
  - "how was the meeting tone"
  - "team sentiment"
  - "were people aligned"
  - "interpersonal dynamics"
  - "meeting health"
metadata:
  author: flow-team
  domain: productivity
  agent: Meeting Summarizer
---

# Meeting Sentiment & Tone Analysis

<context>
Analyze the interpersonal and emotional dynamics of a meeting. Flag friction,
disengagement, or misalignment — not to judge, but to help the team improve.
Be tactful and evidence-based.
</context>

<instructions>
## Analysis dimensions
1. **Alignment** — Did participants converge or leave with different understandings?
2. **Engagement** — Who participated? Who was silent?
3. **Conflict** — Direct or indirect disagreement? Resolved?
4. **Energy** — Overall tone: energized / neutral / tense / disengaged

## Evidence requirement
Every assessment needs a direct quote or observable behavior.
Do not infer emotions beyond what the text supports.

## Output
{"overall_tone": str, "alignment": {"level": str, "evidence": str}, "engagement": {participant: str}, "conflicts": [{"participants": [str], "topic": str, "resolved": bool}], "recommendations": [str]}
</instructions>

<examples>
Input: Meeting where Alice presented, Bob repeatedly interrupted, Carol stayed silent, team left without clear next steps
Output: {"overall_tone": "tense", "alignment": {"level": "LOW", "evidence": "No explicit agreement on next steps"}, "engagement": {"Alice": "high (presented)", "Bob": "high but disruptive", "Carol": "low (silent)"}, "conflicts": [{"participants": ["Alice", "Bob"], "topic": "Presentation approach", "resolved": false}], "recommendations": ["Establish speaking norms", "Follow up with Carol to ensure her input is captured"]}
</examples>
""",
        },
    ],

    "Bug Triage Assistant": [
        {
            "name": "bug-severity-classification",
            "content_md": """\
---
name: bug-severity-classification
description: Activate when classifying bug severity, priority, or urgency based on a bug report or description
version: "1.0"
allowed-tools: retrieve, sandbox
triggers:
  - "classify this bug"
  - "how severe is this"
  - "bug priority"
  - "triage this issue"
  - "P0 or P1"
metadata:
  author: flow-team
  domain: engineering
  agent: Bug Triage Assistant
---

# Bug Severity Classification

<context>
Triage incoming bug reports to assign accurate severity and priority.
Use a consistent framework to prevent priority inflation (everything is P0)
and ensure critical issues are escalated immediately.
</context>

<instructions>
## Severity levels
- **P0 (Critical)** — Production down, data loss, security breach. Page oncall NOW.
- **P1 (High)** — Major feature broken for significant % of users. Fix within 24h.
- **P2 (Medium)** — Feature degraded, workaround exists. Fix within sprint.
- **P3 (Low)** — Minor issue, cosmetic, edge case. Fix when capacity allows.

## Classification factors
1. **Blast radius** — % of users/systems affected
2. **Data risk** — any data loss or corruption possible?
3. **Security** — any security implication?
4. **Workaround** — does one exist?
5. **Revenue impact** — does it block transactions or core flows?

## Output
{"severity": "P0"|"P1"|"P2"|"P3", "rationale": str, "blast_radius": str, "data_risk": bool, "security_risk": bool, "recommended_action": str, "escalate": bool}
</instructions>

<examples>
Input: "Users can't check out — payment page returns 500 error for all users"
Output: {"severity": "P0", "rationale": "Checkout is broken for 100% of users, directly blocking revenue", "blast_radius": "100% of users", "data_risk": false, "security_risk": false, "recommended_action": "Page oncall immediately, roll back last payment service deploy", "escalate": true}
</examples>
""",
        },
        {
            "name": "root-cause-analysis",
            "content_md": """\
---
name: root-cause-analysis
description: Activate when performing root cause analysis for a bug or incident using logs, stack traces, or error descriptions
version: "1.0"
allowed-tools: sandbox, retrieve
triggers:
  - "root cause"
  - "why did this fail"
  - "analyze this stack trace"
  - "what caused this error"
  - "post-mortem"
metadata:
  author: flow-team
  domain: engineering
  agent: Bug Triage Assistant
---

# Root Cause Analysis

<context>
Perform structured root cause analysis for bugs and incidents. Use the
5-Whys technique to get past symptoms to underlying causes. Distinguish
between proximate causes (what broke) and root causes (why it could break).
</context>

<instructions>
## Analysis approach
1. **Symptom** — observable failure (what users/systems saw)
2. **Proximate cause** — immediate technical trigger
3. **5-Whys chain** — follow each "why" until you hit a systemic/process cause
4. **Root cause** — the systemic issue that allowed this to happen
5. **Contributing factors** — other conditions that made it worse

## Output schema
{
  "symptom": str,
  "proximate_cause": str,
  "why_chain": [str],  // each "why" answer, 3-5 items
  "root_cause": str,
  "contributing_factors": [str],
  "fix": str,           // proximate fix
  "systemic_fix": str   // prevents recurrence
}
</instructions>

<examples>
Input: "API returned 500 due to null pointer exception in user lookup"
Output: {"symptom": "500 errors on user lookup", "proximate_cause": "Null pointer exception — user object not checked before access", "why_chain": ["Why NPE? user was null", "Why null? lookup returned null for deleted user", "Why no check? deletion doesn't invalidate active sessions", "Why? session cleanup not implemented"], "root_cause": "Session management doesn't handle user deletion — sessions outlive the user record", "contributing_factors": ["No integration test covering deleted-user session scenario"], "fix": "Add null check before user attribute access", "systemic_fix": "Implement session invalidation on user deletion + add test coverage"}
</examples>
""",
        },
    ],

    "Financial Report Analyst": [
        {
            "name": "financial-metrics-extraction",
            "content_md": """\
---
name: financial-metrics-extraction
description: Activate when extracting financial metrics, KPIs, or performance indicators from reports or documents
version: "1.0"
allowed-tools: retrieve, fetch_webpage
triggers:
  - "analyze this financial report"
  - "extract financial metrics"
  - "revenue analysis"
  - "P&L analysis"
  - "financial performance"
metadata:
  author: flow-team
  domain: finance
  agent: Financial Report Analyst
---

# Financial Metrics Extraction

<context>
Extract and structure financial metrics from reports, earnings calls, or
financial statements. Prioritize accuracy — financial figures must be
sourced directly from the document, never extrapolated.
</context>

<instructions>
## Core metrics to extract (when present)
- Revenue (total, by segment, YoY growth)
- Gross profit and gross margin %
- EBITDA / Operating income
- Net income / EPS
- Cash and equivalents
- Debt (total, net)
- Key segment metrics (ARR, NRR, churn for SaaS; AUM for finance)

## Per metric format
{"metric": str, "value": number, "unit": str, "period": str, "vs_prior": str|null, "source": str}

## Output
{"period": str, "company": str, "metrics": [...], "highlights": [str], "concerns": [str]}
</instructions>

<examples>
Input: "Q3 2025: Revenue $2.1B (+18% YoY). Gross margin 68%. Net income $210M. ARR $8.4B."
Output: {"period": "Q3 2025", "company": "Unknown", "metrics": [{"metric": "Revenue", "value": 2.1, "unit": "B USD", "period": "Q3 2025", "vs_prior": "+18% YoY", "source": "Q3 report"}, {"metric": "Gross Margin", "value": 68, "unit": "%", "period": "Q3 2025", "vs_prior": null, "source": "Q3 report"}], "highlights": ["Revenue growth accelerating at 18% YoY", "Strong 68% gross margin"], "concerns": []}
</examples>
""",
        },
        {
            "name": "financial-narrative-synthesis",
            "content_md": """\
---
name: financial-narrative-synthesis
description: Activate when writing an executive-level narrative summary of financial performance for non-financial audiences
version: "1.0"
allowed-tools: retrieve
triggers:
  - "write financial summary"
  - "explain financial results"
  - "executive summary of financials"
  - "board-level summary"
  - "investor narrative"
metadata:
  author: flow-team
  domain: finance
  agent: Financial Report Analyst
---

# Financial Narrative Synthesis

<context>
Transform extracted financial metrics into a clear, executive-level narrative.
Your audience may not be financial experts — use plain language, explain
ratios in context, and highlight what matters for decision-making.
</context>

<instructions>
## Narrative structure
1. **Headline** — 1 sentence: what's the overall story (growth / decline / mixed)
2. **Revenue story** — what drove growth or decline
3. **Profitability** — margins trend, operating leverage
4. **Balance sheet health** — cash position, debt, runway if relevant
5. **Key risk** — 1 specific concern with evidence
6. **Outlook** — guidance if available, else analyst consensus signal

## Writing rules
- No jargon without explanation ("EBITDA margin" → "EBITDA margin (profit before interest/taxes/depreciation)")
- Every claim needs a number
- Use plain comparisons ("revenue grew faster than costs — a positive sign")

## Output
{"headline": str, "narrative": str (500 words max), "key_takeaways": [str (3 max)], "risk_flag": str|null}
</instructions>

<examples>
Headline: "Strong quarter: revenue grew 18% while costs grew only 12%, widening margins."
Takeaways: ["Revenue growth accelerating — 18% vs 14% last quarter", "Gross margin expansion signals improving product mix", "Net debt declining — financial position strengthening"]
</examples>
""",
        },
    ],

    "Content Strategist": [
        {
            "name": "content-brief-generation",
            "content_md": """\
---
name: content-brief-generation
description: Activate when creating a content brief for an article, blog post, or campaign asset
version: "1.0"
allowed-tools: tavily_search, retrieve
triggers:
  - "create a content brief"
  - "content strategy"
  - "write a brief for"
  - "content plan"
  - "article outline"
metadata:
  author: flow-team
  domain: content
  agent: Content Strategist
---

# Content Brief Generation

<context>
Create comprehensive content briefs that guide writers to produce SEO-optimized,
audience-appropriate content. The brief is the contract between strategist and writer —
it must be specific enough that the output is predictable.
</context>

<instructions>
## Brief components (all required)
1. **Target audience** — persona, pain points, knowledge level
2. **Search intent** — informational / navigational / commercial / transactional
3. **Target keyword** — primary + 3-5 secondary keywords
4. **Competitor analysis** — top 3 ranking articles: their angle, gaps to exploit
5. **Unique angle** — what makes our take different/better
6. **Structure** — H1, H2s, approximate word count per section
7. **CTAs** — primary and secondary calls to action
8. **Success metrics** — how we'll measure if this piece succeeded

## SEO guidance
- Title tag: 50-60 characters including primary keyword
- Meta description: 150-160 characters with CTA
- Internal linking: suggest 2-3 relevant existing articles to link from

## Output
{"title": str, "audience": {...}, "intent": str, "keywords": {...}, "angle": str, "outline": [...], "ctas": [...], "success_metrics": [...]}
</instructions>

<examples>
Input: "Brief for an article about RAG for enterprise"
Output: {"title": "RAG for Enterprise: Implementation Guide (2025)", "audience": {"persona": "Enterprise ML engineer", "pain_points": ["Hallucination risk", "Data privacy"], "knowledge_level": "advanced"}, "intent": "informational", "keywords": {"primary": "enterprise RAG implementation", "secondary": ["RAG architecture", "private document QA", "vector database enterprise"]}, "angle": "Unlike surface-level guides, focus on security architecture and data governance — gaps in competitor content", "outline": [{"h2": "Why RAG for enterprise differs from demos", "words": 300}, {"h2": "Architecture patterns", "words": 600}], "ctas": ["Download architecture template", "Book implementation consultation"], "success_metrics": ["Rank top 3 for primary keyword in 90 days", "20% email capture rate"]}
</examples>
""",
        },
        {
            "name": "audience-analysis",
            "content_md": """\
---
name: audience-analysis
description: Activate when analyzing target audience characteristics, behaviors, or content preferences for a campaign
version: "1.0"
allowed-tools: tavily_search, retrieve
triggers:
  - "audience analysis"
  - "who is our target audience"
  - "audience personas"
  - "content audience"
  - "reader profile"
metadata:
  author: flow-team
  domain: content
  agent: Content Strategist
---

# Audience Analysis

<context>
Build evidence-based audience profiles that inform content strategy. Ground
personas in observable data (surveys, community behavior, search patterns)
not assumptions. Each persona needs a "day in the life" to make it actionable.
</context>

<instructions>
## Persona dimensions
1. **Demographics** — role, company size, industry, experience level
2. **Goals** — what they're trying to accomplish
3. **Pain points** — what slows them down or keeps them up at night
4. **Information behavior** — where they consume content (channels, formats, cadence)
5. **Objections** — why they might not trust our content
6. **Day in the life** — 3-sentence narrative of their typical workday

## Content implications
For each persona: top 3 content formats, top 3 topics, preferred depth (overview vs deep-dive)

## Output
{"personas": [{...}], "primary_persona": str, "content_recommendations": {persona_name: {...}}}
</instructions>

<examples>
Persona: {"name": "Senior ML Engineer", "demographics": {"role": "ML Engineer L5+", "company_size": "500+", "industry": "tech/finance"}, "goals": ["Ship reliable models to production", "Stay current with research"], "pain_points": ["Debugging production model drift", "Translating research to prod-ready code"], "information_behavior": {"channels": ["arXiv", "Twitter/X", "HN"], "formats": ["technical deep-dives", "code tutorials"], "cadence": "daily reader"}, "objections": ["Too basic", "Not production-realistic"], "day_in_life": "Starts with paper review, spends most of the day debugging model behavior in staging, ends by reviewing PRs."}
</examples>
""",
        },
    ],
}


# ── DB operations ─────────────────────────────────────────────────────────────

async def seed_skills_for_workspace(pool: asyncpg.Pool, workspace_id: uuid.UUID) -> None:
    logger.info("seeding_skills", workspace_id=str(workspace_id))
    seeded = 0

    for agent_name, skills in SKILLS.items():
        agent_row = await pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 AND name = $2",
            workspace_id, agent_name,
        )
        if not agent_row:
            logger.warning("agent_not_found", name=agent_name)
            continue

        agent_id = agent_row["id"]

        for skill in skills:
            name = skill["name"]
            content_md = skill["content_md"]

            # Get next version (append-only versioning, matching repo.upsert_agent_skill)
            row = await pool.fetchrow(
                "SELECT COALESCE(MAX(version), 0) AS max_v FROM agent_skills WHERE agent_id=$1 AND name=$2",
                agent_id, name,
            )
            max_v = row["max_v"] if row else 0

            if max_v > 0:
                # Already seeded — skip (idempotent)
                logger.info("skill.exists", agent=agent_name, skill=name, version=max_v)
                continue

            # Deactivate old versions (none, but for correctness)
            await pool.execute(
                "UPDATE agent_skills SET active = false WHERE agent_id=$1 AND name=$2",
                agent_id, name,
            )

            await pool.execute(
                """
                INSERT INTO agent_skills (agent_id, workspace_id, name, version, content_md, active)
                VALUES ($1, $2, $3, $4, $5, true)
                """,
                agent_id, workspace_id, name, 1, content_md,
            )
            logger.info("skill.seeded", agent=agent_name, skill=name)
            seeded += 1

    logger.info("seed_skills.done", workspace_id=str(workspace_id), seeded=seeded)


async def seed(pool: asyncpg.Pool) -> None:
    workspaces = await pool.fetch("SELECT id FROM workspaces")
    if not workspaces:
        logger.error("no_workspace", message="No workspace found. Run migrations and create a user first.")
        return
    for ws in workspaces:
        await seed_skills_for_workspace(pool, ws["id"])


async def main() -> None:
    configure_logging(level="INFO", json_output=False, force_colors=True, service="seed_skills")
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        await seed(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
