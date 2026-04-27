from __future__ import annotations

from openai import AsyncOpenAI


async def embed_texts(*, api_key: str, texts: list[str]) -> list[list[float]]:
    client = AsyncOpenAI(api_key=api_key)
    res = await client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [list(d.embedding) for d in res.data]
