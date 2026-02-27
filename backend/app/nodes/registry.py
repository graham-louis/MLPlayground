"""
Node registry for the application. 

This module provides a centralized registry for all nodes in the application, 
allowing for easy management and retrieval of node instances. 
The registry supports adding, removing, and retrieving nodes by their unique identifiers.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DatasourceEntry:
    """Metadata and callable for a single registered node."""

    def __init__(
        self,
        node_id: str,
        display_name: str,
        endpoint: str,
        description: str = "",
        inputs: Optional[list[str]] = None,
        outputs: Optional[list[str]] = None,
        params: Optional[list[str]] = None,
        run_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.node_id = node_id
        self.display_name = display_name
        self.endpoint = endpoint
        self.description = description
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.params = params or []
        self.run_fn = run_fn

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "display_name": self.display_name,
            "endpoint": self.endpoint,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "params": self.params,
        }
    
class NodeRegistry:
    """Central registry for all node modules."""

    def __init__(self) -> None:
        self._entries: dict[str, DatasourceEntry] = {}

    def register(
        self,
        node_id: str,
        display_name: str,
        endpoint: str,
        description: str = "",
        inputs: Optional[list[str]] = None,
        outputs: Optional[list[str]] = None,
        params: Optional[list[str]] = None,
        run_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        if node_id in self._entries:
            logger.warning(f"Overwriting existing node with id '{node_id}' in registry.")
        self._entries[node_id] = DatasourceEntry(
            node_id=node_id,
            display_name=display_name,
            endpoint=endpoint,
            description=description,
            inputs=inputs,
            outputs=outputs,
            params=params,
            run_fn=run_fn
        )
        logger.debug("NodeRegistry: registered node key=%r", node_id)

    def get(self, node_id: str) -> Optional[DatasourceEntry]:
        return self._entries.get(node_id)
    
    def list_nodes(self) -> list[DatasourceEntry]:
        return list(self._entries.values())
    
# Create a global instance of the registry that can be imported and used throughout the app
NODE_REGISTRY = NodeRegistry()