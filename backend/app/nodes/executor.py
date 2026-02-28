"""Graph execution engine for MLPlayground.

Defines:
  - GraphSpec, NodeInstance, Edge  — Pydantic schema for a submitted graph
  - ExecutionPlan                  — internal sorted representation
  - GraphBuilder                   — validates a spec and topologically sorts it
  - NodeExecutor                   — runs the plan, passes outputs between nodes,
                                     and maintains a content-addressable cache
  - serialize_outputs              — converts in-memory outputs to a JSON string
                                     for database storage
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _artifacts_base() -> str:
    """Return the configured artifacts root, read lazily to avoid import-time issues."""
    try:
        from app.core.config import settings
        return settings.ARTIFACTS_BASE
    except Exception:  # pragma: no cover
        return os.environ.get("ARTIFACTS_BASE", "/app/artifacts")


def _cache_dir() -> str:
    return os.path.join(_artifacts_base(), "cache")


# ---------------------------------------------------------------------------
# Graph schema (the JSON a client posts to POST /graphs/run)
# ---------------------------------------------------------------------------

class NodeInstance(BaseModel):
    """A node placed in a graph, identified by a unique instance_id."""
    instance_id: str
    node_type: str
    params: dict[str, Any] = {}
    bypassed: bool = False


class Edge(BaseModel):
    """A directed wiring from one node's output slot to another's input slot."""
    source_instance_id: str
    source_slot: str
    target_instance_id: str
    target_slot: str


class GraphSpec(BaseModel):
    """Complete description of a graph: nodes + edges."""
    nodes: list[NodeInstance]
    edges: list[Edge]


# ---------------------------------------------------------------------------
# ExecutionPlan — internal, produced by GraphBuilder
# ---------------------------------------------------------------------------

class ExecutionPlan:
    """Topologically-ordered execution plan for a validated GraphSpec."""

    def __init__(
        self,
        ordered_ids: list[str],
        node_map: dict[str, NodeInstance],
        edge_map: dict[str, list[Edge]],
    ) -> None:
        self.ordered_ids = ordered_ids   # instance_ids in execution order
        self.node_map = node_map         # instance_id → NodeInstance
        self.edge_map = edge_map         # target instance_id → edges feeding into it


# ---------------------------------------------------------------------------
# GraphBuilder — validation + topological sort
# ---------------------------------------------------------------------------

class GraphBuilder:
    """Validates a GraphSpec and returns an ExecutionPlan."""

    def build(self, spec: GraphSpec) -> ExecutionPlan:
        from app.nodes.registry import NODE_REGISTRY

        node_map = {n.instance_id: n for n in spec.nodes}

        # Validate every node type is registered
        for node in spec.nodes:
            if NODE_REGISTRY.get(node.node_type) is None:
                raise ValueError(
                    f"Unknown node type: {node.node_type!r}. "
                    f"Known types: {[e.node_id for e in NODE_REGISTRY.list_nodes()]}"
                )

        # Build adjacency structures
        in_degree: dict[str, int] = {n.instance_id: 0 for n in spec.nodes}
        adjacency: dict[str, list[str]] = {n.instance_id: [] for n in spec.nodes}
        edge_map: dict[str, list[Edge]] = {n.instance_id: [] for n in spec.nodes}

        for edge in spec.edges:
            if edge.source_instance_id not in node_map:
                raise ValueError(
                    f"Edge references unknown source node: {edge.source_instance_id!r}"
                )
            if edge.target_instance_id not in node_map:
                raise ValueError(
                    f"Edge references unknown target node: {edge.target_instance_id!r}"
                )
            adjacency[edge.source_instance_id].append(edge.target_instance_id)
            edge_map[edge.target_instance_id].append(edge)
            in_degree[edge.target_instance_id] += 1

        # Kahn's topological sort
        queue: collections.deque[str] = collections.deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        ordered: list[str] = []
        while queue:
            nid = queue.popleft()
            ordered.append(nid)
            for neighbor in adjacency[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(spec.nodes):
            raise ValueError(
                "Graph contains a cycle — execution order is undefined. "
                "Ensure all edges point forward (no node can depend on its own output)."
            )

        return ExecutionPlan(ordered_ids=ordered, node_map=node_map, edge_map=edge_map)


# ---------------------------------------------------------------------------
# Value serialization helpers
# ---------------------------------------------------------------------------

def _serialize_value(value: Any, run_id: str, instance_id: str, slot: str) -> Any:
    """Convert a node output to a JSON-serializable form.

    DataFrames are written to parquet in artifacts/cache/ and replaced with a
    reference dict that also embeds the first 20 rows for inline preview.
    sklearn-compatible models are written with joblib.
    Everything else is returned unchanged (must already be JSON-serializable).
    """
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            cache_dir = _cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            path = os.path.join(cache_dir, f"{run_id}__{instance_id}__{slot}.parquet")
            value.to_parquet(path, index=False)
            preview_rows = value.head(20).to_dict(orient="records")
            return {
                "__type__": "dataframe",
                "path": path,
                "shape": list(value.shape),
                "columns": list(value.columns),
                "preview_rows": preview_rows,
            }
    except ImportError:
        pass

    if hasattr(value, "predict") and hasattr(value, "fit"):
        import joblib
        cache_dir = _cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{run_id}__{instance_id}__{slot}.pkl")
        joblib.dump(value, path)
        return {"__type__": "model", "path": path}

    return value


def _deserialize_value(value: Any) -> Any:
    """Reverse of _serialize_value — loads parquet/joblib references."""
    if not isinstance(value, dict):
        return value
    t = value.get("__type__")
    if t == "dataframe":
        import pandas as pd
        return pd.read_parquet(value["path"])
    if t == "model":
        import joblib
        return joblib.load(value["path"])
    return value


def serialize_outputs(
    outputs: dict[str, dict[str, Any]],
    run_id: str,
    timings: dict[str, float] | None = None,
) -> str:
    """Serialize all node outputs to a JSON string for database storage.

    If *timings* is provided it is injected as ``"_timings_"`` at the top
    level of the result JSON so the frontend execution-log drawer can read it.
    """
    result: dict[str, dict[str, Any]] = {}
    for instance_id, slots in outputs.items():
        result[instance_id] = {
            slot: _serialize_value(val, run_id, instance_id, slot)
            for slot, val in slots.items()
        }
    if timings is not None:
        result["_timings_"] = timings  # type: ignore[assignment]
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Content-addressable hash
# ---------------------------------------------------------------------------

def _node_hash(node_type: str, params: dict, input_hashes: dict[str, str]) -> str:
    """Hash a node's configuration plus its upstream output hashes.

    Using sort_keys=True ensures the same dict always produces the same string
    regardless of insertion order.
    """
    payload = {"node_type": node_type, "params": params, "inputs": input_hashes}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# NodeExecutor
# ---------------------------------------------------------------------------

class NodeExecutor:
    """Executes an ExecutionPlan, supporting content-addressable caching.

    The cache maps a node's content hash to its serialized outputs.  If the
    hash is present, the node is skipped and cached outputs are returned
    immediately.  This allows partial re-execution: only nodes downstream of
    changed inputs are re-run.
    """

    def __init__(self) -> None:
        # In-memory cache: node_hash → {slot: serialized_value}
        self._cache: dict[str, dict[str, Any]] = {}

    def execute(
        self,
        plan: ExecutionPlan,
        run_id: str,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, float]]:
        """Execute all nodes in topological order.

        Returns
        -------
        outputs : dict[instance_id, dict[slot, value]]
            Live Python objects passed between nodes.
        statuses : dict[instance_id, str]
            "success", "cached", "bypassed", or "error: <message>" per node.
        timings : dict[instance_id, float]
            Wall-clock seconds spent in each node's ``run()`` call.
            Bypassed and cached nodes get 0.0.
        """
        from app.nodes.base import BaseNode

        outputs: dict[str, dict[str, Any]] = {}
        hashes: dict[str, str] = {}
        statuses: dict[str, str] = {}
        timings: dict[str, float] = {}

        for instance_id in plan.ordered_ids:
            node_inst = plan.node_map[instance_id]
            incoming = plan.edge_map[instance_id]

            # Wire inputs from upstream outputs
            node_inputs: dict[str, Any] = {}
            input_hashes: dict[str, str] = {}
            for edge in incoming:
                upstream_slots = outputs.get(edge.source_instance_id, {})
                node_inputs[edge.target_slot] = upstream_slots.get(edge.source_slot)
                input_hashes[edge.target_slot] = hashes.get(edge.source_instance_id, "")

            # ── Bypass: pass the first upstream input straight through ──────
            if node_inst.bypassed:
                # Discover what output slot names this node normally produces
                node_obj = BaseNode._instances.get(node_inst.node_type)
                output_slot_names: list[str] = (
                    [s.name for s in node_obj.outputs]
                    if node_obj and node_obj.outputs
                    else list(node_inputs.keys())  # fallback: mirror input slots
                )
                # Use the first available upstream value as the pass-through value
                passthrough = next(iter(node_inputs.values()), None)
                bypass_outputs = {slot: passthrough for slot in output_slot_names}
                outputs[instance_id] = bypass_outputs
                hashes[instance_id] = _node_hash(node_inst.node_type, {"bypassed": True}, input_hashes)
                statuses[instance_id] = "bypassed"
                timings[instance_id] = 0.0
                logger.debug("Bypassed node %r, passing through %d slot(s)", instance_id, len(bypass_outputs))
                continue

            # Compute cache key
            node_h = _node_hash(node_inst.node_type, node_inst.params, input_hashes)

            if node_h in self._cache:
                cached_raw = self._cache[node_h]
                outputs[instance_id] = {
                    k: _deserialize_value(v) for k, v in cached_raw.items()
                }
                hashes[instance_id] = node_h
                statuses[instance_id] = "cached"
                timings[instance_id] = 0.0
                logger.debug("Cache hit: %r (hash %s…)", instance_id, node_h[:8])
                continue

            # Instantiate params
            node_obj = BaseNode._instances.get(node_inst.node_type)
            if node_obj is None:
                raise ValueError(
                    f"Node type {node_inst.node_type!r} registered but has no instance."
                )
            params_cls = getattr(type(node_obj), "params", None)
            if isinstance(params_cls, type) and issubclass(params_cls, BaseModel):
                try:
                    params_obj = params_cls(**node_inst.params)
                except Exception as exc:
                    raise ValueError(
                        f"Invalid params for node '{instance_id}' "
                        f"({node_inst.node_type}): {exc}"
                    ) from exc
            else:
                params_obj = BaseModel()

            # Run
            try:
                _t0 = time.perf_counter()
                result = node_obj.run(inputs=node_inputs, params=params_obj)
                timings[instance_id] = round(time.perf_counter() - _t0, 3)
                outputs[instance_id] = result
                hashes[instance_id] = node_h
                statuses[instance_id] = "success"
                # Cache serialized form
                self._cache[node_h] = {
                    k: _serialize_value(v, run_id, instance_id, k)
                    for k, v in result.items()
                }
            except Exception as exc:
                timings[instance_id] = round(time.perf_counter() - _t0, 3)
                statuses[instance_id] = f"error: {exc}"
                raise RuntimeError(
                    f"Node '{instance_id}' ({node_inst.node_type}) failed: {exc}"
                ) from exc

        return outputs, statuses, timings


# Shared executor instance — cache persists for the process lifetime
_EXECUTOR = NodeExecutor()
