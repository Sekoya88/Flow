"""Static skill template library. Not pre-saved to DB — instantiated via UI or CLI."""

from __future__ import annotations

SKILL_TEMPLATES: list[dict] = [
    # ── Research ─────────────────────────────────────────────────
    {
        "name": "web-research",
        "category": "Research",
        "description": "Use this skill when the user asks to research a topic, find current information, or gather facts from the web.",
        "content_md": """\
---
name: web-research
description: Use this skill when the user asks to research a topic, find current information, or gather facts from the web.
version: "1.0"
category: Research
allowed-tools: tavily_search, fetch_webpage
triggers:
  - "research"
  - "find information about"
  - "search for"
  - "look up"
metadata:
  author: flow
---

# Web Research

<context>
Systematic web research using search and fetch to gather accurate, up-to-date information.
</context>

<instructions>
1. Identify the core research question from the user message
2. Formulate 2-3 targeted search queries covering different angles
3. Execute searches and retrieve top results
4. Fetch primary sources when more detail is needed
5. Synthesize findings into a coherent answer with citations
</instructions>

<output_format>
Summary paragraph followed by key findings as bullet points. Include source URLs for each fact.
</output_format>

<examples>
**Input:** What are the latest developments in quantum computing?
**Output:** Recent advances in quantum computing include... [summary]. Key findings: • Google achieved... [source] • IBM announced... [source]
</examples>
""",
    },
    {
        "name": "academic-search",
        "category": "Research",
        "description": "Use this skill when the user needs academic papers, citations, or scientific literature on a topic.",
        "content_md": """\
---
name: academic-search
description: Use this skill when the user needs academic papers, citations, or scientific literature on a topic.
version: "1.0"
category: Research
allowed-tools: arxiv_search, hf_papers
triggers:
  - "find papers"
  - "academic research"
  - "scientific literature"
  - "citations"
metadata:
  author: flow
---

# Academic Search

<context>
Retrieves and summarizes academic papers from ArXiv and HuggingFace Daily Papers.
</context>

<instructions>
1. Extract key concepts and technical terms from the query
2. Search ArXiv for relevant papers
3. Check HF Daily Papers for recent ML/AI work if applicable
4. Return top 3-5 most relevant papers with abstracts
5. Highlight practical implications and key findings
</instructions>

<output_format>
List of papers: **Title** (Year) — Authors. One-sentence summary. Link.
</output_format>

<examples>
**Input:** Papers on RLHF for language models
**Output:** 1. **Training language models to follow instructions with human feedback** (2022) — Ouyang et al. Introduces InstructGPT... [arxiv link]
</examples>
""",
    },
    {
        "name": "source-evaluation",
        "category": "Research",
        "description": "Use this skill when the user needs to evaluate the credibility, bias, or quality of a source or claim.",
        "content_md": """\
---
name: source-evaluation
description: Use this skill when the user needs to evaluate the credibility, bias, or quality of a source or claim.
version: "1.0"
category: Research
allowed-tools: fetch_webpage, tavily_search
triggers:
  - "is this reliable"
  - "evaluate source"
  - "fact check"
  - "is this true"
metadata:
  author: flow
---

# Source Evaluation

<context>
Critical evaluation of sources and claims using corroborating evidence and credibility signals.
</context>

<instructions>
1. Identify the specific claim or source to evaluate
2. Check the primary source directly if a URL is provided
3. Search for corroborating or contradicting evidence
4. Assess: author credentials, publication date, peer review status, conflicts of interest
5. Cross-reference with authoritative sources
</instructions>

<output_format>
Verdict: [Credible / Questionable / Misleading]. Confidence: [High/Medium/Low]. Reasoning in 2-3 sentences with supporting sources.
</output_format>
""",
    },

    # ── Code ──────────────────────────────────────────────────────
    {
        "name": "code-explanation",
        "category": "Code",
        "description": "Use this skill when the user asks to explain, document, or understand a piece of code.",
        "content_md": """\
---
name: code-explanation
description: Use this skill when the user asks to explain, document, or understand a piece of code.
version: "1.0"
category: Code
allowed-tools: retrieve
triggers:
  - "explain this code"
  - "what does this do"
  - "how does this work"
  - "document"
metadata:
  author: flow
---

# Code Explanation

<context>
Produces clear, audience-appropriate explanations of code at multiple levels of detail.
</context>

<instructions>
1. Identify the language and overall purpose of the code
2. Explain the high-level intent in one sentence
3. Walk through key sections in logical order
4. Highlight non-obvious patterns, algorithms, or design decisions
5. Note any potential issues or improvements
</instructions>

<output_format>
**Purpose:** One sentence. **How it works:** Numbered walkthrough. **Notable details:** Bullet points.
</output_format>
""",
    },
    {
        "name": "code-review",
        "category": "Code",
        "description": "Use this skill when the user asks to review code for bugs, security issues, or improvements.",
        "content_md": """\
---
name: code-review
description: Use this skill when the user asks to review code for bugs, security issues, or improvements.
version: "1.0"
category: Code
allowed-tools: sandbox
triggers:
  - "review this code"
  - "code review"
  - "find bugs"
  - "security review"
metadata:
  author: flow
---

# Code Review

<context>
Systematic code review focusing on correctness, security, performance, and maintainability.
</context>

<instructions>
1. Scan for security vulnerabilities (injection, auth, secrets exposure)
2. Identify logic errors and edge cases
3. Check error handling and null safety
4. Assess performance implications
5. Note style/convention violations only if egregious
6. Prioritize findings: Critical > High > Medium > Low
</instructions>

<output_format>
**Critical:** [list or "none"]. **High:** [list]. **Suggestions:** [list]. Report only high-confidence issues.
</output_format>
""",
    },
    {
        "name": "debugging-guide",
        "category": "Code",
        "description": "Use this skill when the user is debugging an error, exception, or unexpected behavior.",
        "content_md": """\
---
name: debugging-guide
description: Use this skill when the user is debugging an error, exception, or unexpected behavior.
version: "1.0"
category: Code
allowed-tools: sandbox, retrieve
triggers:
  - "debug"
  - "error"
  - "exception"
  - "not working"
  - "broken"
metadata:
  author: flow
---

# Debugging Guide

<context>
Systematic debugging using hypothesis-driven investigation and root-cause analysis.
</context>

<instructions>
1. Reproduce the problem from the error message and context
2. Identify the most likely root cause (top 2-3 hypotheses)
3. Propose targeted diagnostic steps for each hypothesis
4. Provide the most likely fix with explanation
5. Suggest tests to prevent regression
</instructions>

<output_format>
**Root cause:** One sentence. **Fix:** Code snippet + explanation. **Prevention:** One-line test suggestion.
</output_format>
""",
    },

    # ── Communication ─────────────────────────────────────────────
    {
        "name": "email-drafter",
        "category": "Communication",
        "description": "Use this skill when the user needs to write or improve a professional email.",
        "content_md": """\
---
name: email-drafter
description: Use this skill when the user needs to write or improve a professional email.
version: "1.0"
category: Communication
allowed-tools: retrieve
triggers:
  - "write an email"
  - "draft email"
  - "email to"
  - "reply to"
metadata:
  author: flow
---

# Email Drafter

<context>
Writes professional, clear emails adapted to context (tone, recipient, urgency).
</context>

<instructions>
1. Identify recipient type (internal/external, seniority level)
2. Determine tone needed (formal, friendly, urgent)
3. Structure: subject line → greeting → context → ask/action → closing
4. Keep to 150 words unless complexity requires more
5. End with a clear single call-to-action
</instructions>

<output_format>
**Subject:** [subject line]

[email body]
</output_format>
""",
    },
    {
        "name": "meeting-summarizer",
        "category": "Communication",
        "description": "Use this skill when the user provides meeting notes or transcripts and needs a summary with action items.",
        "content_md": """\
---
name: meeting-summarizer
description: Use this skill when the user provides meeting notes or transcripts and needs a summary with action items.
version: "1.0"
category: Communication
allowed-tools: retrieve
triggers:
  - "summarize meeting"
  - "meeting notes"
  - "action items"
  - "meeting summary"
metadata:
  author: flow
---

# Meeting Summarizer

<context>
Distills meeting transcripts or notes into executive summaries with clear action items and owners.
</context>

<instructions>
1. Extract the meeting purpose and key decisions made
2. Identify all action items with assigned owners and deadlines
3. Note unresolved questions or blockers
4. Write a 3-5 sentence executive summary
5. Format action items as a checklist
</instructions>

<output_format>
**Summary:** [3-5 sentences]. **Decisions:** [bullet list]. **Action items:** [ ] Owner: Task (deadline).
</output_format>
""",
    },
    {
        "name": "slack-formatter",
        "category": "Communication",
        "description": "Use this skill when the user needs to format or rewrite content for Slack messages.",
        "content_md": """\
---
name: slack-formatter
description: Use this skill when the user needs to format or rewrite content for Slack messages.
version: "1.0"
category: Communication
allowed-tools: retrieve
triggers:
  - "slack message"
  - "post to slack"
  - "format for slack"
metadata:
  author: flow
---

# Slack Formatter

<context>
Rewrites content for Slack: scannable, concise, using Slack markdown (*bold*, _italic_, `code`, bullet lists).
</context>

<instructions>
1. Lead with the most important information
2. Use bullet points for lists (max 5 bullets)
3. Bold key terms and action items
4. Keep total length under 300 characters for announcements, longer for updates
5. Add relevant emoji sparingly for tone
</instructions>

<output_format>
Slack-formatted message ready to paste.
</output_format>
""",
    },

    # ── Analysis ──────────────────────────────────────────────────
    {
        "name": "topic-clustering",
        "category": "Analysis",
        "description": "Use this skill when the user wants to group, categorize, or cluster a set of items by topic.",
        "content_md": """\
---
name: topic-clustering
description: Use this skill when the user wants to group, categorize, or cluster a set of items by topic.
version: "1.0"
category: Analysis
allowed-tools: retrieve
triggers:
  - "group by topic"
  - "categorize"
  - "cluster"
  - "organize these"
metadata:
  author: flow
---

# Topic Clustering

<context>
Groups unstructured items into coherent clusters using semantic similarity.
</context>

<instructions>
1. Read all items and identify recurring themes
2. Propose 3-7 topic clusters (fewer is better)
3. Assign each item to its best-fit cluster
4. Name each cluster with a 2-4 word label
5. Flag items that don't fit any cluster as "Other"
</instructions>

<output_format>
**Cluster Name** (N items): item1, item2, item3...
</output_format>
""",
    },
    {
        "name": "sentiment-classifier",
        "category": "Analysis",
        "description": "Use this skill when the user needs to classify sentiment of text (positive/negative/neutral).",
        "content_md": """\
---
name: sentiment-classifier
description: Use this skill when the user needs to classify sentiment of text (positive, negative, or neutral).
version: "1.0"
category: Analysis
allowed-tools: retrieve
triggers:
  - "sentiment"
  - "tone analysis"
  - "positive or negative"
metadata:
  author: flow
---

# Sentiment Classifier

<context>
Fine-grained sentiment analysis with confidence scores and reasoning.
</context>

<instructions>
1. Read the text carefully
2. Classify overall sentiment: Positive / Neutral / Negative
3. Score confidence: 0-100%
4. Identify the 2-3 most sentiment-carrying phrases
5. Note any mixed or ambiguous signals
</instructions>

<output_format>
**Sentiment:** [Positive/Neutral/Negative] (confidence: X%). **Key signals:** phrase1, phrase2. **Notes:** [any nuance].
</output_format>
""",
    },
    {
        "name": "text-summarizer",
        "category": "Analysis",
        "description": "Use this skill when the user wants to summarize a long text, article, or document.",
        "content_md": """\
---
name: text-summarizer
description: Use this skill when the user wants to summarize a long text, article, or document.
version: "1.0"
category: Analysis
allowed-tools: retrieve
triggers:
  - "summarize"
  - "tldr"
  - "brief summary"
  - "key points"
metadata:
  author: flow
---

# Text Summarizer

<context>
Produces accurate, faithful summaries at multiple granularities without hallucinating.
</context>

<instructions>
1. Identify the document type (article, report, transcript, etc.)
2. Extract the central thesis or main point
3. Pull out supporting key points (max 5)
4. Note any caveats, limitations, or counter-arguments
5. Write summary proportional to source length
</instructions>

<output_format>
**TL;DR:** One sentence. **Key points:** bullet list. **Caveats:** [if any].
</output_format>
""",
    },

    # ── Memory ────────────────────────────────────────────────────
    {
        "name": "fact-extraction",
        "category": "Memory",
        "description": "Use this skill when new factual information about the user should be extracted and stored for future reference.",
        "content_md": """\
---
name: fact-extraction
description: Use this skill when new factual information about the user should be extracted and stored for future reference.
version: "1.0"
category: Memory
allowed-tools: retrieve
triggers:
  - "remember that"
  - "note that"
  - "I prefer"
  - "I work at"
metadata:
  author: flow
---

# Fact Extraction

<context>
Extracts atomic, reusable facts from conversation for the agent's long-term memory.
</context>

<instructions>
1. Identify statements that are facts about the user, their preferences, or their context
2. Decompose compound statements into atomic facts
3. Phrase each fact as a standalone, context-free statement
4. Discard transient facts (e.g. "I'm tired today") — keep durable ones
5. Return confirmed list for storage
</instructions>

<output_format>
Extracted facts as bullet points. One fact per line.
</output_format>
""",
    },
    {
        "name": "pattern-recognition",
        "category": "Memory",
        "description": "Use this skill to identify recurring patterns in user behavior, preferences, or requests.",
        "content_md": """\
---
name: pattern-recognition
description: Use this skill to identify recurring patterns in user behavior, preferences, or requests.
version: "1.0"
category: Memory
allowed-tools: retrieve
triggers:
  - "pattern"
  - "recurring"
  - "usually asks"
metadata:
  author: flow
---

# Pattern Recognition

<context>
Identifies recurring patterns in past interactions to anticipate needs and personalize responses.
</context>

<instructions>
1. Review the conversation history for repeated topics, styles, or preferences
2. Identify patterns with ≥2 occurrences
3. Classify each pattern: preference, workflow, knowledge gap, communication style
4. Rank by frequency and relevance
5. Surface insights that can improve future interactions
</instructions>

<output_format>
**Patterns identified:** [type] — description (seen N times).
</output_format>
""",
    },
    {
        "name": "preference-tracking",
        "category": "Memory",
        "description": "Use this skill to update and maintain a model of user preferences based on feedback signals.",
        "content_md": """\
---
name: preference-tracking
description: Use this skill to update and maintain a model of user preferences based on feedback signals.
version: "1.0"
category: Memory
allowed-tools: retrieve
triggers:
  - "I like"
  - "I don't like"
  - "prefer"
  - "always"
  - "never"
metadata:
  author: flow
---

# Preference Tracking

<context>
Maintains an up-to-date preference model from explicit and implicit feedback signals.
</context>

<instructions>
1. Detect explicit preferences (stated directly) and implicit ones (inferred from feedback)
2. Record: preference type, value, confidence, date
3. Handle contradictions by keeping both with timestamps
4. Merge with existing preferences if already known
5. Return updated preference delta
</instructions>

<output_format>
**New preference:** [type]: [value] (confidence: [high/medium/low]).
</output_format>
""",
    },

    # ── Planning ──────────────────────────────────────────────────
    {
        "name": "task-decomposer",
        "category": "Planning",
        "description": "Use this skill when the user presents a large or complex goal that needs to be broken into steps.",
        "content_md": """\
---
name: task-decomposer
description: Use this skill when the user presents a large or complex goal that needs to be broken into steps.
version: "1.0"
category: Planning
allowed-tools: retrieve
triggers:
  - "break down"
  - "plan this"
  - "how to approach"
  - "decompose"
metadata:
  author: flow
---

# Task Decomposer

<context>
Breaks complex goals into actionable, sequenced subtasks with dependencies and estimates.
</context>

<instructions>
1. Clarify the end goal and success criteria
2. Identify major phases or milestones
3. Break each phase into concrete tasks (verb + noun)
4. Identify dependencies between tasks
5. Assign rough effort estimates (S/M/L) to each task
</instructions>

<output_format>
**Goal:** [one sentence]. **Phases:** numbered list with tasks indented. **Dependencies:** noted inline.
</output_format>
""",
    },
    {
        "name": "goal-setting",
        "category": "Planning",
        "description": "Use this skill when the user wants to define or refine a goal using SMART criteria.",
        "content_md": """\
---
name: goal-setting
description: Use this skill when the user wants to define or refine a goal using SMART criteria.
version: "1.0"
category: Planning
allowed-tools: retrieve
triggers:
  - "set a goal"
  - "define objectives"
  - "OKR"
  - "SMART goal"
metadata:
  author: flow
---

# Goal Setting

<context>
Transforms vague intentions into SMART goals (Specific, Measurable, Achievable, Relevant, Time-bound).
</context>

<instructions>
1. Understand the user's current situation and desired outcome
2. Identify ambiguities (what does success look like?)
3. Reframe as a SMART goal
4. Propose 2-3 leading indicators to track progress
5. Note potential obstacles and mitigations
</instructions>

<output_format>
**SMART Goal:** [full statement]. **Metrics:** bullet list. **Risks:** bullet list.
</output_format>
""",
    },
    {
        "name": "timeline-builder",
        "category": "Planning",
        "description": "Use this skill when the user needs to create a schedule, timeline, or project plan with deadlines.",
        "content_md": """\
---
name: timeline-builder
description: Use this skill when the user needs to create a schedule, timeline, or project plan with deadlines.
version: "1.0"
category: Planning
allowed-tools: retrieve
triggers:
  - "timeline"
  - "schedule"
  - "deadline"
  - "project plan"
  - "when should I"
metadata:
  author: flow
---

# Timeline Builder

<context>
Constructs realistic timelines by working backward from deadlines or forward from start dates.
</context>

<instructions>
1. Identify the hard deadline or desired completion date
2. List all required tasks from the task decomposition
3. Assign durations and sequence them with dependencies
4. Add buffer time (20% for known risks, more for unknowns)
5. Highlight critical path items
</instructions>

<output_format>
**Timeline:** Week-by-week or day-by-day table. **Critical path:** highlighted. **Buffers:** noted.
</output_format>
""",
    },

    # ── General ───────────────────────────────────────────────────
    {
        "name": "clarifying-questions",
        "category": "General",
        "description": "Use this skill when a user request is ambiguous and needs clarification before proceeding.",
        "content_md": """\
---
name: clarifying-questions
description: Use this skill when a user request is ambiguous and needs clarification before proceeding.
version: "1.0"
category: General
allowed-tools: retrieve
triggers:
  - "what do you mean"
  - "could you clarify"
  - "I'm not sure what you want"
metadata:
  author: flow
---

# Clarifying Questions

<context>
Asks targeted questions to resolve ambiguity before generating a final response.
</context>

<instructions>
1. Identify the ambiguous dimension(s) in the request
2. Formulate the fewest questions needed to resolve the ambiguity (max 3)
3. Prefer closed/multiple-choice questions over open-ended when possible
4. Explain briefly why each question matters
</instructions>

<output_format>
Ask questions directly, numbered. One clarifying sentence per question.
</output_format>
""",
    },
]
