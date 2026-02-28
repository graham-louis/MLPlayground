from app.nodes.base import BaseNode, IOTypes, IOSlot
from typing import Any, Optional
from pydantic import BaseModel


class ToyNodeParams(BaseModel):
    """Parameters for ToyNode — both addends can also be supplied as params
    instead of (or as a fallback for) wired inputs."""
    x: Optional[float] = None
    y: Optional[float] = None


class ToyNode(BaseNode):
    node_id = "toy_node"
    display_name = "Toy Node"
    description = "Adds two numbers together.  Wire numeric inputs or set params."
    category = "Example"

    inputs = [
        IOSlot(name="x", type=IOTypes.NUMERIC, required=False),
        IOSlot(name="y", type=IOTypes.NUMERIC, required=False),
    ]
    outputs = [IOSlot(name="result", type=IOTypes.NUMERIC)]
    params = ToyNodeParams

    def run(self, inputs: dict[str, Any], params: ToyNodeParams) -> dict[str, float]:
        # Wired inputs take priority; fall back to params.
        x = float(inputs.get("x") if inputs.get("x") is not None else (params.x or 0))
        y = float(inputs.get("y") if inputs.get("y") is not None else (params.y or 0))
        return {"result": x + y}
    

def test_toy_node():
    node = ToyNode()
    node_inputs = {"x": 2, "y": 3}
    result = node.run(node_inputs, params={})["result"]
    assert result == 5, f"Expected 5 but got {result}"
    if result == 5:
        print("ToyNode test passed!")


if __name__ == "__main__":    
    test_toy_node()