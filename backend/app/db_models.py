from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime as _datetime


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
