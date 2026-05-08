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

AGENTS = [
    {
        "name": "Research Analyst",
        "template": "deer_flow",
        "config": {
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
        "name": "Daily AI Briefing",
        "template": "linear-3",
        "config": {
            "system_prompt": (
                "You are the Daily AI Briefing Agent. Every morning you:\n"
                "1. Pull trending papers from HuggingFace Daily Papers.\n"
                "2. Search for AI/ML news from the last 24h via Tavily.\n"
                "3. Synthesize into a digestible briefing: Top 3 papers, Top 3 news items, "
                "   one 'Signal of the Day' insight, and a short trend analysis.\n"
                "Keep the tone professional but accessible. Use concrete numbers.\n"
                "Output format: {date, papers: [{title, one_liner, why_it_matters}], "
                "news: [{headline, source, summary}], signal_of_the_day, trend_analysis}"
            ),
            "tools": {
                "retrieve": False,
                "sandbox": False,
                "long_term_memory": True,
                "tavily_search": True,
                "fetch_webpage": True,
                "arxiv_search": False,
                "hf_papers": True,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.4},
            "state_schema": {
                "description": "BriefingState TypedDict",
                "fields": {
                    "date": "str",
                    "hf_papers": "list[dict]",
                    "news_items": "list[dict]",
                    "draft_briefing": "str | None",
                    "final_briefing": "Briefing | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "Briefing",
                "fields": {
                    "date": "str",
                    "papers": "list[PaperHighlight]",
                    "news": "list[NewsItem]",
                    "signal_of_the_day": "str",
                    "trend_analysis": "str",
                },
            },
        },
    },
    {
        "name": "Knowledge Curator",
        "template": "deer_flow",
        "config": {
            "system_prompt": (
                "You are a Knowledge Curator specialized in building and maintaining knowledge graphs. "
                "When given a topic or document:\n"
                "1. Retrieve relevant existing knowledge from the RAG store.\n"
                "2. Extract entities, relationships, and key facts.\n"
                "3. Identify gaps in existing knowledge and suggest what to add.\n"
                "4. Store structured summaries in long-term memory.\n"
                "5. Return a curation report with extracted knowledge and update recommendations.\n"
                "Output: {topic, entities: [{name, type, properties}], "
                "relationships: [{source, relation, target}], gaps: [str], "
                "memory_updates: [{key, value}], summary}"
            ),
            "tools": {
                "retrieve": True,
                "sandbox": False,
                "long_term_memory": True,
                "tavily_search": True,
                "fetch_webpage": True,
                "arxiv_search": False,
                "hf_papers": False,
            },
            "llm_config": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.3},
            "state_schema": {
                "description": "CurationState TypedDict",
                "fields": {
                    "topic": "str",
                    "retrieved_docs": "list[dict]",
                    "extracted_entities": "list[Entity]",
                    "extracted_relations": "list[Relation]",
                    "knowledge_gaps": "list[str]",
                    "curation_report": "CurationReport | None",
                    "messages": "list[BaseMessage]",
                },
            },
            "output_schema": {
                "name": "CurationReport",
                "fields": {
                    "topic": "str",
                    "entities": "list[Entity]",
                    "relationships": "list[Relation]",
                    "gaps": "list[str]",
                    "memory_updates": "list[dict]",
                    "summary": "str",
                },
            },
        },
    },
    {
        "name": "Data Analyst",
        "template": "tool-agent",
        "config": {
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
                "expected_output": json.dumps({
                    "title": "Advances in Retrieval-Augmented Generation",
                    "summary": "Recent work improves RAG via better chunking, hybrid retrieval, and re-ranking.",
                    "key_findings": [{"claim": "Contextual chunking outperforms fixed-size chunking", "source": "arXiv", "confidence": 0.9}],
                    "limitations": ["Most studies use synthetic benchmarks"],
                    "conclusion": "RAG is maturing rapidly with clear improvement vectors",
                    "recommended_reading": ["arXiv:2312.10997"],
                }),
                "scoring_criteria": "Report must include: (1) at least 2 cited sources, (2) structured findings with confidence scores, (3) identified limitations, (4) concrete conclusion. Score 0-10.",
            },
            {
                "input_text": "Summarize recent research on LLM alignment and safety techniques.",
                "expected_output": json.dumps({
                    "title": "LLM Alignment and Safety: 2024-2025 Landscape",
                    "summary": "RLHF, Constitutional AI, and DPO remain dominant. New work explores scalable oversight.",
                    "key_findings": [
                        {"claim": "DPO trains faster than PPO-based RLHF with comparable results", "source": "arXiv", "confidence": 0.85},
                        {"claim": "Scalable oversight via debate shows promise for superhuman tasks", "source": "Anthropic/OpenAI papers", "confidence": 0.75},
                    ],
                    "limitations": ["Alignment metrics lack standardization"],
                    "conclusion": "No silver bullet; ensemble approaches may be necessary",
                    "recommended_reading": ["Constitutional AI paper", "DPO paper"],
                }),
                "scoring_criteria": "Must cover RLHF/DPO/Constitutional AI, cite specific techniques, acknowledge open problems.",
            },
            {
                "input_text": "What does recent research say about transformer scaling laws?",
                "expected_output": json.dumps({
                    "title": "Transformer Scaling Laws: Recent Findings",
                    "summary": "Chinchilla scaling laws revised compute-optimal training. Recent work questions power-law assumptions.",
                    "key_findings": [
                        {"claim": "Chinchilla-optimal models are undertrained by common practice", "source": "DeepMind", "confidence": 0.95},
                        {"claim": "Data quality matters as much as quantity at scale", "source": "Multiple sources", "confidence": 0.8},
                    ],
                    "limitations": ["Scaling laws may not generalize across modalities"],
                    "conclusion": "Compute-optimal training requires more tokens than previously thought",
                    "recommended_reading": ["Chinchilla paper", "Scaling Data-Constrained Language Models"],
                }),
                "scoring_criteria": "Must reference Chinchilla, explain compute-optimal training, note recent challenges.",
            },
            {
                "input_text": "Analyze research on multimodal language models — what architectures dominate?",
                "expected_output": json.dumps({
                    "title": "Multimodal LLM Architectures: State of the Art",
                    "summary": "Decoder-only transformers with vision encoders (CLIP-style) dominate. MoE variants gaining traction.",
                    "key_findings": [
                        {"claim": "Late fusion (vision encoder → projection → LLM) is the dominant pattern", "source": "Survey papers", "confidence": 0.9},
                        {"claim": "Native multimodal training (Chameleon-style) shows promise", "source": "Meta AI", "confidence": 0.7},
                    ],
                    "limitations": ["Video understanding remains a hard problem"],
                    "conclusion": "CLIP + LLM fusion is battle-tested; native multimodal is the next frontier",
                    "recommended_reading": ["LLaVA", "Flamingo", "GPT-4V technical report"],
                }),
                "scoring_criteria": "Must name specific architectures, compare approaches, identify dominant patterns.",
            },
            {
                "input_text": "What are current challenges in neural network interpretability?",
                "expected_output": json.dumps({
                    "title": "Neural Network Interpretability: Open Challenges",
                    "summary": "Mechanistic interpretability advances but lacks scalability. Feature attribution remains disputed.",
                    "key_findings": [
                        {"claim": "Superposition makes individual neuron analysis unreliable", "source": "Anthropic", "confidence": 0.88},
                        {"claim": "Circuits-based analysis scales poorly to full models", "source": "Multiple labs", "confidence": 0.8},
                    ],
                    "limitations": ["Ground truth for interpretability is hard to define"],
                    "conclusion": "The field needs standardized benchmarks and more scalable methods",
                    "recommended_reading": ["Toy Models of Superposition", "In-context Learning and Induction Heads"],
                }),
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
                "expected_output": json.dumps({
                    "language": "python",
                    "overall_verdict": "request_changes",
                    "score": 2,
                    "findings": [
                        {"severity": "critical", "category": "security", "line": 4, "description": "SQL injection vulnerability via f-string interpolation", "fix": "Use parameterized query: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"},
                        {"severity": "high", "category": "correctness", "line": 2, "description": "Connection never closed — resource leak", "fix": "Use context manager: with sqlite3.connect('app.db') as conn:"},
                    ],
                    "summary": "Critical SQL injection and resource leak. Must fix before any use.",
                }),
                "scoring_criteria": "Must identify SQL injection as critical, note connection leak, provide parameterized query fix.",
            },
            {
                "input_text": "Review this async Python:\n```python\nimport asyncio\nasync def fetch_all(urls):\n    results = []\n    for url in urls:\n        r = await fetch(url)\n        results.append(r)\n    return results\n```",
                "expected_output": json.dumps({
                    "language": "python",
                    "overall_verdict": "request_changes",
                    "score": 5,
                    "findings": [
                        {"severity": "medium", "category": "performance", "line": 4, "description": "Sequential awaiting negates async benefits — O(n) latency", "fix": "Use asyncio.gather(*[fetch(url) for url in urls])"},
                        {"severity": "low", "category": "correctness", "line": None, "description": "No error handling — one failed fetch crashes all", "fix": "Use return_exceptions=True in gather or try/except per fetch"},
                    ],
                    "summary": "Works but misses core async benefit. Use gather() for concurrent execution.",
                }),
                "scoring_criteria": "Must identify sequential await issue, suggest asyncio.gather, note missing error handling.",
            },
            {
                "input_text": "Review:\n```typescript\nconst users = await db.query(`SELECT * FROM users WHERE email = '${email}'`);\n```",
                "expected_output": json.dumps({
                    "language": "typescript",
                    "overall_verdict": "reject",
                    "score": 1,
                    "findings": [
                        {"severity": "critical", "category": "security", "line": 1, "description": "SQL injection via template literal interpolation", "fix": "Use parameterized query: db.query('SELECT * FROM users WHERE email = $1', [email])"},
                    ],
                    "summary": "Critical SQL injection. Single-line change but cannot ship as-is.",
                }),
                "scoring_criteria": "Must flag SQL injection as critical/reject, provide parameterized fix.",
            },
            {
                "input_text": "Review this React component:\n```tsx\nfunction UserList() {\n  const [users, setUsers] = useState([]);\n  useEffect(() => {\n    fetch('/api/users').then(r => r.json()).then(setUsers);\n  });\n  return <ul>{users.map(u => <li>{u.name}</li>)}</ul>;\n}\n```",
                "expected_output": json.dumps({
                    "language": "typescript",
                    "overall_verdict": "request_changes",
                    "score": 4,
                    "findings": [
                        {"severity": "high", "category": "correctness", "line": 4, "description": "useEffect missing dependency array — infinite fetch loop", "fix": "Add empty array: useEffect(() => {...}, [])"},
                        {"severity": "medium", "category": "correctness", "line": 6, "description": "Missing key prop on list items", "fix": "Add key={u.id} to <li>"},
                        {"severity": "low", "category": "correctness", "line": 4, "description": "No error handling on fetch", "fix": "Add .catch(console.error) or error state"},
                    ],
                    "summary": "Infinite loop bug is critical for production. Easy fixes.",
                }),
                "scoring_criteria": "Must identify infinite loop (missing deps), key prop warning, and error handling.",
            },
            {
                "input_text": "Review:\n```python\ndef process_batch(items: list) -> list:\n    return [transform(item) for item in items if item is not None]\n```",
                "expected_output": json.dumps({
                    "language": "python",
                    "overall_verdict": "approve",
                    "score": 8,
                    "findings": [
                        {"severity": "info", "category": "readability", "line": 1, "description": "Generic type hint — consider list[Item] if Item type is known", "fix": "def process_batch(items: list[Item]) -> list[TransformedItem]:"},
                    ],
                    "summary": "Clean, idiomatic Python. Minor type hint improvement possible.",
                }),
                "scoring_criteria": "Should approve with high score. May note type hint specificity. Should not flag false positives.",
            },
        ],
    },
    "Daily AI Briefing": {
        "name": "Daily AI Briefing — Quality & Coverage",
        "description": "Tests briefing completeness, accuracy, and appropriate depth",
        "items": [
            {
                "input_text": "Generate today's AI briefing. Focus on language models and reasoning.",
                "expected_output": json.dumps({
                    "date": "2026-05-08",
                    "papers": [
                        {"title": "Chain-of-Thought Prompting Elicits Reasoning in LLMs", "one_liner": "Step-by-step prompting enables complex reasoning in large models", "why_it_matters": "Directly applicable to production prompting strategies"},
                    ],
                    "news": [
                        {"headline": "Anthropic releases Claude 4 family", "source": "Anthropic", "summary": "New models with improved reasoning and safety"},
                    ],
                    "signal_of_the_day": "Reasoning is the new benchmark battleground — test-time compute is winning",
                    "trend_analysis": "The field is converging on inference-time scaling as the next frontier after pretraining.",
                }),
                "scoring_criteria": "Must include at least 2 papers, 2 news items, a signal of the day, and trend analysis. Content must be substantive and specific.",
            },
            {
                "input_text": "Briefing on multimodal AI developments.",
                "expected_output": json.dumps({
                    "date": "2026-05-08",
                    "papers": [
                        {"title": "Vision-Language Models for Medical Imaging", "one_liner": "VLMs outperform specialist models on radiology tasks", "why_it_matters": "High-stakes domain validation of multimodal AI"},
                    ],
                    "news": [{"headline": "Google Gemini Ultra 2.0 vision benchmarks", "source": "Google AI", "summary": "State-of-art on multimodal reasoning tasks"}],
                    "signal_of_the_day": "Video understanding remains the last hard multimodal frontier",
                    "trend_analysis": "Vision encoders are commoditizing; differentiation moves to reasoning over visual content.",
                }),
                "scoring_criteria": "Must reference specific multimodal papers or models. Signal must relate to the theme. Trend must be specific and actionable.",
            },
            {
                "input_text": "What's happening in AI agents and tool use today?",
                "expected_output": json.dumps({
                    "date": "2026-05-08",
                    "papers": [
                        {"title": "LangGraph: Stateful Multi-Actor Applications with LLMs", "one_liner": "Graph-based framework for production agentic workflows", "why_it_matters": "Used by thousands of production deployments"},
                    ],
                    "news": [{"headline": "OpenAI launches Operator for browser automation", "source": "OpenAI", "summary": "First-party agent product with real-world task completion"}],
                    "signal_of_the_day": "Agent reliability (not capability) is the bottleneck to enterprise adoption",
                    "trend_analysis": "The agent tooling ecosystem is consolidating around LangGraph and CrewAI patterns.",
                }),
                "scoring_criteria": "Must cover agentic frameworks and real deployments. Signal must be practically relevant.",
            },
        ],
    },
    "Knowledge Curator": {
        "name": "Knowledge Curator — Extraction & Structuring",
        "description": "Tests ability to extract entities, relationships, and identify knowledge gaps",
        "items": [
            {
                "input_text": "Curate knowledge about: 'The attention mechanism in transformers and its variants (MHA, GQA, MLA)'",
                "expected_output": json.dumps({
                    "topic": "Attention mechanisms in transformers",
                    "entities": [
                        {"name": "Multi-Head Attention", "type": "algorithm", "properties": {"paper": "Attention Is All You Need", "year": 2017}},
                        {"name": "Grouped-Query Attention", "type": "algorithm", "properties": {"benefit": "KV cache reduction", "used_in": "Llama 2+"}},
                        {"name": "Multi-Head Latent Attention", "type": "algorithm", "properties": {"benefit": "Lower memory with lossless compression", "used_in": "DeepSeek"}},
                    ],
                    "relationships": [
                        {"source": "Grouped-Query Attention", "relation": "improves_efficiency_of", "target": "Multi-Head Attention"},
                        {"source": "Multi-Head Latent Attention", "relation": "extends", "target": "Grouped-Query Attention"},
                    ],
                    "gaps": ["Comparison of wall-clock performance", "Benchmarks on long-context tasks"],
                    "memory_updates": [{"key": "attention_variants_2025", "value": "MHA→GQA→MLA evolution for KV cache efficiency"}],
                    "summary": "Three generations of attention with clear efficiency improvements.",
                }),
                "scoring_criteria": "Must extract at least 3 entities with properties, 2 relationships with typed edges, and identify at least 1 knowledge gap.",
            },
            {
                "input_text": "Curate knowledge about: 'Vector databases — Pinecone, Weaviate, Qdrant, pgvector'",
                "expected_output": json.dumps({
                    "topic": "Vector databases",
                    "entities": [
                        {"name": "Pinecone", "type": "product", "properties": {"type": "managed", "use_case": "enterprise RAG"}},
                        {"name": "Weaviate", "type": "product", "properties": {"type": "open-source/managed", "feature": "hybrid search"}},
                        {"name": "Qdrant", "type": "product", "properties": {"type": "open-source", "language": "Rust", "feature": "fast filtering"}},
                        {"name": "pgvector", "type": "extension", "properties": {"type": "PostgreSQL extension", "advantage": "no new infra"}},
                    ],
                    "relationships": [
                        {"source": "pgvector", "relation": "integrates_with", "target": "PostgreSQL"},
                        {"source": "Pinecone", "relation": "competes_with", "target": "Weaviate"},
                    ],
                    "gaps": ["Benchmark comparisons at 100M+ vectors", "Cost comparison at scale"],
                    "memory_updates": [{"key": "vector_db_landscape_2025", "value": "Qdrant for OSS, pgvector for existing Postgres users, Pinecone for managed scale"}],
                    "summary": "Mature market with clear segmentation: managed vs OSS, specialized vs embedded.",
                }),
                "scoring_criteria": "Must extract all 4 databases as entities, show competitive/integration relationships, identify meaningful gaps.",
            },
            {
                "input_text": "Curate: 'Model Context Protocol (MCP) by Anthropic'",
                "expected_output": json.dumps({
                    "topic": "Model Context Protocol",
                    "entities": [
                        {"name": "MCP", "type": "protocol", "properties": {"creator": "Anthropic", "purpose": "standardized LLM-tool interface"}},
                        {"name": "MCP Server", "type": "component", "properties": {"role": "exposes tools/resources to LLM"}},
                        {"name": "MCP Client", "type": "component", "properties": {"role": "consumes MCP server capabilities"}},
                    ],
                    "relationships": [
                        {"source": "MCP Client", "relation": "connects_to", "target": "MCP Server"},
                        {"source": "MCP", "relation": "standardizes", "target": "LLM tool calling"},
                    ],
                    "gaps": ["Security model for untrusted MCP servers", "Rate limiting standards"],
                    "memory_updates": [{"key": "mcp_overview", "value": "Anthropic's open protocol for LLM-tool standardization, gaining adoption in Claude Code etc."}],
                    "summary": "Open protocol replacing ad-hoc tool integration with a standard interface.",
                }),
                "scoring_criteria": "Must identify MCP as a protocol, its components, key relationships, and practical gaps.",
            },
        ],
    },
    "Data Analyst": {
        "name": "Data Analyst — Code Execution & Insight Quality",
        "description": "Tests statistical analysis, Python execution, and insight generation",
        "items": [
            {
                "input_text": "Analyze this dataset and find trends:\n```\nmonth,revenue,users\nJan,12000,450\nFeb,13500,480\nMar,11000,420\nApr,15000,520\nMay,16500,560\nJun,14000,490\n```",
                "expected_output": json.dumps({
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
                }),
                "scoring_criteria": "Must compute at least 3 metrics, identify the March anomaly, provide business-relevant recommendations.",
            },
            {
                "input_text": "Analyze model training loss:\n```\nepoch,train_loss,val_loss\n1,2.45,2.67\n2,1.89,2.12\n3,1.45,1.78\n4,1.12,1.52\n5,0.89,1.48\n6,0.72,1.61\n7,0.61,1.87\n```",
                "expected_output": json.dumps({
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
                }),
                "scoring_criteria": "Must identify overfitting at epoch 6, recommend epoch 5 checkpoint, suggest regularization.",
            },
            {
                "input_text": "Analyze A/B test results:\n```\ngroup,conversions,total\ncontrol,234,1200\ntreatment,278,1180\n```",
                "expected_output": json.dumps({
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
                }),
                "scoring_criteria": "Must run chi-square or z-test, compute lift correctly (~20%), confirm statistical significance, recommend shipping.",
            },
            {
                "input_text": "Quick stats on: [23, 45, 12, 67, 34, 89, 23, 45, 56, 78, 34, 12, 90, 45, 67]",
                "expected_output": json.dumps({
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
                }),
                "scoring_criteria": "Must compute mean, median, std, quartiles correctly. Must note the mean≈median symmetry.",
            },
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Main seeding function
# ──────────────────────────────────────────────────────────────────────────────

async def seed(pool: asyncpg.Pool) -> None:
    workspace = await pool.fetchrow("SELECT id FROM workspaces LIMIT 1")
    if not workspace:
        logger.error("no_workspace", message="No workspace found. Run migrations and create a user first.")
        return
    workspace_id = workspace["id"]
    logger.info("seeding", workspace_id=str(workspace_id))

    seeded_agents: dict[str, uuid.UUID] = {}

    for agent_def in AGENTS:
        existing = await pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 AND name = $2",
            workspace_id, agent_def["name"],
        )
        if existing:
            agent_id = existing["id"]
            await pool.execute(
                "UPDATE agents SET config = $1, template = $2 WHERE id = $3",
                json.dumps(agent_def["config"]), agent_def["template"], agent_id,
            )
            logger.info("agent.updated", name=agent_def["name"])
        else:
            agent_id = uuid.uuid4()
            await pool.execute(
                "INSERT INTO agents (id, workspace_id, name, template, config) VALUES ($1, $2, $3, $4, $5)",
                agent_id, workspace_id, agent_def["name"],
                agent_def["template"], json.dumps(agent_def["config"]),
            )
            logger.info("agent.created", name=agent_def["name"])

        seeded_agents[agent_def["name"]] = agent_id

    for agent_name, gs_def in GOLDEN_SETS.items():
        agent_id = seeded_agents.get(agent_name)
        if not agent_id:
            continue

        existing_set = await pool.fetchrow(
            "SELECT id FROM golden_sets WHERE workspace_id = $1 AND name = $2",
            workspace_id, gs_def["name"],
        )
        if existing_set:
            set_id = existing_set["id"]
            logger.info("golden_set.exists", name=gs_def["name"])
        else:
            set_id = uuid.uuid4()
            await pool.execute(
                "INSERT INTO golden_sets (id, workspace_id, agent_id, name, description) VALUES ($1, $2, $3, $4, $5)",
                set_id, workspace_id, agent_id, gs_def["name"], gs_def["description"],
            )
            logger.info("golden_set.created", name=gs_def["name"], items=len(gs_def["items"]))

            for item in gs_def["items"]:
                item_id = uuid.uuid4()
                await pool.execute(
                    "INSERT INTO golden_items (id, set_id, input_text, expected_output, scoring_criteria) VALUES ($1, $2, $3, $4, $5)",
                    item_id, set_id,
                    item["input_text"], item["expected_output"], item["scoring_criteria"],
                )

    logger.info("seed.done", agents=len(seeded_agents), golden_sets=len(GOLDEN_SETS))


async def main() -> None:
    configure_logging(level="INFO", json_output=False, force_colors=True, service="seed")
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        await seed(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
