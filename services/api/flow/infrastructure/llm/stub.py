from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class StubChatModel(BaseChatModel):
    """Deterministic test double for BaseChatModel.

    Cycles through scripted responses in order. Uses object.__setattr__ to
    mutate _call_count without triggering Pydantic's immutability checks.
    """

    responses: list[str] = []

    def __init__(self, responses: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "responses", responses or [])
        object.__setattr__(self, "_call_count", 0)

    @property
    def _llm_type(self) -> str:
        return "stub"

    def _generate(
        self,
        messages: Any,
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        responses: list[str] = object.__getattribute__(self, "responses")
        count: int = object.__getattribute__(self, "_call_count")
        text = responses[count % len(responses)] if responses else ""
        object.__setattr__(self, "_call_count", count + 1)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _agenerate(
        self,
        messages: Any,
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)
