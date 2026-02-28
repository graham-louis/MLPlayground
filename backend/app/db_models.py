from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime as _datetime


def _now() -> str:
    return _datetime.utcnow().isoformat()


# --- Model Run (persisted training artifact) ---

class ModelRunBase(SQLModel):
    run_id: str                             # UUID string
    model_type: str
    datasources: str                        # JSON list, e.g. '["yields","weather","soil"]'
    join_keys: str                          # JSON list, e.g. '["year","state","county"]'
    feature_columns: str                    # JSON list
    target_column: str
    filters: str                            # JSON object, e.g. '{"state":"Iowa","crop":"CORN"}'
    r2: Optional[float] = None
    rmse: Optional[float] = None
    n_samples: Optional[int] = None
    artifact_path: Optional[str] = None    # path to .pkl file on disk
    created_at: str = Field(
        default_factory=lambda: _datetime.utcnow().isoformat()
    )


class ModelRun(ModelRunBase, table=True):
    __tablename__ = "model_runs"
    id: Optional[int] = Field(default=None, primary_key=True)


class ModelRunPublic(ModelRunBase):
    id: int


class ModelRunsPublic(SQLModel):
    data: list[ModelRunPublic]
    count: int

# Generic message
class Message(SQLModel):
    message: str


# ---------------------------------------------------------------------------
# Graph Run — tracks execution of a submitted graph
# ---------------------------------------------------------------------------

class GraphRunBase(SQLModel):
    run_id: str                             # UUID string
    status: str = "pending"                 # pending / running / success / error
    graph_spec: str                         # JSON of GraphSpec
    result: Optional[str] = None            # JSON of serialized outputs; set on success
    error: Optional[str] = None             # Error message; set on failure
    node_statuses: Optional[str] = None     # JSON dict of per-node statuses
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class GraphRun(GraphRunBase, table=True):
    __tablename__ = "graph_runs"
    id: Optional[int] = Field(default=None, primary_key=True)


class GraphRunPublic(GraphRunBase):
    id: int


# ---------------------------------------------------------------------------
# Saved Workflow — user-named graph specs persisted in the database
# ---------------------------------------------------------------------------

class SavedWorkflowBase(SQLModel):
    name: str
    description: Optional[str] = None
    graph_spec: str                         # JSON of {nodes: [...], edges: [...]}
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class SavedWorkflow(SavedWorkflowBase, table=True):
    __tablename__ = "saved_workflows"
    id: Optional[int] = Field(default=None, primary_key=True)


class SavedWorkflowPublic(SavedWorkflowBase):
    id: int
