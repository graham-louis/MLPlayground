"""Base class for all nodes"""
from __future__ import annotations
from typing import Literal, TypedDict, Optional, Any
from abc import ABC, abstractmethod
from enum import Enum
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class IOTypes(str, Enum):
    NUMERIC = "NUMERIC"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    DATAFRAME = "DATAFRAME"
    MODEL = "MODEL"
    ARTIFACT = "ARTIFACT"

class IOSlot:
    def __init__(self, 
                 name: str, 
                 type: IOTypes,
                #  tool_tip: str,
                 required: bool = True) -> None:
        self.name = name
        self.type = type
        # self.tool_tip = tool_tip
        self.required = required

class BaseNode(ABC):
    """Abstract base class for nodes. Includes the names and expected types of attributes."""
    node_id: str
    """Unique identifier for the node, used for registration and lookup."""
    display_name: str
    """Human-friendly name for the node, shown in the UI."""
    description: str
    """Detailed description of the node's functionality."""
    category: str
    """Category for grouping similar nodes in the UI."""

    inputs: list[IOSlot] = []
    """Expected input slots for the node, defined as a list of IOSlot instances."""
    outputs: list[IOSlot] = []
    """Expected output slots for the node, defined as a list of IOSlot instances."""
    params: BaseModel = BaseModel
    """Expected parameter slots for the node, defined as a Pydantic BaseModel subclass."""

    # Registry of all node instances, keyed by node_id
    _instances: dict[str, "BaseNode"] = {}

    # Automatically register subclasses in the node registry on definition
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)  # Call the parent method to ensure proper initialization
        if not getattr(cls, "node_id", ""):
            return  # Skip abstract base class without node_id
        instance = cls()  # Create an instance of the subclass
        BaseNode._instances[cls.node_id] = instance  # Register the instance in the class-level registry

        # Also register with the central NODE_REGISTRY so GET /nodes can discover it.
        # Imported inside the method to avoid a circular import at module load time.
        try:
            from app.nodes.registry import NODE_REGISTRY
            # Extract the JSON schema from the Pydantic params model so the frontend
            # can render a typed form for each node's configuration.
            params_cls = getattr(cls, "params", None)
            params_schema: dict = {}
            if isinstance(params_cls, type) and issubclass(params_cls, BaseModel):
                params_schema = params_cls.model_json_schema()

            NODE_REGISTRY.register(
                node_id=cls.node_id,
                display_name=getattr(cls, "display_name", cls.node_id),
                category=getattr(cls, "category", "Unknown"),
                endpoint=f"/api/v1/graphs/execute/{cls.node_id}",
                description=getattr(cls, "description", ""),
                inputs=[s.name for s in getattr(cls, "inputs", [])],
                outputs=[s.name for s in getattr(cls, "outputs", [])],
                params=[],
                params_schema=params_schema,
                run_fn=instance.run,
            )
            logger.debug("BaseNode: registered node_id=%r", cls.node_id)
        except Exception as exc:
            logger.warning("BaseNode: failed to register node_id=%r: %s", cls.node_id, exc)


    @abstractmethod
    def run(self, inputs: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        """Run the node's logic. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement the run() method.")






