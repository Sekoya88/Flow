from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from flow.application.kg_connectors import fetch_from_obsidian_api, parse_upload, sync_from_path
from flow.application.kg_ingestion_graph import IngestionConfig, build_kg_ingestion_graph
from flow.application.kg_query_graph import QueryConfig, build_kg_query_graph
from flow.infrastructure.kg.graph_engine import KGGraphEngine
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas_kg import (
    KGEdgeOut,
    KGGraphOut,
    KGIngestObsidianIn,
    KGNodeDetailOut,
    KGNodeOut,
    KGQueryIn,
    KGSyncIn,
)

router = APIRouter(prefix="/api/v1/kg", tags=["knowledge-graph"])


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")


def _node_out(row) -> KGNodeOut:
    import json as _json

    meta = row["metadata"]
    if isinstance(meta, str):
        meta = _json.loads(meta)
    return KGNodeOut(
        id=str(row["id"]),
        label=row["label"],
        node_type=row["node_type"],
        summary=row.get("summary"),
        source_path=row.get("source_path"),
        cluster_id=row.get("cluster_id"),
        pagerank=float(row.get("pagerank") or 0.0),
        pos_x=float(row.get("pos_x") or 0.0),
        pos_y=float(row.get("pos_y") or 0.0),
        metadata=meta or {},
    )


def _edge_out(row) -> KGEdgeOut:
    return KGEdgeOut(
        id=str(row["id"]),
        source_id=str(row["source_id"]),
        target_id=str(row["target_id"]),
        edge_type=row["edge_type"],
        weight=float(row.get("weight") or 1.0),
    )


async def _run_ingest_batch(docs, config: IngestionConfig, repo, workspace_id, engine: KGGraphEngine) -> int:
    """Ingest all docs, then recompute graph metrics once at the end."""
    graph = build_kg_ingestion_graph(config)
    count = 0
    for doc in docs:
        result = await graph.ainvoke({"document": doc})
        if not result.get("is_duplicate"):
            count += 1
    G = await engine.load_graph(workspace_id)
    if G.number_of_nodes() > 0:
        engine.compute_metrics(G)
        positions = engine.spring_positions(G)
        pageranks = {UUID(nid): G.nodes[nid]["pagerank"] for nid in G.nodes}
        clusters = {UUID(nid): G.nodes[nid].get("cluster_id", 0) for nid in G.nodes}
        pos_map = {UUID(nid): positions.get(nid, (0.0, 0.0)) for nid in G.nodes}
        await repo.bulk_update_kg_metrics(pageranks, clusters, pos_map)
    return count


@router.post("/ingest/upload", status_code=status.HTTP_202_ACCEPTED)
async def ingest_upload(
    request: Request,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    files: list[UploadFile] = File(...),
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    from flow.config import get_settings

    s = get_settings()
    if not s.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required")

    docs = await parse_upload(files)
    engine = KGGraphEngine(request.app.state.pool)
    config = IngestionConfig(workspace_id=workspace_id, repo=repo, openai_api_key=s.openai_api_key)
    count = await _run_ingest_batch(docs, config, repo, workspace_id, engine)
    return {"ingested": count, "total": len(docs)}


@router.post("/ingest/obsidian", status_code=status.HTTP_202_ACCEPTED)
async def ingest_obsidian(
    request: Request,
    body: KGIngestObsidianIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, body.workspace_id, repo)
    from flow.config import get_settings

    s = get_settings()
    if not s.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required")

    try:
        docs = await fetch_from_obsidian_api(body.base_url, body.api_key, body.vault_path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Obsidian API error: {e}")

    engine = KGGraphEngine(request.app.state.pool)
    config = IngestionConfig(workspace_id=body.workspace_id, repo=repo, openai_api_key=s.openai_api_key)
    count = await _run_ingest_batch(docs, config, repo, body.workspace_id, engine)
    return {"ingested": count, "total": len(docs)}


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_vault(
    request: Request,
    body: KGSyncIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, body.workspace_id, repo)
    from flow.config import get_settings

    s = get_settings()
    if not s.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required")

    try:
        docs = await sync_from_path(body.vault_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    engine = KGGraphEngine(request.app.state.pool)
    config = IngestionConfig(workspace_id=body.workspace_id, repo=repo, openai_api_key=s.openai_api_key)
    count = await _run_ingest_batch(docs, config, repo, body.workspace_id, engine)
    return {"ingested": count, "total": len(docs)}


@router.get("/graph")
async def get_graph(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    node_types: str | None = None,
) -> KGGraphOut:
    await _assert_workspace(user_id, workspace_id, repo)
    if node_types:
        type_list = [t.strip() for t in node_types.split(",") if t.strip()]
        nodes = await repo.list_kg_nodes_by_types(workspace_id, type_list)
    else:
        nodes = await repo.list_kg_nodes(workspace_id)
    node_ids = {n["id"] for n in nodes}
    edges = await repo.list_kg_edges(workspace_id)
    edges = [e for e in edges if e["source_id"] in node_ids and e["target_id"] in node_ids]
    cluster_ids = {n.get("cluster_id") for n in nodes if n.get("cluster_id") is not None}
    return KGGraphOut(
        nodes=[_node_out(n) for n in nodes],
        edges=[_edge_out(e) for e in edges],
        cluster_count=len(cluster_ids),
    )


@router.get("/graph/node/{node_id}")
async def get_node_detail(
    node_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> KGNodeDetailOut:
    await _assert_workspace(user_id, workspace_id, repo)
    node = await repo.get_kg_node(node_id)
    if node is None or node["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="Node not found")
    neighbors, edges = await repo.get_kg_neighbors(node_id, workspace_id)
    return KGNodeDetailOut(
        node=_node_out(node),
        neighbors=[_node_out(n) for n in neighbors],
        edges=[_edge_out(e) for e in edges],
    )


@router.delete("/node/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> None:
    await _assert_workspace(user_id, workspace_id, repo)
    deleted = await repo.delete_kg_node(workspace_id, node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")


@router.post("/query")
async def query_graph(
    request: Request,
    body: KGQueryIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> StreamingResponse:
    await _assert_workspace(user_id, body.workspace_id, repo)
    from flow.config import get_settings

    s = get_settings()
    if not s.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required")

    engine = KGGraphEngine(request.app.state.pool)
    config = QueryConfig(
        workspace_id=body.workspace_id,
        repo=repo,
        engine=engine,
        openai_api_key=s.openai_api_key,
    )
    graph = build_kg_query_graph(config)

    async def event_stream():
        result = await graph.ainvoke({"question": body.question})

        for tc in result.get("tool_calls", []):
            yield f"event: kg_tool_call\ndata: {json.dumps(tc)}\n\n"

        if result.get("graph_path"):
            yield f"event: kg_path\ndata: {json.dumps({'nodes': result['graph_path'], 'edges': result.get('graph_path_edges', [])})}\n\n"

        if result.get("cited_node_ids"):
            yield f"event: kg_highlight\ndata: {json.dumps({'node_ids': result['cited_node_ids']})}\n\n"

        answer = result.get("answer", "")
        yield f"event: kg_answer\ndata: {json.dumps({'text': answer})}\n\n"
        yield "event: kg_done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
