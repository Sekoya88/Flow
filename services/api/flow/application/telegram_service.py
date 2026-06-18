"""Telegram Bot API — thin httpx wrappers, no business logic."""

from __future__ import annotations

import httpx

_BASE = "https://api.telegram.org/bot{token}/{method}"
_TELEGRAM_MAX_CHARS = 4096


def _url(token: str, method: str) -> str:
    return _BASE.format(token=token, method=method)


def _truncate(text: str) -> str:
    if len(text) <= _TELEGRAM_MAX_CHARS:
        return text
    return text[: _TELEGRAM_MAX_CHARS - 3] + "..."


async def get_me(bot_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(_url(bot_token, "getMe"))
        r.raise_for_status()
        return r.json()


async def register_webhook(bot_token: str, webhook_url: str, secret: str) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            _url(bot_token, "setWebhook"),
            json={"url": webhook_url, "secret_token": secret, "allowed_updates": ["message"]},
        )
        r.raise_for_status()


async def delete_webhook(bot_token: str) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(_url(bot_token, "deleteWebhook"))


async def send_message(bot_token: str, chat_id: int | str, text: str) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(
            _url(bot_token, "sendMessage"),
            json={"chat_id": chat_id, "text": _truncate(text), "parse_mode": "Markdown"},
        )


async def send_chat_action(bot_token: str, chat_id: int | str) -> None:
    async with httpx.AsyncClient(timeout=5) as c:
        await c.post(
            _url(bot_token, "sendChatAction"),
            json={"chat_id": chat_id, "action": "typing"},
        )
