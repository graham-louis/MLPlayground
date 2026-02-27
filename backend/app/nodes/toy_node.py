from app.nodes.base import BaseNode, IOTypes, IOSlot
from typing import Any

class ToyNode(BaseNode):
    node_id = "toy_node"
    display_name = "Toy Node"
    description = "A simple toy node that demonstrates the structure of a node."
    category = "Example"

    inputs = [
        IOSlot(name = "x", type=IOTypes.NUMERIC),
        IOSlot(name="y", type=IOTypes.NUMERIC)
    ]
    outputs = [IOSlot(name = "result", type=IOTypes.NUMERIC)]

    def run(self, inputs: dict[str, float], params: dict[str, Any]) -> dict[str, float]:
        x = inputs["x"]
        y = inputs["y"]
        result = x + y  # Simple logic for demonstration
        return {"result": result}
    

def test_toy_node():
    node = ToyNode()
    node_inputs = {"x": 2, "y": 3}
    result = node.run(node_inputs, params={})["result"]
    assert result == 5, f"Expected 5 but got {result}"
    if result == 5:
        print("ToyNode test passed!")


if __name__ == "__main__":    
    test_toy_node()