"""API routes related to graph management and node execution.
This module defines endpoints for listing available nodes and executing them with specified inputs and parameters.
Endpoints:
- GET /api/v1/graphs/nodes: List all registered nodes with their metadata.
- POST /api/v1/graphs/execute/{node_id}: Execute a specific node with given inputs and parameters.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

from app.nodes.registry import NODE_REGISTRY

router = APIRouter(prefix="/graphs", tags=["graphs"])

class NodeInfo(BaseModel):
    node_id: str
    display_name: str
    endpoint: str
    description: str
    inputs: list[str]
    outputs: list[str]
    params: list[str]

class NodesResponse(BaseModel):
    data: list[NodeInfo]
    count: int

@router.get("/nodes")
def list_nodes():
    """
    List all registered nodes.

    Returns metadata for each node:
    - **node_id**: machine-readable identifier (e.g. ``"csv_source"``)
    - **display_name**: human-readable name shown in the UI
    - **endpoint**: API path to execute the node (e.g. ``"/api/v1/execute/csv_source"``)
    - **description**: short text describing the node
    - **inputs**: list of input slot names
    - **outputs**: list of output slot names
    - **params**: list of parameter names that can be configured when executing the node
    """
    entries = [NodeInfo(**e.to_dict()) for e in NODE_REGISTRY.list_nodes()]
    return NodesResponse(data=entries, count=len(entries))


