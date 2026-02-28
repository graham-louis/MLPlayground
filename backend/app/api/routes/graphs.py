"""API routes for graph management and node execution.

Endpoints
---------
GET  /api/v1/graphs/nodes                 List all registered node types.
GET  /api/v1/graphs/datasource-keys       List registered datasource keys.
GET  /api/v1/graphs/datasource-info/{key} Columns + query params of a datasource.
POST /api/v1/graphs/upload                Upload a CSV/data file to artifacts/uploads/.
GET  /api/v1/graphs/workflows             List saved workflows.
GET  /api/v1/graphs/workflows/{id}        Fetch a single saved workflow.
POST /api/v1/graphs/workflows             Create a saved workflow.
PUT  /api/v1/graphs/workflows/{id}        Update a saved workflow.
DELETE /api/v1/graphs/workflows/{id}      Delete a saved workflow.
POST /api/v1/graphs/validate              Validate a graph spec (no execution).
POST /api/v1/graphs/run                   Submit a graph for async execution.
GET  /api/v1/graphs/{run_id}/status       Poll run status.
GET  /api/v1/graphs/{run_id}/result       Fetch completed run outputs.
GET  /api/v1/graphs/artifacts/{path}      Download an artifact file.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import uuid
from datetime import datetime as _dt
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine, get_session
from app.db_models import GraphRun, SavedWorkflow
from app.nodes.executor import GraphBuilder, GraphSpec, _EXECUTOR, serialize_outputs
from app.nodes.registry import NODE_REGISTRY

logger = logging.getLogger(__name__)

ARTIFACTS_ROOT = Path(settings.ARTIFACTS_BASE).resolve()
UPLOADS_DIR = ARTIFACTS_ROOT / "uploads"

router = APIRouter(prefix="/graphs", tags=["graphs"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class NodeInfo(BaseModel):
    node_id: str
    display_name: str
    category: str
    endpoint: str
    description: str
    inputs: list[str]
    outputs: list[str]
    params: list[str]
    params_schema: dict[str, Any]


class NodesResponse(BaseModel):
    data: list[NodeInfo]
    count: int


class ValidateResponse(BaseModel):
    valid: bool
    node_count: int
    edge_count: int
    ordered_node_ids: list[str]


class RunResponse(BaseModel):
    run_id: str
    status: str


class StatusResponse(BaseModel):
    run_id: str
    status: str
    created_at: str
    updated_at: str
    error: Optional[str] = None
    node_statuses: Optional[dict[str, str]] = None


class ResultResponse(BaseModel):
    run_id: str
    status: str
    result: dict[str, Any]
    node_statuses: dict[str, str]


class UploadResponse(BaseModel):
    path: str
    filename: str


class DatasourceColumnInfo(BaseModel):
    name: str
    type_str: str


class DatasourceInfoResponse(BaseModel):
    key: str
    columns: list[DatasourceColumnInfo]
    query_params: list[str]  # names of accepted kwargs in ds.query()


class WorkflowCreateBody(BaseModel):
    name: str
    description: Optional[str] = None
    graph_spec: str  # JSON string of {nodes, edges}


class WorkflowUpdateBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    graph_spec: Optional[str] = None


class WorkflowSummary(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: str


class WorkflowDetail(WorkflowSummary):
    graph_spec: str


# ---------------------------------------------------------------------------
# GET /graphs/nodes
# ---------------------------------------------------------------------------

@router.get("/nodes", response_model=NodesResponse)
def list_nodes() -> NodesResponse:
    """List all registered node types and their metadata."""
    entries = [NodeInfo(**e.to_dict()) for e in NODE_REGISTRY.list_nodes()]
    return NodesResponse(data=entries, count=len(entries))


# ---------------------------------------------------------------------------
# GET /graphs/datasource-keys
# ---------------------------------------------------------------------------

@router.get("/datasource-keys", response_model=list[str])
def list_datasource_keys() -> list[str]:
    """Return the keys of all registered BaseDatasource instances (e.g. 'yields', 'weather')."""
    from app.ingest.base import BaseDatasource  # local import to avoid circular dep
    return sorted(BaseDatasource._instances.keys())


# ---------------------------------------------------------------------------
# GET /graphs/datasource-info/{key}
# ---------------------------------------------------------------------------

@router.get("/datasource-info/{key}", response_model=DatasourceInfoResponse)
def datasource_info(key: str) -> DatasourceInfoResponse:
    """Return column schema and accepted query parameters for a datasource."""
    from app.ingest.base import BaseDatasource
    ds = BaseDatasource._instances.get(key)
    if ds is None:
        raise HTTPException(status_code=404, detail=f"Datasource '{key}' not found.")
    cols = [
        DatasourceColumnInfo(name=c.name, type_str=c.dtype.__name__ if hasattr(c.dtype, "__name__") else str(c.dtype))
        for c in ds.columns
    ]
    sig = inspect.signature(ds.query)
    query_params = [
        p for p in sig.parameters
        if p not in ("self", "skip", "limit")
    ]
    return DatasourceInfoResponse(key=key, columns=cols, query_params=query_params)


# ---------------------------------------------------------------------------
# POST /graphs/upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """Accept a file upload and store it under artifacts/uploads/. Returns the server path."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS_DIR / (file.filename or "upload.csv")
    contents = await file.read()
    dest.write_bytes(contents)
    return UploadResponse(path=str(dest), filename=dest.name)


# ---------------------------------------------------------------------------
# Saved Workflows CRUD
# ---------------------------------------------------------------------------

@router.get("/workflows", response_model=list[WorkflowSummary])
def list_workflows(session: Session = Depends(get_session)) -> list[WorkflowSummary]:
    """List all saved workflows (without graph_spec payload)."""
    rows = session.exec(select(SavedWorkflow).order_by(SavedWorkflow.updated_at.desc())).all()  # type: ignore[arg-type]
    return [WorkflowSummary(id=r.id, name=r.name, description=r.description, created_at=r.created_at, updated_at=r.updated_at) for r in rows]


@router.post("/workflows", response_model=WorkflowDetail, status_code=201)
def create_workflow(body: WorkflowCreateBody, session: Session = Depends(get_session)) -> WorkflowDetail:
    """Persist a named workflow to the database."""
    now = _dt.utcnow().isoformat()
    wf = SavedWorkflow(
        name=body.name,
        description=body.description,
        graph_spec=body.graph_spec,
        created_at=now,
        updated_at=now,
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return WorkflowDetail(id=wf.id, name=wf.name, description=wf.description, graph_spec=wf.graph_spec, created_at=wf.created_at, updated_at=wf.updated_at)


@router.get("/workflows/{workflow_id}", response_model=WorkflowDetail)
def get_workflow(workflow_id: int, session: Session = Depends(get_session)) -> WorkflowDetail:
    """Fetch a single saved workflow including its graph_spec."""
    wf = session.get(SavedWorkflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found.")
    return WorkflowDetail(id=wf.id, name=wf.name, description=wf.description, graph_spec=wf.graph_spec, created_at=wf.created_at, updated_at=wf.updated_at)


@router.put("/workflows/{workflow_id}", response_model=WorkflowDetail)
def update_workflow(workflow_id: int, body: WorkflowUpdateBody, session: Session = Depends(get_session)) -> WorkflowDetail:
    """Update the name, description, or graph_spec of an existing workflow."""
    wf = session.get(SavedWorkflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found.")
    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.graph_spec is not None:
        wf.graph_spec = body.graph_spec
    wf.updated_at = _dt.utcnow().isoformat()
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return WorkflowDetail(id=wf.id, name=wf.name, description=wf.description, graph_spec=wf.graph_spec, created_at=wf.created_at, updated_at=wf.updated_at)


@router.delete("/workflows/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: int, session: Session = Depends(get_session)) -> None:
    """Delete a saved workflow."""
    wf = session.get(SavedWorkflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found.")
    session.delete(wf)
    session.commit()


# ---------------------------------------------------------------------------
# POST /graphs/validate
# ---------------------------------------------------------------------------

@router.post("/validate", response_model=ValidateResponse)
def validate_graph(spec: GraphSpec) -> ValidateResponse:
    """Validate a graph spec without running it.

    Checks that all node types exist, edge endpoints are valid, and the graph
    contains no cycles.  Returns the topologically-sorted node order on success.
    """
    try:
        plan = GraphBuilder().build(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ValidateResponse(
        valid=True,
        node_count=len(spec.nodes),
        edge_count=len(spec.edges),
        ordered_node_ids=plan.ordered_ids,
    )


# ---------------------------------------------------------------------------
# POST /graphs/run
# ---------------------------------------------------------------------------

@router.post("/run", response_model=RunResponse, status_code=202)
def run_graph(
    spec: GraphSpec,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> RunResponse:
    """Submit a graph for execution.

    The graph is validated synchronously.  If valid, a ``GraphRun`` record is
    created with status ``pending`` and the execution is enqueued as a
    background task.  Returns ``run_id`` immediately — poll ``/{run_id}/status``
    to track progress.
    """
    try:
        GraphBuilder().build(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    run_id = str(uuid.uuid4())
    run = GraphRun(
        run_id=run_id,
        status="pending",
        graph_spec=spec.model_dump_json(),
    )
    session.add(run)
    session.commit()

    background_tasks.add_task(_execute_graph_bg, run_id, spec)
    return RunResponse(run_id=run_id, status="pending")


def _execute_graph_bg(run_id: str, spec: GraphSpec) -> None:
    """Background task: build and execute the graph, then update the DB record."""
    with Session(engine) as session:
        run = session.exec(select(GraphRun).where(GraphRun.run_id == run_id)).first()
        if run is None:
            logger.error("Background task: GraphRun %r not found.", run_id)
            return

        run.status = "running"
        run.updated_at = _dt.utcnow().isoformat()
        session.add(run)
        session.commit()

        try:
            plan = GraphBuilder().build(spec)
            outputs, statuses, timings = _EXECUTOR.execute(plan, run_id)
            run.status = "success"
            run.result = serialize_outputs(outputs, run_id, timings=timings)
            run.node_statuses = json.dumps(statuses)
        except Exception as exc:
            logger.exception("Graph run %r failed.", run_id)
            run.status = "error"
            run.error = str(exc)

        run.updated_at = _dt.utcnow().isoformat()
        session.add(run)
        session.commit()


# ---------------------------------------------------------------------------
# GET /graphs/{run_id}/status
# ---------------------------------------------------------------------------

@router.get("/{run_id}/status", response_model=StatusResponse)
def get_run_status(
    run_id: str,
    session: Session = Depends(get_session),
) -> StatusResponse:
    """Return the current status of a graph run."""
    run = session.exec(select(GraphRun).where(GraphRun.run_id == run_id)).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    node_statuses = json.loads(run.node_statuses) if run.node_statuses else None
    return StatusResponse(
        run_id=run.run_id,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        error=run.error,
        node_statuses=node_statuses,
    )


# ---------------------------------------------------------------------------
# GET /graphs/{run_id}/result
# ---------------------------------------------------------------------------

@router.get("/{run_id}/result", response_model=ResultResponse)
def get_run_result(
    run_id: str,
    session: Session = Depends(get_session),
) -> ResultResponse:
    """Return the outputs of a completed graph run.

    Raises ``409 Conflict`` if the run is still pending or running.
    Raises ``500`` if the run ended in an error.
    """
    run = session.exec(select(GraphRun).where(GraphRun.run_id == run_id)).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    if run.status in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Run is still '{run.status}'. Poll /graphs/{run_id}/status until complete.",
        )
    if run.status == "error":
        raise HTTPException(status_code=500, detail=f"Run failed: {run.error}")

    result = json.loads(run.result) if run.result else {}
    node_statuses = json.loads(run.node_statuses) if run.node_statuses else {}
    return ResultResponse(
        run_id=run.run_id,
        status=run.status,
        result=result,
        node_statuses=node_statuses,
    )


# ---------------------------------------------------------------------------
# GET /graphs/runs  — run history
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    run_id: str
    status: str
    created_at: str
    updated_at: str
    error: Optional[str] = None


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[RunSummary]:
    """Return the most recent graph runs (newest first). Capped at *limit* rows."""
    rows = session.exec(
        select(GraphRun).order_by(GraphRun.created_at.desc()).limit(limit)  # type: ignore[arg-type]
    ).all()
    return [
        RunSummary(
            run_id=r.run_id,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            error=r.error,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /graphs/{run_id}/stream  — SSE live progress
# ---------------------------------------------------------------------------

@router.get("/{run_id}/stream")
def stream_run_status(run_id: str) -> StreamingResponse:
    """Server-Sent Events stream for a graph run.

    Emits a JSON ``data:`` line every 400 ms while the run is pending or
    running, then one final event and closes.

    Event payload::

        {"type": "status", "run_id": "...", "status": "...",
         "node_statuses": {...}, "error": null}

    The frontend can subscribe via ``new EventSource(url)`` and update node
    colours without polling the ``/status`` endpoint.
    """

    async def _generate():
        while True:
            with Session(engine) as session:
                run = session.exec(
                    select(GraphRun).where(GraphRun.run_id == run_id)
                ).first()

            if run is None:
                payload = json.dumps({"type": "error", "message": f"Run '{run_id}' not found."})
                yield f"data: {payload}\n\n"
                return

            node_statuses = json.loads(run.node_statuses) if run.node_statuses else {}
            payload = json.dumps({
                "type": "status",
                "run_id": run_id,
                "status": run.status,
                "node_statuses": node_statuses,
                "error": run.error,
            })
            yield f"data: {payload}\n\n"

            if run.status in ("success", "error"):
                yield f"data: {json.dumps({'type': 'done', 'run_id': run_id})}\n\n"
                return

            await asyncio.sleep(0.4)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# GET /graphs/artifacts/{path}
# ---------------------------------------------------------------------------

@router.get("/artifacts/{path:path}")
def download_artifact(path: str) -> FileResponse:
    """Serve an artifact file by its path relative to the artifacts root.

    The ``resolve()`` + ``startswith`` check guards against path traversal
    attacks (e.g. ``../../etc/passwd``).
    """
    full_path = (ARTIFACTS_ROOT / path).resolve()
    if not str(full_path).startswith(str(ARTIFACTS_ROOT)):
        raise HTTPException(status_code=403, detail="Access denied: path outside artifacts root.")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact '{path}' not found.")
    return FileResponse(str(full_path))
