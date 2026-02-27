from app.nodes.base import BaseNode, IOTypes, IOSlot
from pydantic import BaseModel
from typing import Any

class CsvSourceNode(BaseNode):
    node_id = "csv_source"
    display_name = "CSV Source Node"
    description = "Node that reads data from a CSV file and outputs a DataFrame."
    category = "Sources"

    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    # Parameters for the node, such as the file path to read from
    class Params(BaseModel):
        file_path: str
        separator: str = ","
        encoding: str = "utf-8"
    
    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd
        
        try:
            df = pd.read_csv(params.file_path, sep=params.separator, encoding=params.encoding)
            return {"dataframe": df}
        except Exception as e:
            raise RuntimeError(f"Failed to read CSV file at {params.file_path}: {e}")


