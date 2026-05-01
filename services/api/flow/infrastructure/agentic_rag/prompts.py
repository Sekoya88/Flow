SUPERVISOR_PROMPT = """You are a RAG retrieval supervisor. Pick the best retrieval strategy.

User question: {query}
Attempt: {iteration} / {max_iterations}
Prior context: {previous_context}

Strategies:
- RETRIEVE_HYBRID: factual question, specific terms, code, proper nouns → dense + sparse BM25 with RRF
- RETRIEVE_DENSE: broad conceptual / semantic-only question
- WEB_SEARCH: very recent events or clearly outside the doc base
- DIRECT_ANSWER: greeting, trivial calculation, no docs needed
- MULTI_HOP: complex question → decompose (fill sub_queries)

Return JSON only (no markdown):
{{"decision": "RETRIEVE_HYBRID", "reasoning": "...", "sub_queries": [], "confidence": 0.9}}
"""

GRADER_PROMPT = """You evaluate chunk relevance for answering a user question.

Question:
{question}

Chunk #{chunk_id}:
---
{document}
---
Source metadata: {source}

Score independently:
1) thematic_score: does the chunk discuss the topic? 0=off-topic, 1=on-topic
2) utility_score: does it help answer the question? 0=no facts, 1=direct answer available

Set relevant=true if (thematic_score + utility_score) / 2 >= 0.6

Return JSON only:
{{"thematic_score": 0.8, "utility_score": 0.7, "relevant": true, "reason": "..."}}
"""

REWRITER_PROMPT = """Rewrite the search query to improve vector retrieval.

Original: {query}
Issue: {failure_reason}
Attempt {attempt} / {max_attempts}

Reply with ONLY the rewritten query text (no quotes, no explanation).
"""
