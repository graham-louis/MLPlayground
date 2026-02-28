"""
Tests for the Yield Prediction graph workflow.

These tests verify the graph topology (structure + topological order) and
functional correctness using synthetic in-memory DataFrames — no real
database or external API calls are needed.
"""
from __future__ import annotations

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers to construct the yield prediction GraphSpec
# ---------------------------------------------------------------------------

def build_yield_prediction_spec():
    """Return a GraphSpec matching the Yield Prediction template in graph.tsx."""
    import app.nodes.node_sources   # noqa: F401 — registers csv_source, database_source
    import app.nodes.node_transforms  # noqa: F401 — registers join, select_columns, drop_na
    import app.nodes.node_modeling   # noqa: F401 — registers trainer
    from app.nodes.executor import GraphSpec, NodeInstance, Edge

    nodes = [
        NodeInstance(instance_id="t1", node_type="database_source",
                     params={"datasource_key": "yields", "filters_json": "{}", "limit": 5000}),
        NodeInstance(instance_id="t2", node_type="database_source",
                     params={"datasource_key": "weather", "filters_json": "{}", "limit": 5000}),
        NodeInstance(instance_id="t3", node_type="database_source",
                     params={"datasource_key": "soil", "filters_json": "{}", "limit": 5000}),
        NodeInstance(instance_id="t4", node_type="join",
                     params={"on": ["year", "state", "county"], "how": "inner"}),
        NodeInstance(instance_id="t5", node_type="join",
                     params={"on": ["state", "county"], "how": "left"}),
        NodeInstance(instance_id="t6", node_type="select_columns",
                     params={"columns": ["year", "state", "county", "crop", "value",
                                         "avg_temp", "precipitation", "gdd",
                                         "ph", "organic_matter", "sand_pct", "clay_pct"]}),
        NodeInstance(instance_id="t7", node_type="drop_na", params={"columns": []}),
        NodeInstance(instance_id="t9", node_type="trainer",
                     params={
                         "model_type": "random_forest",
                         "target_column": "value",
                         "feature_columns": ["avg_temp", "precipitation", "gdd",
                                              "ph", "organic_matter", "sand_pct", "clay_pct"],
                         "test_size": 0.2,
                         "random_state": 42,
                     }),
    ]
    edges = [
        Edge(source_instance_id="t1", source_slot="dataframe",
             target_instance_id="t4", target_slot="left"),
        Edge(source_instance_id="t2", source_slot="dataframe",
             target_instance_id="t4", target_slot="right"),
        Edge(source_instance_id="t4", source_slot="dataframe",
             target_instance_id="t5", target_slot="left"),
        Edge(source_instance_id="t3", source_slot="dataframe",
             target_instance_id="t5", target_slot="right"),
        Edge(source_instance_id="t5", source_slot="dataframe",
             target_instance_id="t6", target_slot="dataframe"),
        Edge(source_instance_id="t6", source_slot="dataframe",
             target_instance_id="t7", target_slot="dataframe"),
        Edge(source_instance_id="t7", source_slot="dataframe",
             target_instance_id="t9", target_slot="dataframe"),
    ]
    return GraphSpec(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Topology tests (no DB, no side effects)
# ---------------------------------------------------------------------------

class TestYieldPredictionTopology:
    """Verify graph structure is valid and produces correct topological order."""

    def test_graph_builds_without_error(self):
        from app.nodes.executor import GraphBuilder
        spec = build_yield_prediction_spec()
        plan = GraphBuilder().build(spec)
        assert plan is not None

    def test_all_eight_nodes_included(self):
        from app.nodes.executor import GraphBuilder
        spec = build_yield_prediction_spec()
        plan = GraphBuilder().build(spec)
        assert len(plan.ordered_ids) == 8

    def test_sources_come_before_joins(self):
        from app.nodes.executor import GraphBuilder
        spec = build_yield_prediction_spec()
        plan = GraphBuilder().build(spec)
        order = plan.ordered_ids
        # t1, t2, t3 must all appear before t4 and t5
        for src in ("t1", "t2", "t3"):
            assert order.index(src) < order.index("t4"), f"{src} must precede t4"
        assert order.index("t4") < order.index("t5"), "t4 must precede t5"

    def test_pipeline_order_is_correct(self):
        from app.nodes.executor import GraphBuilder
        spec = build_yield_prediction_spec()
        plan = GraphBuilder().build(spec)
        order = plan.ordered_ids
        # The linear portion: t5 → t6 → t7 → t9
        for pred, succ in [("t5", "t6"), ("t6", "t7"), ("t7", "t9")]:
            assert order.index(pred) < order.index(succ), f"{pred} must precede {succ}"

    def test_trainer_is_last(self):
        from app.nodes.executor import GraphBuilder
        spec = build_yield_prediction_spec()
        plan = GraphBuilder().build(spec)
        # t9 (trainer) must be the final node in execution order
        assert plan.ordered_ids[-1] == "t9"

    def test_no_cycle_in_graph(self):
        """GraphBuilder raises ValueError on cyclic graphs; absence of error confirms DAG."""
        from app.nodes.executor import GraphBuilder
        spec = build_yield_prediction_spec()
        plan = GraphBuilder().build(spec)
        assert len(plan.ordered_ids) == len(spec.nodes)


# ---------------------------------------------------------------------------
# Functional tests (synthetic data, no DB)
# ---------------------------------------------------------------------------

@pytest.fixture()
def synthetic_frames():
    """Small synthetic DataFrames that mimic yields, weather, and soil shapes."""
    counties = ["Alamance", "Durham", "Wake", "Orange", "Chatham",
                "Guilford", "Forsyth", "Mecklenburg", "Cabarrus", "Union"]
    years = [2019, 2020, 2021]

    yields_rows = [
        {"year": y, "state": "NC", "county": c, "crop": "CORN",
         "value": 110.0 + i * 3 + y - 2019}
        for i, c in enumerate(counties) for y in years
    ]
    weather_rows = [
        {"year": y, "state": "NC", "county": c,
         "avg_temp": 20.0 + i * 0.5,
         "precipitation": 700.0 + i * 10,
         "gdd": 1400.0 + i * 20,
         "vp": 1.0 + i * 0.05,
         "srad": 190.0 + i * 2}
        for i, c in enumerate(counties) for y in years
    ]
    soil_rows = [
        {"state": "NC", "county": c,
         "ph": 6.0 + i * 0.05,
         "organic_matter": 2.0 + i * 0.05,
         "sand_pct": 40.0 + i,
         "clay_pct": 20.0 + i * 0.5}
        for i, c in enumerate(counties)
    ]

    return pd.DataFrame(yields_rows), pd.DataFrame(weather_rows), pd.DataFrame(soil_rows)


def test_join_yields_and_weather(synthetic_frames):
    """Inner join on year/state/county produces correct row count and columns."""
    yields_df, weather_df, _ = synthetic_frames
    merged = yields_df.merge(weather_df, on=["year", "state", "county"], how="inner")
    # 10 counties × 3 years = 30 rows
    assert len(merged) == 30
    assert "avg_temp" in merged.columns
    assert "value" in merged.columns


def test_join_with_soil_left(synthetic_frames):
    """Left join with soil on state/county preserves all weather+yield rows."""
    yields_df, weather_df, soil_df = synthetic_frames
    step1 = yields_df.merge(weather_df, on=["year", "state", "county"], how="inner")
    step2 = step1.merge(soil_df, on=["state", "county"], how="left")
    assert len(step2) == 30
    assert "ph" in step2.columns
    assert "sand_pct" in step2.columns


def test_select_columns_keeps_training_features(synthetic_frames):
    """select_columns retains exactly the specified feature + target columns."""
    yields_df, weather_df, soil_df = synthetic_frames
    merged = (yields_df
              .merge(weather_df, on=["year", "state", "county"])
              .merge(soil_df, on=["state", "county"], how="left"))

    keep = ["year", "state", "county", "crop", "value",
            "avg_temp", "precipitation", "gdd", "ph", "organic_matter", "sand_pct", "clay_pct"]
    result = merged[keep]
    assert list(result.columns) == keep
    assert len(result) == 30


def test_drop_na_removes_rows_with_missing_values(synthetic_frames):
    """drop_na (no column subset) removes rows that have any NaN."""
    yields_df, weather_df, soil_df = synthetic_frames
    merged = (yields_df
              .merge(weather_df, on=["year", "state", "county"])
              .merge(soil_df, on=["state", "county"], how="left"))
    keep = ["year", "state", "county", "crop", "value",
            "avg_temp", "precipitation", "gdd", "ph", "organic_matter", "sand_pct", "clay_pct"]
    selected = merged[keep]
    # Inject a NaN row to confirm drop_na removes it
    row_with_nan = selected.iloc[[0]].copy()
    row_with_nan["ph"] = float("nan")
    with_nan = pd.concat([selected, row_with_nan], ignore_index=True)
    cleaned = with_nan.dropna()
    assert len(cleaned) == len(selected)


def test_trainer_runs_on_synthetic_data(synthetic_frames, tmp_path, monkeypatch):
    """TrainerNode trains a random forest on synthetic data and returns valid metrics."""
    import app.nodes.node_modeling  # noqa: F401

    yields_df, weather_df, soil_df = synthetic_frames
    merged = (yields_df
              .merge(weather_df, on=["year", "state", "county"])
              .merge(soil_df, on=["state", "county"], how="left"))
    keep = ["value", "avg_temp", "precipitation", "gdd", "ph", "organic_matter", "sand_pct", "clay_pct"]
    df = merged[keep].dropna()

    # Patch ARTIFACTS_BASE so the trainer saves to a temp directory
    monkeypatch.setenv("ARTIFACTS_BASE", str(tmp_path))
    import app.nodes.executor as exec_module
    monkeypatch.setattr(exec_module, "ARTIFACTS_BASE", str(tmp_path))

    from app.nodes.base import BaseNode
    trainer_obj = BaseNode._instances.get("trainer")
    assert trainer_obj is not None, "trainer node not registered — import node_modeling first"

    TrainerParams = type(trainer_obj).params
    params_obj = TrainerParams(
        model_type="random_forest",
        target_column="value",
        feature_columns=["avg_temp", "precipitation", "gdd",
                          "ph", "organic_matter", "sand_pct", "clay_pct"],
        test_size=0.2,
        random_state=42,
    )
    result = trainer_obj.run(inputs={"dataframe": df}, params=params_obj)

    assert "model" in result, "trainer must output a model"
    assert "metrics" in result, "trainer must output metrics"
    metrics = result["metrics"]
    assert "r2" in metrics or "rmse" in metrics or "mae" in metrics, \
        f"Expected at least one regression metric, got: {list(metrics.keys())}"
    assert result["model"] is not None
