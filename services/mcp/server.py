from __future__ import annotations

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.sse import SseServerTransport

from .auth import current_mcp_context, verify_jwt_token
from .mcp_app import mcp

app = FastAPI(title="Flow MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sse_transport = SseServerTransport("/messages/")


@app.get("/sse")
async def sse_endpoint(request: Request, token: str = Query(...)) -> None:
    """SSE MCP endpoint — authenticated via Flow JWT query param."""
    try:
        context = await verify_jwt_token(token)
    except ValueError as e:
        # Return 401 directly since we can't raise HTTPException inside SSE easily
        return Response(str(e), status_code=401)  # type: ignore[return-value]

    current_mcp_context.set(context)
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send  # type: ignore[attr-defined]
    ) as streams:
        await mcp._mcp_server.run(
            streams[0],
            streams[1],
            mcp._mcp_server.create_initialization_options(),
        )


@app.post("/messages/")
async def handle_post_message(request: Request, token: str = Query(default="")) -> None:
    """Handle MCP POST messages for the SSE transport."""
    if token:
        try:
            context = await verify_jwt_token(token)
            current_mcp_context.set(context)
        except ValueError:
            pass
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send  # type: ignore[attr-defined]
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "flow-mcp"}
