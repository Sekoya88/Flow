"""Bot integrations — Telegram (and future WhatsApp).

Public endpoints (webhook receivers) are verified by a per-bot secret token,
not by JWT — Telegram POSTs from its own servers, not from our frontend.
"""
from __future__ import annotations

import asyncio
import secrets
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from flow.application.telegram_service import (
    delete_webhook,
    get_me,
    register_webhook,
    send_chat_action,
    send_message,
)
from flow.infrastructure.queue.client import enqueue_execution
from flow.interfaces.http.deps import get_current_user_id, get_pool

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class TelegramBotIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    bot_token: str


# ── CRUD (auth required) ──────────────────────────────────────────────────────


@router.post("/telegram", status_code=status.HTTP_201_CREATED)
async def register_telegram_bot(
    body: TelegramBotIn,
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> dict:
    member = await pool.fetchrow(
        "SELECT 1 FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        body.workspace_id,
        user_id,
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a workspace member")

    agent = await pool.fetchrow(
        "SELECT id FROM agents WHERE id = $1 AND workspace_id = $2",
        body.agent_id,
        body.workspace_id,
    )
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found in workspace")

    try:
        me = await get_me(body.bot_token)
        bot_username: str | None = me.get("result", {}).get("username")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid bot token: {exc}") from exc

    webhook_secret = secrets.token_hex(32)
    bot_id: UUID = await pool.fetchval(
        """
        INSERT INTO telegram_bots (workspace_id, agent_id, user_id, bot_token, bot_username, webhook_secret)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        body.workspace_id,
        body.agent_id,
        user_id,
        body.bot_token,
        bot_username,
        webhook_secret,
    )

    api_base = str(request.base_url).rstrip("/")
    webhook_url = f"{api_base}/api/v1/integrations/telegram/{bot_id}/webhook"
    await register_webhook(body.bot_token, webhook_url, webhook_secret)

    return {"bot_id": str(bot_id), "bot_username": bot_username, "webhook_url": webhook_url}


@router.get("/telegram")
async def list_telegram_bots(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> list[dict]:
    member = await pool.fetchrow(
        "SELECT 1 FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        workspace_id,
        user_id,
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a workspace member")

    rows = await pool.fetch(
        """
        SELECT tb.id, tb.agent_id, tb.bot_username, tb.created_at, a.name AS agent_name
        FROM telegram_bots tb
        JOIN agents a ON a.id = tb.agent_id
        WHERE tb.workspace_id = $1
        ORDER BY tb.created_at DESC
        """,
        workspace_id,
    )
    return [
        {
            "id": str(r["id"]),
            "agent_id": str(r["agent_id"]),
            "agent_name": r["agent_name"],
            "bot_username": r["bot_username"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.delete("/telegram/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_telegram_bot(
    bot_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> None:
    member = await pool.fetchrow(
        "SELECT 1 FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        workspace_id,
        user_id,
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a workspace member")

    bot = await pool.fetchrow(
        "SELECT bot_token FROM telegram_bots WHERE id = $1 AND workspace_id = $2",
        bot_id,
        workspace_id,
    )
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bot not found")

    await delete_webhook(bot["bot_token"])
    await pool.execute("DELETE FROM telegram_bots WHERE id = $1", bot_id)


# ── Webhook receiver (public — verified by Telegram secret header) ────────────


@router.post("/telegram/{bot_id}/webhook")
async def telegram_webhook(
    bot_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict:
    bot = await pool.fetchrow("SELECT * FROM telegram_bots WHERE id = $1", bot_id)
    if not bot:
        return {"ok": True}  # silently ignore unknown bot_id (Telegram retries)

    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != bot["webhook_secret"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid webhook secret")

    body = await request.json()
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    text: str = (message.get("text") or "").strip()
    chat_id: int = message["chat"]["id"]
    if not text:
        return {"ok": True}

    background_tasks.add_task(
        _handle_message,
        app=request.app,
        pool=pool,
        bot_token=bot["bot_token"],
        workspace_id=bot["workspace_id"],
        agent_id=bot["agent_id"],
        user_id=bot["user_id"],
        chat_id=chat_id,
        text=text,
    )
    return {"ok": True}


async def _handle_message(
    *,
    app: object,
    pool: asyncpg.Pool,
    bot_token: str,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    chat_id: int,
    text: str,
) -> None:
    from flow.infrastructure.persistence.repo import FlowRepository

    repo = FlowRepository(pool)
    stream_hub = app.state.stream_hub  # type: ignore[attr-defined]

    try:
        await send_chat_action(bot_token, chat_id)

        eid, _ = await repo.create_execution(agent_id, workspace_id, text)

        agent_row = await pool.fetchrow("SELECT config FROM agents WHERE id = $1", agent_id)
        agent_config: dict = dict(agent_row["config"]) if agent_row and isinstance(agent_row["config"], dict) else {}

        await enqueue_execution(
            execution_id=eid,
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id,
            user_message=text,
            agent_config=agent_config,
        )

        tokens: list[str] = []
        final_answer: str | None = None

        async def _collect(hub, execution_id: UUID) -> str | None:
            nonlocal tokens, final_answer
            async for event in hub.subscribe(execution_id):
                kind = event.get("kind")
                if kind == "token":
                    tokens.append(event.get("text", ""))
                elif kind == "final":
                    return event.get("answer") or "".join(tokens)
                elif kind in ("error", "done"):
                    break
            return None

        try:
            async with asyncio.timeout(55):
                final_answer = await _collect(stream_hub, eid)
        except TimeoutError:
            # Send whatever accumulated tokens we have, then wait for final
            partial = "".join(tokens)
            if partial:
                await send_message(bot_token, chat_id, f"_{partial}_\n\n_(processing...)_")
            tokens.clear()
            try:
                async with asyncio.timeout(120):
                    final_answer = await _collect(stream_hub, eid)
            except TimeoutError:
                pass

        answer = final_answer or "".join(tokens) or "No response received."
        await send_message(bot_token, chat_id, answer)

    except Exception as exc:  # noqa: BLE001
        try:
            await send_message(bot_token, chat_id, f"Error: {exc}")
        except Exception:
            pass
