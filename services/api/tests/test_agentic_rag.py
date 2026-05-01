from flow.infrastructure.agentic_rag.context_pack import flow_kb_label, format_graded_context
from flow.infrastructure.agentic_rag.graph import route_after_grade, route_supervisor


def test_route_after_grade() -> None:
    assert route_after_grade({"graded_docs": [{"x": 1}], "iteration_count": 1}) == "assemble"
    assert route_after_grade({"graded_docs": [], "iteration_count": 3, "max_iterations": 3}) == "web_fallback"
    assert route_after_grade({"graded_docs": [], "iteration_count": 1, "max_iterations": 3}) == "rewrite"


def test_route_supervisor() -> None:
    assert route_supervisor({"routing_decision": "DIRECT_ANSWER"}) == "assemble_direct"
    assert route_supervisor({"routing_decision": "WEB_SEARCH"}) == "web_search"
    assert route_supervisor({"routing_decision": "RETRIEVE_HYBRID"}) == "retrieve"


def test_format_graded_context_includes_label_and_body() -> None:
    text = format_graded_context(
        [
            {
                "content": "chunk body",
                "metadata": {"title": "Doc"},
                "grade": {"combined_score": 0.9, "thematic_score": 0.9},
            }
        ]
    )
    assert flow_kb_label(1) in text
    assert "chunk body" in text
    assert "Doc" in text


def test_build_rag_messages_web_only() -> None:
    from flow.infrastructure.agentic_rag.context_pack import build_rag_messages

    bits = build_rag_messages(graded_docs=[], web_results=["snippet a", "snippet b"])
    assert len(bits) == 1
    assert "Web search" in bits[0]
    assert "snippet a" in bits[0]
