from __future__ import annotations

from pydantic import BaseModel, Field

ROUTING_LITERAL = (
    "RETRIEVE_HYBRID",
    "RETRIEVE_DENSE",
    "WEB_SEARCH",
    "DIRECT_ANSWER",
    "MULTI_HOP",
)


class RoutingDecision(BaseModel):
    decision: str = Field(
        description="RETRIEVE_HYBRID | RETRIEVE_DENSE | WEB_SEARCH | DIRECT_ANSWER | MULTI_HOP"
    )
    reasoning: str = ""
    sub_queries: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class DocumentGrade(BaseModel):
    thematic_score: float = Field(ge=0.0, le=1.0)
    utility_score: float = Field(ge=0.0, le=1.0)
    relevant: bool = False
    reason: str = ""

    @property
    def combined_score(self) -> float:
        return round((self.thematic_score + self.utility_score) / 2, 3)


class SourceCitation(BaseModel):
    chunk_id: str
    source_url: str = ""
    source_title: str = ""
    page_number: int | None = None
    excerpt: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    used_in_answer: bool = False
