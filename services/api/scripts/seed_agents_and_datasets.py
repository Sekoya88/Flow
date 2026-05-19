"""Seed diverse LangGraph agent types and golden evaluation datasets.

Creates 5 specialized agents across thematic domains, each with:
  - Full tool configuration
  - Detailed system prompt
  - TypedDict state definition (stored in config for documentation)
  - Pydantic output schema
  - Matched golden evaluation dataset (5–8 items each)

Usage:
  uv run python scripts/seed_agents_and_datasets.py
"""

from __future__ import annotations

import asyncio
import json
import uuid

import asyncpg

from flow.config import get_settings
from flow.infrastructure.observability.logging import configure_logging, get_logger

logger = get_logger("seed")

# ──────────────────────────────────────────────────────────────────────────────
# Agent definitions
# ──────────────────────────────────────────────────────────────────────────────

# Canonical 7 agents — anything else gets deleted on seed run
CANONICAL_AGENT_NAMES = [
    "General Assistant",
    "Research Analyst",
    "Code Review Agent",
    "Data Analyst",
    "Content Strategist",
    "Meeting Summarizer",
    "Bug Triage Assistant",
]

AGENTS = [
    {
        "name": "General Assistant",
        "template": "react-agent",
        "config": {
            "template": "react-agent",
            "system_prompt": (
                "You are Flow's General Assistant. Answer any user question accurately and concisely.\n"
                "\n"
                "You have specialized colleagues available via the `subagent_call` tool. Delegate when "
                "a task is highly specialized; otherwise, answer directly. Available specialists:\n"
                "  • Research Analyst — papers, web research, structured reports\n"
                "  • Code Review Agent — security + quality assessment of code diffs\n"
                "  • Data Analyst — exploratory analysis, sandbox-powered numeric work\n"
                "  • Content Strategist — content briefs, SEO planning\n"
                "  • Meeting Summarizer — transcript condensation\n"
                "  • Bug Triage Assistant — severity classification + root-cause analysis\n"
                "\n"
                "Decision rule: if the question fits one of the specialists' charters, call that agent "
                "via subagent_call with a tightly-scoped message; then synthesize the response for the "
                "user. Otherwise answer directly using your own tools (knowledge search, web, memory).\n"
                "\n"
                "Always cite sources you used (URLs, knowledge snippets, memory facts). Be concise."
            ),
            "tools": {
                "retrieve": True,
                "sandbox": True,
                "long_term_memory": True,
                "tavily_search": True,
                "fetch_webpage": True,
                "subagent_call": True,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.6},
        },
    },
    {
        "name": "Research Analyst",
        "template": "deer_flow",
        "config": {
            "template": "deer_flow",
            "system_prompt": (
                "You are a rigorous Research Analyst. When asked a research question you:\n"
                "1. Search arXiv for recent papers (last 6 months preferred).\n"
                "2. Search the web via Tavily for complementary context.\n"
                "3. Cross-reference findings, note contradictions.\n"
                "4. Produce a structured report: Background, Key Findings, Limitations, Conclusion.\n"
                "Output must be in JSON matching the ResearchReport schema:\n"
                "  {title, summary, key_findings: [{claim, source, confidence}], "
                "limitations: [str], conclusion, recommended_reading: [str]}"
            ),
            "tools": {
                "retrieve": False,
                "sandbox": False,
                "long_term_memory": True,
                "tavily_search": True,
                "fetch_webpage": True,
                "arxiv_search": True,
                "hf_papers": True,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.2},
            "state_schema": {
                "description": "ResearchState TypedDict",
                "fields": {
                    "query": "str",
                    "arxiv_results": "list[dict]",
                    "web_results": "list[dict]",
                    "draft_report": "str | None",
                    "final_report": "ResearchReport | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "ResearchReport",
                "fields": {
                    "title": "str",
                    "summary": "str",
                    "key_findings": "list[Finding]",
                    "limitations": "list[str]",
                    "conclusion": "str",
                    "recommended_reading": "list[str]",
                },
            },
        },
    },
    {
        "name": "Code Review Agent",
        "template": "tool-agent",
        "config": {
            "template": "tool-agent",
            "system_prompt": (
                "You are an expert Code Reviewer with 15+ years of experience in Python, TypeScript, "
                "and distributed systems. When given code:\n"
                "1. Run it in the Python sandbox to detect runtime errors.\n"
                "2. Check for: correctness, performance, security (OWASP Top 10), readability.\n"
                "3. Classify findings by severity: critical | high | medium | low | info.\n"
                "4. Suggest concrete fixes with before/after snippets.\n"
                "Output must be in JSON matching the ReviewReport schema:\n"
                "  {language, overall_verdict: 'approve'|'request_changes'|'reject', "
                "score: 0-10, findings: [{severity, category, line, description, fix}], summary}"
            ),
            "tools": {
                "retrieve": True,
                "sandbox": True,
                "long_term_memory": False,
                "tavily_search": False,
                "fetch_webpage": False,
                "arxiv_search": False,
                "hf_papers": False,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.1},
            "state_schema": {
                "description": "CodeReviewState TypedDict",
                "fields": {
                    "code": "str",
                    "language": "str",
                    "execution_result": "dict | None",
                    "findings": "list[Finding]",
                    "final_report": "ReviewReport | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "ReviewReport",
                "fields": {
                    "language": "str",
                    "overall_verdict": "Literal['approve', 'request_changes', 'reject']",
                    "score": "int",
                    "findings": "list[Finding]",
                    "summary": "str",
                },
            },
        },
    },
    {
        "name": "Meeting Summarizer",
        "template": "tool-agent",
        "config": {
            "template": "tool-agent",
            "system_prompt": (
                "You are a Meeting Summarizer. When given a meeting transcript or notes:\n"
                "1. Retrieve context about participants and prior meeting decisions from memory.\n"
                "2. Extract: key decisions made, action items (owner + deadline), open questions, and topics discussed.\n"
                "3. Write a concise executive summary (3-5 bullet points).\n"
                "4. Store action items and key decisions in long-term memory for future retrieval.\n"
                "Be precise: 'Alice will review the API spec by Friday' not 'someone will look at it'.\n"
                "Output JSON: {meeting_title, date, participants: [str], summary: [str], "
                "decisions: [{decision, rationale}], action_items: [{task, owner, deadline, priority: P1|P2|P3}], "
                "open_questions: [str], follow_up_date: str | None}"
            ),
            "tools": {
                "retrieve": True,
                "sandbox": False,
                "long_term_memory": True,
                "tavily_search": False,
                "fetch_webpage": False,
                "arxiv_search": False,
                "hf_papers": False,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.2},
            "state_schema": {
                "description": "MeetingState TypedDict",
                "fields": {
                    "transcript": "str",
                    "retrieved_context": "list[dict]",
                    "extracted_action_items": "list[ActionItem]",
                    "meeting_summary": "MeetingSummary | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "MeetingSummary",
                "fields": {
                    "meeting_title": "str",
                    "date": "str",
                    "participants": "list[str]",
                    "summary": "list[str]",
                    "decisions": "list[Decision]",
                    "action_items": "list[ActionItem]",
                    "open_questions": "list[str]",
                    "follow_up_date": "str | None",
                },
            },
        },
    },
    {
        "name": "Bug Triage Assistant",
        "template": "tool-agent",
        "config": {
            "template": "tool-agent",
            "system_prompt": (
                "You are a Bug Triage Assistant for software engineering teams. When given a bug report:\n"
                "1. Retrieve similar past bugs and related code context from the knowledge base.\n"
                "2. Write a minimal reproduction script and execute it in the sandbox to confirm the bug.\n"
                "3. Classify severity: P0 (production down), P1 (major feature broken), P2 (degraded), P3 (minor/cosmetic).\n"
                "4. Identify likely root cause based on code analysis and execution results.\n"
                "5. Suggest a fix approach with code snippets.\n"
                "Output JSON: {title, severity: P0|P1|P2|P3, confirmed: bool, reproduction_steps: [str], "
                "root_cause: str, affected_components: [str], fix_approach: str, estimated_effort: str, "
                "related_bugs: [str]}"
            ),
            "tools": {
                "retrieve": True,
                "sandbox": True,
                "long_term_memory": False,
                "tavily_search": False,
                "fetch_webpage": False,
                "arxiv_search": False,
                "hf_papers": False,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.1},
            "state_schema": {
                "description": "BugTriageState TypedDict",
                "fields": {
                    "bug_report": "str",
                    "retrieved_context": "list[dict]",
                    "reproduction_result": "dict | None",
                    "triage_result": "BugTriage | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "BugTriage",
                "fields": {
                    "title": "str",
                    "severity": "Literal['P0', 'P1', 'P2', 'P3']",
                    "confirmed": "bool",
                    "reproduction_steps": "list[str]",
                    "root_cause": "str",
                    "affected_components": "list[str]",
                    "fix_approach": "str",
                    "estimated_effort": "str",
                    "related_bugs": "list[str]",
                },
            },
        },
    },
    {
        "name": "Content Strategist",
        "template": "researcher-critic-writer",
        "config": {
            "template": "researcher-critic-writer",
            "system_prompt": (
                "You are a Content Strategist specializing in SEO-driven content planning and competitor gap analysis. "
                "When given a topic, product, or keyword:\n"
                "1. Research the competitive landscape: what content exists, who ranks, what angles are taken.\n"
                "2. Identify content gaps: high-intent queries that aren't well served.\n"
                "3. Draft a content brief: target keyword, search intent, outline, recommended word count, CTAs.\n"
                "4. Critique the brief: is it differentiated? Does it address a real user need?\n"
                "5. Refine into a final, actionable brief.\n"
                "Output JSON: {topic, target_keyword, search_intent: informational|commercial|transactional|navigational, "
                "competitor_analysis: [{url, strengths, gaps}], content_brief: {title, outline: [section], "
                "word_count_target, key_points: [str], cta: str}, differentiation_angle: str}"
            ),
            "tools": {
                "retrieve": False,
                "sandbox": False,
                "long_term_memory": False,
                "tavily_search": True,
                "fetch_webpage": True,
                "arxiv_search": False,
                "hf_papers": False,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.5},
            "state_schema": {
                "description": "ContentStrategyState TypedDict",
                "fields": {
                    "topic": "str",
                    "serp_results": "list[dict]",
                    "competitor_pages": "list[dict]",
                    "draft_brief": "str | None",
                    "critique": "str | None",
                    "final_brief": "ContentBrief | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "ContentBrief",
                "fields": {
                    "topic": "str",
                    "target_keyword": "str",
                    "search_intent": "str",
                    "competitor_analysis": "list[dict]",
                    "content_brief": "dict",
                    "differentiation_angle": "str",
                },
            },
        },
    },
    {
        "name": "Data Analyst",
        "template": "tool-agent",
        "config": {
            "template": "tool-agent",
            "system_prompt": (
                "You are a Data Analyst with expertise in Python (pandas, numpy, matplotlib, scipy). "
                "When given data or an analysis request:\n"
                "1. Write Python code to load, clean, and analyze the data.\n"
                "2. Execute it in the sandbox, capture stdout and any plots.\n"
                "3. Interpret the results: identify trends, anomalies, correlations.\n"
                "4. Provide actionable recommendations.\n"
                "Always validate data quality first. Show your code. "
                "Output: {task, code_executed, key_metrics: {str: float}, "
                "insights: [str], anomalies: [str], recommendations: [str], "
                "confidence: 0.0-1.0}"
            ),
            "tools": {
                "retrieve": False,
                "sandbox": True,
                "long_term_memory": False,
                "tavily_search": False,
                "fetch_webpage": False,
                "arxiv_search": False,
                "hf_papers": False,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.15},
            "state_schema": {
                "description": "AnalysisState TypedDict",
                "fields": {
                    "task": "str",
                    "data_input": "str | dict | None",
                    "code_iterations": "list[str]",
                    "execution_outputs": "list[dict]",
                    "analysis_result": "AnalysisReport | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "AnalysisReport",
                "fields": {
                    "task": "str",
                    "code_executed": "str",
                    "key_metrics": "dict[str, float]",
                    "insights": "list[str]",
                    "anomalies": "list[str]",
                    "recommendations": "list[str]",
                    "confidence": "float",
                },
            },
        },
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Golden evaluation datasets (keyed by agent name)
# ──────────────────────────────────────────────────────────────────────────────

GOLDEN_SETS: dict[str, dict] = {
    "Research Analyst": {
        "name": "Research Analyst — Core Capabilities",
        "description": "Tests ability to synthesize academic sources, identify key findings, and structure reports",
        "items": [
            {
                "input_text": "What are the latest advances in retrieval-augmented generation (RAG)?",
                "expected_output": json.dumps(
                    {
                        "title": "Advances in Retrieval-Augmented Generation",
                        "summary": "Recent work improves RAG via better chunking, hybrid retrieval, and re-ranking.",
                        "key_findings": [{"claim": "Contextual chunking outperforms fixed-size chunking", "source": "arXiv", "confidence": 0.9}],
                        "limitations": ["Most studies use synthetic benchmarks"],
                        "conclusion": "RAG is maturing rapidly with clear improvement vectors",
                        "recommended_reading": ["arXiv:2312.10997"],
                    }
                ),
                "scoring_criteria": "Report must include: (1) at least 2 cited sources, (2) structured findings with confidence scores, (3) identified limitations, (4) concrete conclusion. Score 0-10.",
            },
            {
                "input_text": "Summarize recent research on LLM alignment and safety techniques.",
                "expected_output": json.dumps(
                    {
                        "title": "LLM Alignment and Safety: 2024-2025 Landscape",
                        "summary": "RLHF, Constitutional AI, and DPO remain dominant. New work explores scalable oversight.",
                        "key_findings": [
                            {"claim": "DPO trains faster than PPO-based RLHF with comparable results", "source": "arXiv", "confidence": 0.85},
                            {
                                "claim": "Scalable oversight via debate shows promise for superhuman tasks",
                                "source": "Anthropic/OpenAI papers",
                                "confidence": 0.75,
                            },
                        ],
                        "limitations": ["Alignment metrics lack standardization"],
                        "conclusion": "No silver bullet; ensemble approaches may be necessary",
                        "recommended_reading": ["Constitutional AI paper", "DPO paper"],
                    }
                ),
                "scoring_criteria": "Must cover RLHF/DPO/Constitutional AI, cite specific techniques, acknowledge open problems.",
            },
            {
                "input_text": "What does recent research say about transformer scaling laws?",
                "expected_output": json.dumps(
                    {
                        "title": "Transformer Scaling Laws: Recent Findings",
                        "summary": "Chinchilla scaling laws revised compute-optimal training. Recent work questions power-law assumptions.",
                        "key_findings": [
                            {"claim": "Chinchilla-optimal models are undertrained by common practice", "source": "DeepMind", "confidence": 0.95},
                            {"claim": "Data quality matters as much as quantity at scale", "source": "Multiple sources", "confidence": 0.8},
                        ],
                        "limitations": ["Scaling laws may not generalize across modalities"],
                        "conclusion": "Compute-optimal training requires more tokens than previously thought",
                        "recommended_reading": ["Chinchilla paper", "Scaling Data-Constrained Language Models"],
                    }
                ),
                "scoring_criteria": "Must reference Chinchilla, explain compute-optimal training, note recent challenges.",
            },
            {
                "input_text": "Analyze research on multimodal language models — what architectures dominate?",
                "expected_output": json.dumps(
                    {
                        "title": "Multimodal LLM Architectures: State of the Art",
                        "summary": "Decoder-only transformers with vision encoders (CLIP-style) dominate. MoE variants gaining traction.",
                        "key_findings": [
                            {
                                "claim": "Late fusion (vision encoder → projection → LLM) is the dominant pattern",
                                "source": "Survey papers",
                                "confidence": 0.9,
                            },
                            {"claim": "Native multimodal training (Chameleon-style) shows promise", "source": "Meta AI", "confidence": 0.7},
                        ],
                        "limitations": ["Video understanding remains a hard problem"],
                        "conclusion": "CLIP + LLM fusion is battle-tested; native multimodal is the next frontier",
                        "recommended_reading": ["LLaVA", "Flamingo", "GPT-4V technical report"],
                    }
                ),
                "scoring_criteria": "Must name specific architectures, compare approaches, identify dominant patterns.",
            },
            {
                "input_text": "What are current challenges in neural network interpretability?",
                "expected_output": json.dumps(
                    {
                        "title": "Neural Network Interpretability: Open Challenges",
                        "summary": "Mechanistic interpretability advances but lacks scalability. Feature attribution remains disputed.",
                        "key_findings": [
                            {"claim": "Superposition makes individual neuron analysis unreliable", "source": "Anthropic", "confidence": 0.88},
                            {"claim": "Circuits-based analysis scales poorly to full models", "source": "Multiple labs", "confidence": 0.8},
                        ],
                        "limitations": ["Ground truth for interpretability is hard to define"],
                        "conclusion": "The field needs standardized benchmarks and more scalable methods",
                        "recommended_reading": ["Toy Models of Superposition", "In-context Learning and Induction Heads"],
                    }
                ),
                "scoring_criteria": "Must address superposition, cite mechanistic interpretability work, identify open problems.",
            },
        ],
    },
    "Code Review Agent": {
        "name": "Code Review Agent — Quality Assessment",
        "description": "Tests ability to detect bugs, security issues, and provide actionable fix suggestions",
        "items": [
            {
                "input_text": "Review this Python function:\n```python\ndef get_user(user_id):\n    conn = sqlite3.connect('app.db')\n    cursor = conn.cursor()\n    cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n    return cursor.fetchone()\n```",
                "expected_output": json.dumps(
                    {
                        "language": "python",
                        "overall_verdict": "request_changes",
                        "score": 2,
                        "findings": [
                            {
                                "severity": "critical",
                                "category": "security",
                                "line": 4,
                                "description": "SQL injection vulnerability via f-string interpolation",
                                "fix": "Use parameterized query: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
                            },
                            {
                                "severity": "high",
                                "category": "correctness",
                                "line": 2,
                                "description": "Connection never closed — resource leak",
                                "fix": "Use context manager: with sqlite3.connect('app.db') as conn:",
                            },
                        ],
                        "summary": "Critical SQL injection and resource leak. Must fix before any use.",
                    }
                ),
                "scoring_criteria": "Must identify SQL injection as critical, note connection leak, provide parameterized query fix.",
            },
            {
                "input_text": "Review this async Python:\n```python\nimport asyncio\nasync def fetch_all(urls):\n    results = []\n    for url in urls:\n        r = await fetch(url)\n        results.append(r)\n    return results\n```",
                "expected_output": json.dumps(
                    {
                        "language": "python",
                        "overall_verdict": "request_changes",
                        "score": 5,
                        "findings": [
                            {
                                "severity": "medium",
                                "category": "performance",
                                "line": 4,
                                "description": "Sequential awaiting negates async benefits — O(n) latency",
                                "fix": "Use asyncio.gather(*[fetch(url) for url in urls])",
                            },
                            {
                                "severity": "low",
                                "category": "correctness",
                                "line": None,
                                "description": "No error handling — one failed fetch crashes all",
                                "fix": "Use return_exceptions=True in gather or try/except per fetch",
                            },
                        ],
                        "summary": "Works but misses core async benefit. Use gather() for concurrent execution.",
                    }
                ),
                "scoring_criteria": "Must identify sequential await issue, suggest asyncio.gather, note missing error handling.",
            },
            {
                "input_text": "Review:\n```typescript\nconst users = await db.query(`SELECT * FROM users WHERE email = '${email}'`);\n```",
                "expected_output": json.dumps(
                    {
                        "language": "typescript",
                        "overall_verdict": "reject",
                        "score": 1,
                        "findings": [
                            {
                                "severity": "critical",
                                "category": "security",
                                "line": 1,
                                "description": "SQL injection via template literal interpolation",
                                "fix": "Use parameterized query: db.query('SELECT * FROM users WHERE email = $1', [email])",
                            },
                        ],
                        "summary": "Critical SQL injection. Single-line change but cannot ship as-is.",
                    }
                ),
                "scoring_criteria": "Must flag SQL injection as critical/reject, provide parameterized fix.",
            },
            {
                "input_text": "Review this React component:\n```tsx\nfunction UserList() {\n  const [users, setUsers] = useState([]);\n  useEffect(() => {\n    fetch('/api/users').then(r => r.json()).then(setUsers);\n  });\n  return <ul>{users.map(u => <li>{u.name}</li>)}</ul>;\n}\n```",
                "expected_output": json.dumps(
                    {
                        "language": "typescript",
                        "overall_verdict": "request_changes",
                        "score": 4,
                        "findings": [
                            {
                                "severity": "high",
                                "category": "correctness",
                                "line": 4,
                                "description": "useEffect missing dependency array — infinite fetch loop",
                                "fix": "Add empty array: useEffect(() => {...}, [])",
                            },
                            {
                                "severity": "medium",
                                "category": "correctness",
                                "line": 6,
                                "description": "Missing key prop on list items",
                                "fix": "Add key={u.id} to <li>",
                            },
                            {
                                "severity": "low",
                                "category": "correctness",
                                "line": 4,
                                "description": "No error handling on fetch",
                                "fix": "Add .catch(console.error) or error state",
                            },
                        ],
                        "summary": "Infinite loop bug is critical for production. Easy fixes.",
                    }
                ),
                "scoring_criteria": "Must identify infinite loop (missing deps), key prop warning, and error handling.",
            },
            {
                "input_text": "Review:\n```python\ndef process_batch(items: list) -> list:\n    return [transform(item) for item in items if item is not None]\n```",
                "expected_output": json.dumps(
                    {
                        "language": "python",
                        "overall_verdict": "approve",
                        "score": 8,
                        "findings": [
                            {
                                "severity": "info",
                                "category": "readability",
                                "line": 1,
                                "description": "Generic type hint — consider list[Item] if Item type is known",
                                "fix": "def process_batch(items: list[Item]) -> list[TransformedItem]:",
                            },
                        ],
                        "summary": "Clean, idiomatic Python. Minor type hint improvement possible.",
                    }
                ),
                "scoring_criteria": "Should approve with high score. May note type hint specificity. Should not flag false positives.",
            },
        ],
    },
    "Meeting Summarizer": {
        "name": "Meeting Summarizer — Accuracy & Completeness",
        "description": "Tests action item extraction, decision capture, and summary quality",
        "items": [
            {
                "input_text": "Transcript: 'Alice: Let's ship the new dashboard by end of month. Bob: I'll need the designs from Carol first — Carol can you have those by Wednesday? Carol: Yes, Wednesday works. Alice: Great. Also, we need to decide on the auth approach — JWT or sessions? Bob: JWT, it's already in the codebase. Alice: Agreed, JWT it is. Any blockers? Bob: None from me. Carol: I need access to Figma — Alice can you grant that? Alice: Will do today.'",
                "expected_output": json.dumps(
                    {
                        "meeting_title": "Product sync",
                        "date": "unknown",
                        "participants": ["Alice", "Bob", "Carol"],
                        "summary": [
                            "Dashboard launch targeted for end of month",
                            "JWT chosen as auth approach (already in codebase)",
                            "Design dependency on Carol blocks Bob's work",
                        ],
                        "decisions": [{"decision": "Use JWT for authentication", "rationale": "Already implemented in codebase"}],
                        "action_items": [
                            {"task": "Deliver dashboard designs", "owner": "Carol", "deadline": "Wednesday", "priority": "P1"},
                            {"task": "Grant Figma access to Carol", "owner": "Alice", "deadline": "today", "priority": "P2"},
                            {"task": "Build dashboard", "owner": "Bob", "deadline": "end of month", "priority": "P1"},
                        ],
                        "open_questions": [],
                        "follow_up_date": None,
                    }
                ),
                "scoring_criteria": "Must extract all 3 action items with correct owners and deadlines. Must capture JWT decision with rationale. Summary must be concise.",
            },
            {
                "input_text": "Meeting notes: Engineering retrospective. Issues raised: CI pipeline taking 45 min (target: 15 min). Dave volunteers to investigate. No decision on whether to split monorepo yet — needs data. Sarah to pull test coverage report by Thursday. Team agrees to weekly 30-min retros going forward.",
                "expected_output": json.dumps(
                    {
                        "meeting_title": "Engineering retrospective",
                        "date": "unknown",
                        "participants": ["Dave", "Sarah"],
                        "summary": [
                            "CI pipeline at 45 min — 3x over target",
                            "Monorepo split decision deferred pending data",
                            "Weekly retros established as recurring cadence",
                        ],
                        "decisions": [{"decision": "Hold weekly 30-min retros", "rationale": "Team alignment on process improvement"}],
                        "action_items": [
                            {"task": "Investigate CI pipeline performance", "owner": "Dave", "deadline": "unspecified", "priority": "P2"},
                            {"task": "Pull test coverage report", "owner": "Sarah", "deadline": "Thursday", "priority": "P2"},
                        ],
                        "open_questions": ["Should the monorepo be split?"],
                        "follow_up_date": None,
                    }
                ),
                "scoring_criteria": "Must capture both action items with correct owners. Must list monorepo as open question. Must note the 3x CI gap as key metric.",
            },
        ],
    },
    "Bug Triage Assistant": {
        "name": "Bug Triage Assistant — Severity & Root Cause",
        "description": "Tests bug reproduction, severity classification, and fix suggestion quality",
        "items": [
            {
                "input_text": "Bug report: 'Users cannot log in since the deployment at 14:00 UTC. Login form returns 500 error. Affects all users. Error in logs: KeyError: JWT_SECRET in settings.'",
                "expected_output": json.dumps(
                    {
                        "title": "Login broken — missing JWT_SECRET env var post-deployment",
                        "severity": "P0",
                        "confirmed": True,
                        "reproduction_steps": [
                            "Deploy without JWT_SECRET environment variable",
                            "Attempt login — POST /api/auth/login",
                            "Observe 500 response with KeyError in logs",
                        ],
                        "root_cause": "JWT_SECRET not set in production environment after deployment. Settings loader raises KeyError on missing required variable.",
                        "affected_components": ["auth service", "login endpoint", "settings loader"],
                        "fix_approach": "1. Immediately: set JWT_SECRET in production env vars and redeploy. 2. Preventive: add startup health check that validates all required env vars and fails fast.",
                        "estimated_effort": "15 minutes (env fix) + 1 hour (health check)",
                        "related_bugs": [],
                    }
                ),
                "scoring_criteria": "Must classify as P0, identify root cause as missing env var, provide both immediate fix and preventive measure.",
            },
            {
                "input_text": "Bug: 'Dashboard loads slowly — takes 12-15 seconds. SQL query in profiler shows N+1: fetching agent details one by one in a loop. 50 agents = 50 queries.'",
                "expected_output": json.dumps(
                    {
                        "title": "Dashboard N+1 query — O(n) DB calls for agent list",
                        "severity": "P2",
                        "confirmed": True,
                        "reproduction_steps": [
                            "Create workspace with 50+ agents",
                            "Load /dashboard",
                            "Observe 12-15s load time",
                            "Check SQL profiler: 50+ individual SELECT queries for agents",
                        ],
                        "root_cause": "N+1 query pattern: outer query fetches agent IDs, then individual queries fetch each agent's details in a loop.",
                        "affected_components": ["dashboard endpoint", "agent repository", "database"],
                        "fix_approach": "Replace loop queries with JOIN or IN clause: 'SELECT * FROM agents WHERE id IN (SELECT agent_id FROM ...) LEFT JOIN agent_stats...'",
                        "estimated_effort": "2-3 hours",
                        "related_bugs": [],
                    }
                ),
                "scoring_criteria": "Must identify as N+1 pattern, classify as P2, provide JOIN-based SQL fix, note O(n) complexity.",
            },
            {
                "input_text": "Bug: 'Export button on reports page does nothing when clicked. Console shows: TypeError: Cannot read property \"data\" of undefined at ExportButton.tsx:42'",
                "expected_output": json.dumps(
                    {
                        "title": "Export button crash — undefined data prop",
                        "severity": "P3",
                        "confirmed": True,
                        "reproduction_steps": [
                            "Navigate to reports page",
                            "Click export button before data has loaded",
                            "Observe TypeError in console",
                        ],
                        "root_cause": "ExportButton accesses `props.data.items` before data fetch completes. Component doesn't guard against undefined data state.",
                        "affected_components": ["ExportButton component", "reports page"],
                        "fix_approach": "Add null check: `if (!data?.items) return;` at line 42. Consider disabling button until data is available.",
                        "estimated_effort": "30 minutes",
                        "related_bugs": [],
                    }
                ),
                "scoring_criteria": "Must classify as P3 (UI only, non-critical), identify undefined prop access as root cause, provide optional chaining or null guard fix.",
            },
        ],
    },
    "Content Strategist": {
        "name": "Content Strategist — Brief Quality & SEO Thinking",
        "description": "Tests competitor gap analysis, keyword strategy, and content brief quality",
        "items": [
            {
                "input_text": "Create a content brief for: 'best practices for RAG systems in production'",
                "expected_output": json.dumps(
                    {
                        "topic": "RAG systems in production",
                        "target_keyword": "RAG production best practices",
                        "search_intent": "informational",
                        "competitor_analysis": [
                            {
                                "url": "competitor-1.com",
                                "strengths": ["Comprehensive overview"],
                                "gaps": ["No performance benchmarks", "No failure mode coverage"],
                            },
                        ],
                        "content_brief": {
                            "title": "RAG in Production: 10 Best Practices from Teams at Scale",
                            "outline": [
                                "Chunking strategy",
                                "Embedding model selection",
                                "Re-ranking",
                                "Evaluation/evals",
                                "Monitoring in production",
                                "Cost optimization",
                            ],
                            "word_count_target": 3500,
                            "key_points": ["Concrete benchmarks", "Failure mode catalog", "Real production learnings, not toy examples"],
                            "cta": "Download our RAG evaluation template",
                        },
                        "differentiation_angle": "Focus on failure modes and monitoring — most content covers happy path only",
                    }
                ),
                "scoring_criteria": "Must identify specific content gaps in competitors, provide structured outline with real sections (not generic), differentiation angle must be specific.",
            },
            {
                "input_text": "Content brief for: 'AI agents for enterprise — buyer's guide'",
                "expected_output": json.dumps(
                    {
                        "topic": "AI agents for enterprise",
                        "target_keyword": "enterprise AI agents buyer guide",
                        "search_intent": "commercial",
                        "competitor_analysis": [
                            {"url": "g2.com-like", "strengths": ["Feature comparisons"], "gaps": ["No TCO analysis", "No integration complexity"]},
                        ],
                        "content_brief": {
                            "title": "Enterprise AI Agents: The 2026 Buyer's Guide (With TCO Analysis)",
                            "outline": [
                                "What to evaluate (security, compliance, integration)",
                                "Build vs buy",
                                "TCO framework",
                                "Vendor comparison matrix",
                                "Implementation pitfalls",
                            ],
                            "word_count_target": 4000,
                            "key_points": ["Security/compliance requirements", "Total cost of ownership", "Integration complexity"],
                            "cta": "Book a demo to see how Flow handles enterprise workflows",
                        },
                        "differentiation_angle": "TCO and integration complexity — buyers don't find this anywhere else",
                    }
                ),
                "scoring_criteria": "Must identify commercial search intent, include TCO as differentiator, provide enterprise-specific outline sections (compliance, security), not generic.",
            },
        ],
    },
    "Data Analyst": {
        "name": "Data Analyst — Code Execution & Insight Quality",
        "description": "Tests statistical analysis, Python execution, and insight generation",
        "items": [
            {
                "input_text": "Analyze this dataset and find trends:\n```\nmonth,revenue,users\nJan,12000,450\nFeb,13500,480\nMar,11000,420\nApr,15000,520\nMay,16500,560\nJun,14000,490\n```",
                "expected_output": json.dumps(
                    {
                        "task": "Revenue and user trend analysis",
                        "code_executed": "import pandas as pd\ndf = pd.read_csv(...)\ndf['revenue_per_user'] = df['revenue'] / df['users']",
                        "key_metrics": {"avg_revenue": 13666.7, "revenue_growth_pct": 16.7, "avg_users": 486.7, "revenue_per_user_avg": 28.1},
                        "insights": [
                            "Revenue grew 37.5% from Jan to May, outpacing user growth (24.4%)",
                            "March shows a dip — investigate cause (seasonal? one-off event?)",
                            "Revenue per user trend is positive: monetization improving",
                        ],
                        "anomalies": ["March dip interrupts otherwise positive trend"],
                        "recommendations": [
                            "Investigate March dip — if seasonal, adjust forecasts",
                            "June slowdown may signal market saturation — monitor July closely",
                        ],
                        "confidence": 0.78,
                    }
                ),
                "scoring_criteria": "Must compute at least 3 metrics, identify the March anomaly, provide business-relevant recommendations.",
            },
            {
                "input_text": "Analyze model training loss:\n```\nepoch,train_loss,val_loss\n1,2.45,2.67\n2,1.89,2.12\n3,1.45,1.78\n4,1.12,1.52\n5,0.89,1.48\n6,0.72,1.61\n7,0.61,1.87\n```",
                "expected_output": json.dumps(
                    {
                        "task": "Training dynamics analysis",
                        "code_executed": "...",
                        "key_metrics": {"best_val_loss": 1.48, "best_epoch": 5, "train_val_gap_epoch7": 1.26},
                        "insights": [
                            "Model converges well through epoch 5",
                            "Validation loss diverges from epoch 6 — clear overfitting signal",
                            "Train/val gap widens 3x from epoch 5 to 7",
                        ],
                        "anomalies": ["Overfitting onset at epoch 6"],
                        "recommendations": [
                            "Use checkpoint from epoch 5 for inference",
                            "Add dropout or weight decay to delay overfitting",
                            "Consider early stopping at val_loss increase of >5%",
                        ],
                        "confidence": 0.92,
                    }
                ),
                "scoring_criteria": "Must identify overfitting at epoch 6, recommend epoch 5 checkpoint, suggest regularization.",
            },
            {
                "input_text": "Analyze A/B test results:\n```\ngroup,conversions,total\ncontrol,234,1200\ntreatment,278,1180\n```",
                "expected_output": json.dumps(
                    {
                        "task": "A/B test statistical significance analysis",
                        "code_executed": "from scipy.stats import chi2_contingency\n...",
                        "key_metrics": {"control_rate": 0.195, "treatment_rate": 0.2356, "lift_pct": 20.8, "p_value": 0.032},
                        "insights": [
                            "Treatment conversion rate is 23.6% vs 19.5% control — 20.8% relative lift",
                            "Chi-square test p=0.032 < 0.05 — statistically significant at 95% confidence",
                            "Sample size sufficient for reliable conclusion",
                        ],
                        "anomalies": [],
                        "recommendations": [
                            "Ship treatment variant — result is statistically significant",
                            "Monitor for Simpson's paradox across user segments before full rollout",
                        ],
                        "confidence": 0.91,
                    }
                ),
                "scoring_criteria": "Must run chi-square or z-test, compute lift correctly (~20%), confirm statistical significance, recommend shipping.",
            },
            {
                "input_text": "Quick stats on: [23, 45, 12, 67, 34, 89, 23, 45, 56, 78, 34, 12, 90, 45, 67]",
                "expected_output": json.dumps(
                    {
                        "task": "Descriptive statistics",
                        "code_executed": "import numpy as np\ndata = [...]\nstats = {'mean': np.mean(data), 'median': np.median(data), ...}",
                        "key_metrics": {"mean": 48.0, "median": 45.0, "std": 24.8, "min": 12, "max": 90, "q25": 27.5, "q75": 67.0},
                        "insights": [
                            "Mean (~48) close to median (45) — roughly symmetric distribution",
                            "High std (24.8) relative to mean indicates high spread",
                            "Range 12–90 with no obvious outliers",
                        ],
                        "anomalies": [],
                        "recommendations": ["Distribution appears roughly normal — parametric tests applicable"],
                        "confidence": 0.95,
                    }
                ),
                "scoring_criteria": "Must compute mean, median, std, quartiles correctly. Must note the mean≈median symmetry.",
            },
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Main seeding function
# ──────────────────────────────────────────────────────────────────────────────


async def seed_workspace(pool: asyncpg.Pool, workspace_id: uuid.UUID, *, prune: bool = False) -> None:
    logger.info("seeding", workspace_id=str(workspace_id), prune=prune)

    # DESTRUCTIVE: only when --prune is passed (used by make rebuild).
    # By default we only upsert canonical agents — no user data is touched.
    if prune:
        stale_ids = await pool.fetch(
            "SELECT id FROM agents WHERE workspace_id = $1 AND name != ALL($2::text[])",
            workspace_id,
            CANONICAL_AGENT_NAMES,
        )
        # ab_tests reference agents without ON DELETE CASCADE, clear first
        await pool.execute("DELETE FROM ab_tests WHERE workspace_id = $1", workspace_id)

        if stale_ids:
            ids = [r["id"] for r in stale_ids]
            candidate_tables = [
                "agent_skills",
                "agent_memories",
                "episodic_memories",
                "agent_negatives",
                "reasoning_patterns",
                "agent_schedules",
                "agent_versions",
                "golden_results",
            ]
            existing_rows = await pool.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ANY($1::text[])",
                candidate_tables,
            )
            existing_tables = {r["table_name"] for r in existing_rows}
            for tbl in candidate_tables:
                if tbl not in existing_tables:
                    continue
                await pool.execute(f"DELETE FROM {tbl} WHERE agent_id = ANY($1)", ids)
            await pool.execute("DELETE FROM executions WHERE agent_id = ANY($1)", ids)
            await pool.execute("DELETE FROM agents WHERE id = ANY($1)", ids)
            logger.info("cleanup.old_agents", count=len(ids), names=CANONICAL_AGENT_NAMES)

    seeded_agents: dict[str, uuid.UUID] = {}

    for agent_def in AGENTS:
        existing = await pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 AND name = $2",
            workspace_id,
            agent_def["name"],
        )
        if existing:
            agent_id = existing["id"]
            await pool.execute(
                "UPDATE agents SET config = $1, template = $2 WHERE id = $3",
                json.dumps(agent_def["config"]),
                agent_def["template"],
                agent_id,
            )
            logger.info("agent.updated", name=agent_def["name"])
        else:
            agent_id = uuid.uuid4()
            await pool.execute(
                "INSERT INTO agents (id, workspace_id, name, template, config) VALUES ($1, $2, $3, $4, $5)",
                agent_id,
                workspace_id,
                agent_def["name"],
                agent_def["template"],
                json.dumps(agent_def["config"]),
            )
            logger.info("agent.created", name=agent_def["name"])

        seeded_agents[agent_def["name"]] = agent_id

    for agent_name, gs_def in GOLDEN_SETS.items():
        agent_id = seeded_agents.get(agent_name)
        if not agent_id:
            continue

        existing_set = await pool.fetchrow(
            "SELECT id FROM golden_sets WHERE workspace_id = $1 AND name = $2",
            workspace_id,
            gs_def["name"],
        )
        if existing_set:
            set_id = existing_set["id"]
            logger.info("golden_set.exists", name=gs_def["name"])
        else:
            set_id = uuid.uuid4()
            await pool.execute(
                "INSERT INTO golden_sets (id, workspace_id, name, description) VALUES ($1, $2, $3, $4)",
                set_id,
                workspace_id,
                gs_def["name"],
                gs_def["description"],
            )
            logger.info("golden_set.created", name=gs_def["name"], items=len(gs_def["items"]))

            for item in gs_def["items"]:
                item_id = uuid.uuid4()
                await pool.execute(
                    "INSERT INTO golden_items (id, set_id, input_text, expected_output, scoring_criteria) VALUES ($1, $2, $3, $4, $5)",
                    item_id,
                    set_id,
                    item["input_text"],
                    item["expected_output"],
                    item["scoring_criteria"],
                )

    logger.info("seed.done", agents=len(seeded_agents), golden_sets=len(GOLDEN_SETS))


async def seed(pool: asyncpg.Pool, *, prune: bool = False) -> None:
    workspaces = await pool.fetch("SELECT id FROM workspaces")
    if not workspaces:
        logger.error("no_workspace", message="No workspace found. Run migrations and create a user first.")
        return
    for ws in workspaces:
        await seed_workspace(pool, ws["id"], prune=prune)


async def main() -> None:
    import os
    import sys

    configure_logging(level="INFO", json_output=False, force_colors=True, service="seed")
    # --prune CLI flag OR SEED_PRUNE=1 env var enables destructive cleanup
    prune = "--prune" in sys.argv or os.environ.get("SEED_PRUNE") == "1"
    if prune:
        logger.info("seed.mode", mode="prune (destructive — removes non-canonical agents)")
    else:
        logger.info("seed.mode", mode="upsert-only (safe, no data deletion)")
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        await seed(pool, prune=prune)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
