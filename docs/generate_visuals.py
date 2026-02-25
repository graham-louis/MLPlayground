"""
generate_visuals.py
-------------------
Generates 30 poster-presentation visuals for MLPlayground.

Run from the repository root:
    python docs/generate_visuals.py

All PNGs are saved to docs/visuals/.
"""

import os
import warnings
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.gridspec import GridSpec
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

OUT_DIR = os.path.join(os.path.dirname(__file__), "visuals")
os.makedirs(OUT_DIR, exist_ok=True)

# ── shared style ──────────────────────────────────────────────────────────────
PALETTE = {
    "green": "#2e7d32",
    "teal": "#00695c",
    "blue": "#1565c0",
    "orange": "#e65100",
    "purple": "#6a1b9a",
    "grey": "#546e7a",
    "light": "#f5f5f5",
    "dark": "#212121",
    "accent": "#f9a825",
}
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "crop_yield_1980-2022.csv")


def save(fig: plt.Figure, name: str) -> None:
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {path}")


# ── helpers ───────────────────────────────────────────────────────────────────

def load_csv() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, index_col=0)
    df.columns = df.columns.str.strip()
    # Keep only rows with a valid numeric yield
    df = df[pd.to_numeric(df["YIELD_LBS_PER_ACRE"], errors="coerce").notna()].copy()
    df["YIELD_LBS_PER_ACRE"] = df["YIELD_LBS_PER_ACRE"].astype(float)
    df["Year"] = df["Year"].astype(int)
    return df


def box(ax, text, xy, w=0.18, h=0.08, color="#1565c0", fontsize=9, textcolor="white"):
    x, y = xy
    rect = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.01",
        linewidth=1.2,
        edgecolor="white",
        facecolor=color,
    )
    ax.add_patch(rect)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color=textcolor, fontweight="bold", wrap=True,
            multialignment="center")


def arrow(ax, src, dst, color="#546e7a"):
    ax.annotate(
        "", xy=dst, xytext=src,
        arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. System Architecture
# ══════════════════════════════════════════════════════════════════════════════
def fig01_system_architecture():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_facecolor(PALETTE["light"])
    ax.set_title("MLPlayground – System Architecture", fontsize=16, fontweight="bold", pad=14)

    layers = [
        ("DATA SOURCES", 0.88, ["USDA NASS\n(Yields)", "NASA NLDAS\n(Weather)", "SSURGO\n(Soil)"], "#2e7d32"),
        ("INGESTION / ETL", 0.68, ["ETL Scripts\n(backend/)", "Feature Eng.\n(GDD, Aggregates)", "DB Writers\n(SQLAlchemy)"], "#1565c0"),
        ("STORAGE", 0.48, ["PostgreSQL\n(yields)", "PostgreSQL\n(weather)", "PostgreSQL\n(soil)"], "#6a1b9a"),
        ("API LAYER", 0.30, ["FastAPI /yields", "FastAPI /weather", "FastAPI /soil"], "#e65100"),
        ("UI LAYER", 0.12, ["Streamlit\nData Select", "Streamlit\nModel", "Streamlit\nExplain"], "#00695c"),
    ]

    xs = [0.22, 0.50, 0.78]
    for label, y, boxes, color in layers:
        ax.text(0.02, y, label, fontsize=8, color=PALETTE["grey"],
                va="center", fontweight="bold")
        for x, text in zip(xs, boxes):
            box(ax, text, (x, y), w=0.22, h=0.10, color=color, fontsize=8)

    # vertical arrows between layers
    for (_l1, y1, _b1, _c1), (_l2, y2, _b2, _c2) in zip(layers, layers[1:]):
        for x in xs:
            arrow(ax, (x, y1 - 0.05), (x, y2 + 0.05))

    save(fig, "01_system_architecture.png")


# ══════════════════════════════════════════════════════════════════════════════
# 2. End-to-end Data Pipeline Flowchart
# ══════════════════════════════════════════════════════════════════════════════
def fig02_data_pipeline():
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("End-to-End Data Pipeline", fontsize=15, fontweight="bold")

    steps = [
        ("Raw Data\nSources", 0.08, PALETTE["green"]),
        ("Ingestion\n& ETL", 0.24, PALETTE["blue"]),
        ("PostgreSQL\nDatabase", 0.40, PALETTE["purple"]),
        ("FastAPI\nEndpoints", 0.56, PALETTE["orange"]),
        ("Streamlit\nUI", 0.72, PALETTE["teal"]),
        ("Model\nTraining", 0.88, PALETTE["blue"]),
    ]
    for text, x, color in steps:
        box(ax, text, (x, 0.5), w=0.13, h=0.35, color=color, fontsize=9)
    for i in range(len(steps) - 1):
        arrow(ax, (steps[i][1] + 0.065, 0.5), (steps[i + 1][1] - 0.065, 0.5))

    save(fig, "02_data_pipeline_flowchart.png")


# ══════════════════════════════════════════════════════════════════════════════
# 3. ML Pipeline Flowchart
# ══════════════════════════════════════════════════════════════════════════════
def fig03_ml_pipeline():
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("Machine Learning Pipeline", fontsize=15, fontweight="bold")

    steps = [
        ("User\nSelects\nRegion & Crop", 0.07),
        ("Fetch Yield,\nWeather,\nSoil Data", 0.22),
        ("Merge &\nClean Data", 0.36),
        ("Feature\nEngineering\n(GDD, Aggregates)", 0.52),
        ("PyCaret\nAutoML\n(compare_models)", 0.67),
        ("Best Model\nSelected", 0.80),
        ("SHAP / LIME\nExplanations", 0.93),
    ]
    colors = [PALETTE["teal"], PALETTE["green"], PALETTE["blue"],
              PALETTE["purple"], PALETTE["orange"], PALETTE["blue"], PALETTE["teal"]]
    for (text, x), color in zip(steps, colors):
        box(ax, text, (x, 0.52), w=0.12, h=0.38, color=color, fontsize=8)
    for i in range(len(steps) - 1):
        arrow(ax, (steps[i][1] + 0.06, 0.52), (steps[i + 1][1] - 0.06, 0.52))

    save(fig, "03_ml_pipeline_flowchart.png")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Technology Stack
# ══════════════════════════════════════════════════════════════════════════════
def fig04_tech_stack():
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("MLPlayground – Technology Stack", fontsize=15, fontweight="bold")

    categories = {
        "Frontend": (["Streamlit"], 0.15, 0.80, PALETTE["teal"]),
        "Backend\nAPI": (["FastAPI", "Uvicorn"], 0.38, 0.80, PALETTE["orange"]),
        "ML /\nExplainability": (["PyCaret", "SHAP", "LIME", "scikit-learn"], 0.62, 0.80, PALETTE["purple"]),
        "Data\nStorage": (["PostgreSQL", "SQLAlchemy", "Alembic"], 0.85, 0.80, PALETTE["blue"]),
        "Data\nSources": (["USDA NASS", "NASA NLDAS", "SSURGO"], 0.15, 0.30, PALETTE["green"]),
        "Feature\nEng.": (["GDD", "Precip. Agg.", "Soil Norm."], 0.50, 0.30, PALETTE["grey"]),
        "DevOps": (["Docker", "Compose", "Git"], 0.85, 0.30, PALETTE["dark"]),
    }

    for cat_label, (libs, x, y, color) in categories.items():
        # category header
        box(ax, cat_label, (x, y + 0.10), w=0.18, h=0.09, color=color, fontsize=9)
        for i, lib in enumerate(libs):
            box(ax, lib, (x, y - 0.02 - i * 0.11), w=0.16, h=0.08,
                color="#eceff1", fontsize=8, textcolor=PALETTE["dark"])

    save(fig, "04_technology_stack.png")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Data Sources Overview
# ══════════════════════════════════════════════════════════════════════════════
def fig05_data_sources():
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.suptitle("Integrated Data Sources", fontsize=15, fontweight="bold")
    fig.patch.set_facecolor(PALETTE["light"])

    sources = [
        ("USDA NASS QuickStats\n(Yield Data)", PALETTE["green"],
         ["• Crop: corn, soybeans,\n  wheat, cotton, peanuts",
          "• Annual county-level\n  yield records",
          "• 1980 – 2022",
          "• Target variable:\n  lbs / acre"]),
        ("NASA NLDAS\n(Weather Data)", PALETTE["blue"],
         ["• Daily temperature\n  (min / max / mean)",
          "• Daily precipitation",
          "• Growing Degree Days\n  (computed)",
          "• Seasonal aggregates"]),
        ("SSURGO\n(Soil Data)", PALETTE["orange"],
         ["• Sand / silt / clay\n  percentages",
          "• Soil pH",
          "• Organic matter %",
          "• County-level averages"]),
    ]

    for ax, (title, color, bullets) in zip(axes, sources):
        ax.set_facecolor(color)
        ax.axis("off")
        ax.set_title(title, color="white", fontsize=11, fontweight="bold", pad=8,
                     bbox=dict(facecolor=color, edgecolor="none"))
        for i, b in enumerate(bullets):
            ax.text(0.05, 0.80 - i * 0.22, b, transform=ax.transAxes,
                    fontsize=9, va="top", color="white")

    save(fig, "05_data_sources_overview.png")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Feature Engineering Diagram
# ══════════════════════════════════════════════════════════════════════════════
def fig06_feature_engineering():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("Automated Feature Engineering", fontsize=15, fontweight="bold")

    raw = [("Daily Tmax\n& Tmin", 0.12, 0.75), ("Daily Precip.", 0.12, 0.50), ("Soil Texture", 0.12, 0.25)]
    eng = [
        ("Growing Degree Days\nGDD = Σ max(0, (Tmax+Tmin)/2 − Tbase)", 0.50, 0.75),
        ("Seasonal Precipitation\nCumulative sum over growing season", 0.50, 0.50),
        ("Soil Normalisation\nsand_pct + silt_pct + clay_pct = 100", 0.50, 0.25),
    ]
    out = [("Feature Matrix\nX (n × p)", 0.88, 0.50)]

    for text, x, y in raw:
        box(ax, text, (x, y), w=0.18, h=0.12, color=PALETTE["blue"])
    for text, x, y in eng:
        box(ax, text, (x, y), w=0.30, h=0.12, color=PALETTE["purple"])
    for text, x, y in out:
        box(ax, text, (x, y), w=0.18, h=0.14, color=PALETTE["green"])

    for (_, rx, ry), (_, ex, ey) in zip(raw, eng):
        arrow(ax, (rx + 0.09, ry), (ex - 0.15, ey))
    for _, ex, ey in eng:
        arrow(ax, (ex + 0.15, ey), (out[0][1] - 0.09, out[0][2]))

    save(fig, "06_feature_engineering.png")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Historical Crop Yield Trends (NC, from CSV)
# ══════════════════════════════════════════════════════════════════════════════
def fig07_yield_trends():
    df = load_csv()
    annual = df.groupby(["Year", "Commodity"])["YIELD_LBS_PER_ACRE"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    for crop, grp in annual.groupby("Commodity"):
        ax.plot(grp["Year"], grp["YIELD_LBS_PER_ACRE"], marker="o", markersize=3, label=crop)

    ax.set_title("Historical Crop Yield Trends – North Carolina (1980–2022)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean Yield (lbs / acre)")
    ax.legend(title="Crop", fontsize=9)
    ax.grid(True, alpha=0.4)
    save(fig, "07_historical_yield_trends.png")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Yield Distribution by Crop (box plots)
# ══════════════════════════════════════════════════════════════════════════════
def fig08_yield_distribution():
    df = load_csv()
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    order = df.groupby("Commodity")["YIELD_LBS_PER_ACRE"].median().sort_values().index.tolist()
    sns.boxplot(data=df, x="Commodity", y="YIELD_LBS_PER_ACRE", order=order,
                palette="Set2", ax=ax)
    ax.set_title("Yield Distribution by Crop – North Carolina", fontsize=14, fontweight="bold")
    ax.set_xlabel("Crop")
    ax.set_ylabel("Yield (lbs / acre)")
    save(fig, "08_yield_distribution_by_crop.png")


# ══════════════════════════════════════════════════════════════════════════════
# 9. Yearly Average Yield Trend (all crops combined)
# ══════════════════════════════════════════════════════════════════════════════
def fig09_yearly_avg_yield():
    df = load_csv()
    annual = df.groupby("Year")["YIELD_LBS_PER_ACRE"].mean()
    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor(PALETTE["light"])
    ax.fill_between(annual.index, annual.values, alpha=0.3, color=PALETTE["green"])
    ax.plot(annual.index, annual.values, color=PALETTE["green"], lw=2)
    # trend line
    z = np.polyfit(annual.index, annual.values, 1)
    p = np.poly1d(z)
    ax.plot(annual.index, p(annual.index), "--", color=PALETTE["orange"], lw=1.5, label="Linear trend")
    ax.set_title("Yearly Average Yield (All Crops, NC)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean Yield (lbs / acre)")
    ax.legend()
    ax.grid(True, alpha=0.4)
    save(fig, "09_yearly_avg_yield_trend.png")


# ══════════════════════════════════════════════════════════════════════════════
# 10. Crop Share (record count bar chart)
# ══════════════════════════════════════════════════════════════════════════════
def fig10_crop_share():
    df = load_csv()
    counts = df["Commodity"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    bars = ax.bar(counts.index, counts.values,
                  color=[PALETTE["green"], PALETTE["blue"], PALETTE["orange"],
                         PALETTE["purple"], PALETTE["teal"]])
    ax.set_title("Number of Records per Crop – NC Dataset", fontsize=14, fontweight="bold")
    ax.set_xlabel("Crop")
    ax.set_ylabel("Record Count")
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20,
                f"{val:,}", ha="center", va="bottom", fontsize=9)
    save(fig, "10_crop_share_bar.png")


# ══════════════════════════════════════════════════════════════════════════════
# 11. Database Schema (ER-style)
# ══════════════════════════════════════════════════════════════════════════════
def fig11_db_schema():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("Database Schema (ER Diagram)", fontsize=15, fontweight="bold")

    tables = {
        "yields": (0.18, 0.55, ["id (PK)", "state", "county", "crop", "year", "value", "unit"], PALETTE["green"]),
        "weather": (0.50, 0.55, ["id (PK)", "state", "county", "year", "avg_temp", "precipitation", "gdd"], PALETTE["blue"]),
        "soil": (0.82, 0.55, ["id (PK)", "state", "county", "district", "sand_pct", "silt_pct", "clay_pct", "ph", "organic_matter"], PALETTE["orange"]),
    }

    for name, (x, y, cols, color) in tables.items():
        h = 0.07 + len(cols) * 0.055
        rect = FancyBboxPatch((x - 0.14, y - h / 2), 0.28, h,
                               boxstyle="round,pad=0.01",
                               linewidth=1.5, edgecolor=color, facecolor="white")
        ax.add_patch(rect)
        # header
        header = FancyBboxPatch((x - 0.14, y - h / 2 + h - 0.05), 0.28, 0.055,
                                 boxstyle="round,pad=0.005",
                                 linewidth=0, facecolor=color)
        ax.add_patch(header)
        ax.text(x, y - h / 2 + h - 0.022, name.upper(), ha="center", va="center",
                fontsize=10, color="white", fontweight="bold")
        for i, col in enumerate(cols):
            ax.text(x - 0.12, y - h / 2 + h - 0.075 - i * 0.052,
                    col, va="center", fontsize=7.5, color=PALETTE["dark"])

    # FK lines
    ax.annotate("", xy=(0.36, 0.55), xytext=(0.50 - 0.14, 0.55),
                arrowprops=dict(arrowstyle="<->", color=PALETTE["grey"], lw=1.3))
    ax.annotate("", xy=(0.64, 0.55), xytext=(0.82 - 0.14, 0.55),
                arrowprops=dict(arrowstyle="<->", color=PALETTE["grey"], lw=1.3))
    ax.text(0.43, 0.58, "county, year", ha="center", fontsize=7, color=PALETTE["grey"])
    ax.text(0.71, 0.58, "county", ha="center", fontsize=7, color=PALETTE["grey"])

    save(fig, "11_database_schema.png")


# ══════════════════════════════════════════════════════════════════════════════
# 12. API Endpoint Overview
# ══════════════════════════════════════════════════════════════════════════════
def fig12_api_endpoints():
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("FastAPI – Endpoint Overview", fontsize=15, fontweight="bold")

    endpoints = [
        ("GET /yields/", "state, crop,\nyear", "JSON list of\nyield records", 0.20),
        ("GET /weather/", "state, county,\nyear", "JSON list of\nweather records", 0.50),
        ("GET /soil/", "state, county,\ndistrict", "JSON list of\nsoil properties", 0.80),
    ]

    for method, params, resp, x in endpoints:
        box(ax, method, (x, 0.78), w=0.24, h=0.10, color=PALETTE["orange"], fontsize=10)
        box(ax, f"Query params:\n{params}", (x, 0.55), w=0.24, h=0.14, color=PALETTE["blue"], fontsize=8)
        box(ax, f"Response:\n{resp}", (x, 0.28), w=0.24, h=0.14, color=PALETTE["green"], fontsize=8)
        arrow(ax, (x, 0.73), (x, 0.62))
        arrow(ax, (x, 0.48), (x, 0.35))

    ax.text(0.50, 0.07, "All endpoints served by FastAPI at http://api:8000",
            ha="center", fontsize=9, color=PALETTE["grey"], style="italic")

    save(fig, "12_api_endpoint_overview.png")


# ══════════════════════════════════════════════════════════════════════════════
# 13. Model Training Workflow
# ══════════════════════════════════════════════════════════════════════════════
def fig13_model_training_workflow():
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("Model Training Workflow (PyCaret)", fontsize=15, fontweight="bold")

    nodes = [
        ("Merged\nDataFrame", 0.50, 0.90, PALETTE["blue"]),
        ("PyCaret\nsetup()", 0.50, 0.72, PALETTE["purple"]),
        ("compare_models()\ngbr | rf | ada | et | lr", 0.50, 0.54, PALETTE["orange"]),
        ("Best Model\nSelected", 0.50, 0.36, PALETTE["green"]),
        ("Evaluate:\nresiduals, error,\nlearning curve", 0.20, 0.18, PALETTE["teal"]),
        ("Explain:\nSHAP / LIME", 0.80, 0.18, PALETTE["purple"]),
    ]

    for text, x, y, color in nodes:
        box(ax, text, (x, y), w=0.30, h=0.12, color=color, fontsize=9)

    for i in range(3):
        arrow(ax, (nodes[i][1], nodes[i][2] - 0.06), (nodes[i + 1][1], nodes[i + 1][2] + 0.06))

    # split to eval and explain
    arrow(ax, (0.50, 0.30), (0.26, 0.24))
    arrow(ax, (0.50, 0.30), (0.74, 0.24))

    save(fig, "13_model_training_workflow.png")


# ══════════════════════════════════════════════════════════════════════════════
# 14. Model Comparison Bar Chart (illustrative)
# ══════════════════════════════════════════════════════════════════════════════
def fig14_model_comparison():
    models = ["Gradient\nBoosting", "Random\nForest", "Extra\nTrees", "AdaBoost", "Linear\nRegression"]
    r2 = [0.87, 0.84, 0.81, 0.74, 0.65]
    mae = [210, 240, 265, 340, 420]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Illustrative Model Comparison (Regression – Crop Yield)", fontsize=13, fontweight="bold")
    fig.patch.set_facecolor(PALETTE["light"])

    colors = [PALETTE["green"] if i == 0 else PALETTE["blue"] for i in range(len(models))]
    ax1.barh(models, r2, color=colors)
    ax1.set_xlabel("R² Score")
    ax1.set_title("R² Score (higher is better)")
    ax1.axvline(0.8, color="grey", linestyle="--", lw=1)
    for i, v in enumerate(r2):
        ax1.text(v + 0.005, i, f"{v:.2f}", va="center", fontsize=9)

    ax2.barh(models, mae, color=colors)
    ax2.set_xlabel("MAE (lbs/acre)")
    ax2.set_title("Mean Absolute Error (lower is better)")
    for i, v in enumerate(mae):
        ax2.text(v + 4, i, str(v), va="center", fontsize=9)

    save(fig, "14_model_comparison.png")


# ══════════════════════════════════════════════════════════════════════════════
# 15. SHAP Summary Bar Plot (illustrative)
# ══════════════════════════════════════════════════════════════════════════════
def fig15_shap_summary():
    features = ["gdd", "precipitation", "avg_temp", "sand_pct", "ph", "clay_pct", "organic_matter"]
    shap_vals = np.array([0.42, 0.31, 0.28, 0.14, 0.10, 0.08, 0.05])

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    bars = ax.barh(features[::-1], shap_vals[::-1],
                   color=[PALETTE["orange"] if v > 0.2 else PALETTE["blue"] for v in shap_vals[::-1]])
    ax.set_xlabel("Mean |SHAP Value|")
    ax.set_title("Global Feature Importance – SHAP Summary (Illustrative)", fontsize=13, fontweight="bold")
    ax.axvline(0, color="black", lw=0.5)
    for bar, val in zip(bars, shap_vals[::-1]):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=9)
    save(fig, "15_shap_summary.png")


# ══════════════════════════════════════════════════════════════════════════════
# 16. LIME Local Explanation (illustrative)
# ══════════════════════════════════════════════════════════════════════════════
def fig16_lime_local():
    features = ["gdd > 2800", "precip < 32 in", "sand_pct > 45", "ph <= 6.2",
                "clay_pct <= 18", "avg_temp > 68 °F", "organic_matter > 1.5"]
    contributions = [0.38, -0.22, 0.18, -0.12, 0.09, 0.14, -0.06]

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    colors = [PALETTE["green"] if v > 0 else PALETTE["orange"] for v in contributions]
    ax.barh(features, contributions, color=colors)
    ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("Contribution to Prediction")
    ax.set_title("LIME Local Explanation – Single Prediction (Illustrative)", fontsize=13, fontweight="bold")
    ax.legend(
        handles=[mpatches.Patch(color=PALETTE["green"], label="Increases yield"),
                 mpatches.Patch(color=PALETTE["orange"], label="Decreases yield")],
        loc="lower right", fontsize=9,
    )
    save(fig, "16_lime_local_explanation.png")


# ══════════════════════════════════════════════════════════════════════════════
# 17. Feature Correlation Heatmap (synthetic data)
# ══════════════════════════════════════════════════════════════════════════════
def fig17_correlation_heatmap():
    rng = np.random.default_rng(42)
    n = 300
    gdd = rng.normal(2800, 300, n)
    precip = rng.normal(35, 8, n)
    avg_temp = rng.normal(68, 4, n)
    sand_pct = rng.uniform(20, 70, n)
    clay_pct = 100 - sand_pct - rng.uniform(10, 30, n)
    ph = rng.uniform(5.5, 7.5, n)
    organic = rng.uniform(0.5, 3.0, n)
    yld = (0.4 * gdd + 2 * precip + 0.5 * avg_temp
           - 1.5 * sand_pct + 10 * organic + rng.normal(0, 80, n))

    df_syn = pd.DataFrame({
        "yield": yld, "gdd": gdd, "precipitation": precip, "avg_temp": avg_temp,
        "sand_pct": sand_pct, "clay_pct": clay_pct, "ph": ph, "organic_matter": organic,
    })

    fig, ax = plt.subplots(figsize=(9, 7))
    fig.patch.set_facecolor(PALETTE["light"])
    sns.heatmap(df_syn.corr(), annot=True, fmt=".2f", cmap="RdYlGn",
                center=0, linewidths=0.4, ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title("Feature Correlation Heatmap (Synthetic Data)", fontsize=13, fontweight="bold")
    save(fig, "17_feature_correlation_heatmap.png")


# ══════════════════════════════════════════════════════════════════════════════
# 18. GDD vs Yield Scatter
# ══════════════════════════════════════════════════════════════════════════════
def fig18_gdd_vs_yield():
    rng = np.random.default_rng(0)
    gdd = rng.normal(2800, 350, 250)
    yld = 0.45 * gdd - 100 + rng.normal(0, 200, 250)

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    ax.scatter(gdd, yld, alpha=0.55, color=PALETTE["blue"], s=30)
    z = np.polyfit(gdd, yld, 1)
    xs = np.linspace(gdd.min(), gdd.max(), 100)
    ax.plot(xs, np.poly1d(z)(xs), color=PALETTE["orange"], lw=2, label="Linear fit")
    ax.set_xlabel("Growing Degree Days (GDD)")
    ax.set_ylabel("Yield (lbs / acre)")
    ax.set_title("GDD vs Crop Yield (Synthetic Illustration)", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save(fig, "18_gdd_vs_yield.png")


# ══════════════════════════════════════════════════════════════════════════════
# 19. Precipitation vs Yield Scatter
# ══════════════════════════════════════════════════════════════════════════════
def fig19_precip_vs_yield():
    rng = np.random.default_rng(1)
    precip = rng.normal(35, 8, 250)
    yld = 60 * precip - 500 + rng.normal(0, 300, 250)

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    ax.scatter(precip, yld, alpha=0.55, color=PALETTE["teal"], s=30)
    z = np.polyfit(precip, yld, 1)
    xs = np.linspace(precip.min(), precip.max(), 100)
    ax.plot(xs, np.poly1d(z)(xs), color=PALETTE["orange"], lw=2, label="Linear fit")
    ax.set_xlabel("Seasonal Precipitation (inches)")
    ax.set_ylabel("Yield (lbs / acre)")
    ax.set_title("Precipitation vs Crop Yield (Synthetic Illustration)", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save(fig, "19_precipitation_vs_yield.png")


# ══════════════════════════════════════════════════════════════════════════════
# 20. Soil pH vs Yield Scatter
# ══════════════════════════════════════════════════════════════════════════════
def fig20_ph_vs_yield():
    rng = np.random.default_rng(2)
    ph = rng.uniform(5.0, 8.0, 250)
    yld = -500 * (ph - 6.5) ** 2 + 4500 + rng.normal(0, 300, 250)

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    ax.scatter(ph, yld, alpha=0.55, color=PALETTE["purple"], s=30)
    xs = np.linspace(5.0, 8.0, 100)
    ax.plot(xs, -500 * (xs - 6.5) ** 2 + 4500, color=PALETTE["orange"],
            lw=2, label="Quadratic fit")
    ax.set_xlabel("Soil pH")
    ax.set_ylabel("Yield (lbs / acre)")
    ax.set_title("Soil pH vs Crop Yield (Synthetic Illustration)", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save(fig, "20_soil_ph_vs_yield.png")


# ══════════════════════════════════════════════════════════════════════════════
# 21. Top-10 County Yield Comparison (NC, from CSV – mean over all years)
# ══════════════════════════════════════════════════════════════════════════════
def fig21_county_yield():
    df = load_csv()
    corn = df[df["Commodity"] == "CORN"]
    county_mean = (corn.groupby("County")["YIELD_LBS_PER_ACRE"].mean()
                   .drop(["OTHER COUNTIES", "OTHER (COMBINED) COUNTIES"], errors="ignore")
                   .sort_values(ascending=False).head(10))

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    ax.bar(county_mean.index, county_mean.values, color=PALETTE["green"], alpha=0.85)
    ax.set_title("Top 10 Counties – Mean Corn Yield (NC, 1980–2022)", fontsize=13, fontweight="bold")
    ax.set_xlabel("County")
    ax.set_ylabel("Mean Yield (lbs / acre)")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.4)
    save(fig, "21_county_yield_comparison.png")


# ══════════════════════════════════════════════════════════════════════════════
# 22. Seasonal Aggregate Feature Diagram
# ══════════════════════════════════════════════════════════════════════════════
def fig22_seasonal_aggregate():
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    rng = np.random.default_rng(3)
    daily_precip = rng.exponential(0.12, len(months) * 30)
    daily_temp = 50 + 20 * np.sin(np.linspace(0, np.pi, len(months) * 30)) + rng.normal(0, 3, len(months) * 30)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    fig.suptitle("Seasonal Aggregate Features – Growing Season Example", fontsize=13, fontweight="bold")
    fig.patch.set_facecolor(PALETTE["light"])

    days = np.arange(len(months) * 30)
    ax1.bar(days, daily_precip, color=PALETTE["blue"], alpha=0.6, width=1)
    ax1.axhline(daily_precip.mean(), color=PALETTE["orange"], lw=1.5, linestyle="--",
                label=f"Season total = {daily_precip.sum():.1f} in")
    ax1.set_ylabel("Daily Precip (in)")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    tbase = 50
    gdd_daily = np.maximum(0, daily_temp - tbase)
    cumgdd = np.cumsum(gdd_daily)
    ax2.plot(days, cumgdd, color=PALETTE["green"], lw=2,
             label=f"Cumulative GDD = {cumgdd[-1]:.0f}")
    ax2.fill_between(days, cumgdd, alpha=0.25, color=PALETTE["green"])
    ax2.set_ylabel("Cumulative GDD")
    ax2.set_xlabel("Day of Growing Season")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    month_ticks = np.arange(0, len(months) * 30, 30)
    ax2.set_xticks(month_ticks)
    ax2.set_xticklabels(months)

    save(fig, "22_seasonal_aggregate_features.png")


# ══════════════════════════════════════════════════════════════════════════════
# 23. Model Residuals Plot (illustrative)
# ══════════════════════════════════════════════════════════════════════════════
def fig23_residuals():
    rng = np.random.default_rng(4)
    y_pred = rng.normal(4000, 600, 200)
    residuals = rng.normal(0, 180, 200)
    y_true = y_pred + residuals

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Model Residuals Analysis (Illustrative)", fontsize=13, fontweight="bold")
    fig.patch.set_facecolor(PALETTE["light"])

    ax1.scatter(y_pred, residuals, alpha=0.5, color=PALETTE["blue"], s=25)
    ax1.axhline(0, color=PALETTE["orange"], lw=1.5, linestyle="--")
    ax1.set_xlabel("Predicted Yield (lbs/acre)")
    ax1.set_ylabel("Residuals")
    ax1.set_title("Residuals vs Predicted")
    ax1.grid(True, alpha=0.3)

    ax2.hist(residuals, bins=25, color=PALETTE["blue"], edgecolor="white", alpha=0.8)
    ax2.axvline(0, color=PALETTE["orange"], lw=1.5, linestyle="--")
    ax2.set_xlabel("Residual Value")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Residual Distribution")
    ax2.grid(True, alpha=0.3)

    save(fig, "23_model_residuals.png")


# ══════════════════════════════════════════════════════════════════════════════
# 24. Prediction Error Distribution
# ══════════════════════════════════════════════════════════════════════════════
def fig24_prediction_error():
    rng = np.random.default_rng(5)
    true_vals = rng.normal(4200, 600, 300)
    errors = {"Gradient Boosting": 180, "Random Forest": 230, "Extra Trees": 255,
              "AdaBoost": 340, "Linear Regression": 415}

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(PALETTE["light"])
    colors = [PALETTE["green"], PALETTE["blue"], PALETTE["teal"], PALETTE["orange"], PALETTE["purple"]]
    for (name, std), color in zip(errors.items(), colors):
        preds = true_vals + rng.normal(0, std, len(true_vals))
        ax.hist(preds - true_vals, bins=30, alpha=0.55, label=f"{name} (MAE≈{std})",
                color=color, edgecolor="white")

    ax.axvline(0, color="black", lw=1.5, linestyle="--")
    ax.set_xlabel("Prediction Error (lbs/acre)")
    ax.set_ylabel("Frequency")
    ax.set_title("Prediction Error Distribution by Model (Illustrative)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    save(fig, "24_prediction_error_distribution.png")


# ══════════════════════════════════════════════════════════════════════════════
# 25. Explainability Framework Diagram
# ══════════════════════════════════════════════════════════════════════════════
def fig25_explainability_framework():
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("Explainability Framework – MLPlayground", fontsize=15, fontweight="bold")

    box(ax, "Trained\nModel", (0.50, 0.75), w=0.20, h=0.12, color=PALETTE["blue"])

    box(ax, "SHAP Explainer\n(Global)", (0.22, 0.50), w=0.28, h=0.14, color=PALETTE["purple"])
    box(ax, "LIME Explainer\n(Local)", (0.78, 0.50), w=0.28, h=0.14, color=PALETTE["orange"])

    box(ax, "Feature Importance\nSummary Bar / Beeswarm", (0.22, 0.24), w=0.28, h=0.14, color=PALETTE["teal"])
    box(ax, "Single Prediction\nFeature Contributions", (0.78, 0.24), w=0.28, h=0.14, color=PALETTE["green"])

    arrow(ax, (0.40, 0.75), (0.22, 0.57))
    arrow(ax, (0.60, 0.75), (0.78, 0.57))
    arrow(ax, (0.22, 0.43), (0.22, 0.31))
    arrow(ax, (0.78, 0.43), (0.78, 0.31))

    ax.text(0.50, 0.07,
            "Model-agnostic methods: applicable to Gradient Boosting, Random Forest, etc.",
            ha="center", fontsize=9, color=PALETTE["grey"], style="italic")

    save(fig, "25_explainability_framework.png")


# ══════════════════════════════════════════════════════════════════════════════
# 26. User Workflow (numbered steps)
# ══════════════════════════════════════════════════════════════════════════════
def fig26_user_workflow():
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("User Workflow – MLPlayground Step-by-Step", fontsize=14, fontweight="bold")

    steps = [
        ("1\nSelect State\n& Crop", 0.07),
        ("2\nSet Year\nRange", 0.21),
        ("3\nFetch &\nMerge Data", 0.35),
        ("4\nChoose\nFeatures", 0.49),
        ("5\nTrain &\nCompare Models", 0.63),
        ("6\nView SHAP\n& LIME", 0.77),
        ("7\nExport\nResults", 0.91),
    ]
    colors = [PALETTE["blue"], PALETTE["teal"], PALETTE["green"],
              PALETTE["purple"], PALETTE["orange"], PALETTE["teal"], PALETTE["green"]]
    for (text, x), color in zip(steps, colors):
        circle = plt.Circle((x, 0.55), 0.055, color=color, zorder=3)
        ax.add_patch(circle)
        num = text.split("\n")[0]
        rest = "\n".join(text.split("\n")[1:])
        ax.text(x, 0.55, num, ha="center", va="center", fontsize=13,
                color="white", fontweight="bold", zorder=4)
        ax.text(x, 0.25, rest, ha="center", va="center", fontsize=8,
                color=PALETTE["dark"], multialignment="center")

    for i in range(len(steps) - 1):
        ax.annotate("", xy=(steps[i + 1][1] - 0.055, 0.55),
                    xytext=(steps[i][1] + 0.055, 0.55),
                    arrowprops=dict(arrowstyle="->", color=PALETTE["grey"], lw=1.5))

    save(fig, "26_user_workflow.png")


# ══════════════════════════════════════════════════════════════════════════════
# 27. Deployment Architecture (Docker Compose)
# ══════════════════════════════════════════════════════════════════════════════
def fig27_deployment():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_title("Deployment Architecture – Docker Compose", fontsize=14, fontweight="bold")

    # Docker Compose box
    outer = FancyBboxPatch((0.05, 0.08), 0.90, 0.78,
                            boxstyle="round,pad=0.01",
                            linewidth=2, edgecolor=PALETTE["blue"],
                            facecolor="#e3f2fd", zorder=0)
    ax.add_patch(outer)
    ax.text(0.50, 0.88, "Docker Compose Stack", ha="center", fontsize=10,
            color=PALETTE["blue"], fontweight="bold")

    services = [
        ("app\n(Streamlit)\n:8501", 0.22, 0.50, PALETTE["teal"]),
        ("api\n(FastAPI)\n:8000", 0.50, 0.50, PALETTE["orange"]),
        ("db\n(PostgreSQL)\n:5432", 0.78, 0.50, PALETTE["blue"]),
    ]
    for text, x, y, color in services:
        box(ax, text, (x, y), w=0.22, h=0.26, color=color, fontsize=9)

    arrow(ax, (0.33, 0.50), (0.39, 0.50))
    arrow(ax, (0.61, 0.50), (0.67, 0.50))
    ax.text(0.36, 0.54, "HTTP\n:8000", ha="center", fontsize=7, color=PALETTE["grey"])
    ax.text(0.64, 0.54, "SQL\n:5432", ha="center", fontsize=7, color=PALETTE["grey"])

    # User
    box(ax, "Browser\n(User)", (0.22, 0.20), w=0.18, h=0.10, color=PALETTE["grey"])
    arrow(ax, (0.22, 0.25), (0.22, 0.37))
    ax.text(0.24, 0.31, ":8501", fontsize=7, color=PALETTE["grey"])

    save(fig, "27_deployment_architecture.png")


# ══════════════════════════════════════════════════════════════════════════════
# 28. Cross-Validation K-Fold Diagram
# ══════════════════════════════════════════════════════════════════════════════
def fig28_cross_validation():
    k = 5
    n = 25  # segments per fold

    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor(PALETTE["light"])
    ax.set_xlim(-0.5, n + 0.5)
    ax.set_ylim(-0.5, k + 0.5)
    ax.axis("off")
    ax.set_title(f"{k}-Fold Cross-Validation (PyCaret default)", fontsize=14, fontweight="bold")

    for fold in range(k):
        for seg in range(n):
            test_start = fold * (n // k)
            test_end = test_start + (n // k)
            is_test = test_start <= seg < test_end
            color = PALETTE["orange"] if is_test else PALETTE["blue"]
            rect = plt.Rectangle((seg, fold), 0.9, 0.8, facecolor=color,
                                  edgecolor="white", linewidth=0.8)
            ax.add_patch(rect)
        ax.text(-0.3, fold + 0.4, f"Fold {fold + 1}", ha="right", va="center", fontsize=9)

    ax.legend(handles=[
        mpatches.Patch(color=PALETTE["blue"], label="Training data"),
        mpatches.Patch(color=PALETTE["orange"], label="Validation data"),
    ], loc="upper right", fontsize=9)

    save(fig, "28_cross_validation_kfold.png")


# ══════════════════════════════════════════════════════════════════════════════
# 29. Project Goals Infographic
# ══════════════════════════════════════════════════════════════════════════════
def fig29_project_goals():
    goals = [
        ("Interactive\nForecasting", "Select crop & region;\nauto-trains a model\nin real-time.", PALETTE["green"]),
        ("Integrated\nData Sources", "USDA NASS yields +\nNASA NLDAS weather +\nSSURGO soil.", PALETTE["blue"]),
        ("Automated\nAgronomic Features", "GDD, seasonal precip.\naggregates, soil\nnormalisation.", PALETTE["purple"]),
        ("Explainability\nFirst", "Every prediction has\nSHAP + LIME\nexplanations.", PALETTE["orange"]),
        ("Regional\nModels", "Piedmont vs Coastal\nPlains — district-level\ntraining scope.", PALETTE["teal"]),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(15, 5))
    fig.suptitle("MLPlayground – Key Project Goals", fontsize=15, fontweight="bold", y=1.02)
    fig.patch.set_facecolor(PALETTE["light"])

    for ax, (title, desc, color) in zip(axes, goals):
        ax.set_facecolor(color)
        ax.axis("off")
        ax.set_aspect("equal")
        ax.text(0.50, 0.75, title, ha="center", va="center", fontsize=11,
                fontweight="bold", color="white", transform=ax.transAxes,
                multialignment="center")
        ax.text(0.50, 0.35, desc, ha="center", va="center", fontsize=8.5,
                color="white", transform=ax.transAxes, multialignment="center")

    plt.tight_layout()
    save(fig, "29_project_goals_infographic.png")


# ══════════════════════════════════════════════════════════════════════════════
# 30. Poster Summary Overview (composite)
# ══════════════════════════════════════════════════════════════════════════════
def fig30_poster_summary():
    df = load_csv()
    annual_corn = df[df["Commodity"] == "CORN"].groupby("Year")["YIELD_LBS_PER_ACRE"].mean()

    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor(PALETTE["light"])
    fig.suptitle("MLPlayground – Poster Overview", fontsize=20, fontweight="bold", y=0.98)

    gs = GridSpec(3, 4, figure=fig, hspace=0.5, wspace=0.4)

    # ── top left: architecture mini-map ──────────────────────────────────────
    ax_arch = fig.add_subplot(gs[0, :2])
    ax_arch.set_xlim(0, 1); ax_arch.set_ylim(0, 1); ax_arch.axis("off")
    ax_arch.set_title("System Overview", fontsize=11, fontweight="bold")
    layers_mini = [
        (["USDA NASS", "NASA NLDAS", "SSURGO"], 0.88, PALETTE["green"]),
        (["ETL / Backend"],                      0.66, PALETTE["blue"]),
        (["PostgreSQL DB"],                       0.46, PALETTE["purple"]),
        (["FastAPI"],                             0.28, PALETTE["orange"]),
        (["Streamlit UI"],                        0.10, PALETTE["teal"]),
    ]
    for (lbs, y, color) in layers_mini:
        xs_m = np.linspace(0.15, 0.85, len(lbs))
        for x_m, lb in zip(xs_m, lbs):
            box(ax_arch, lb, (x_m, y), w=0.22, h=0.10, color=color, fontsize=7)
    for i in range(len(layers_mini) - 1):
        arrow(ax_arch, (0.50, layers_mini[i][1] - 0.05), (0.50, layers_mini[i + 1][1] + 0.05))

    # ── top right: corn yield trend ───────────────────────────────────────────
    ax_trend = fig.add_subplot(gs[0, 2:])
    ax_trend.plot(annual_corn.index, annual_corn.values, color=PALETTE["green"], lw=2)
    ax_trend.fill_between(annual_corn.index, annual_corn.values, alpha=0.2, color=PALETTE["green"])
    ax_trend.set_title("NC Corn Yield Trend (1980–2022)", fontsize=11, fontweight="bold")
    ax_trend.set_xlabel("Year", fontsize=8)
    ax_trend.set_ylabel("Mean Yield (lbs/acre)", fontsize=8)
    ax_trend.grid(True, alpha=0.3)
    ax_trend.tick_params(labelsize=7)

    # ── middle left: model comparison ─────────────────────────────────────────
    ax_models = fig.add_subplot(gs[1, :2])
    models = ["GBR", "RF", "ET", "ADA", "LR"]
    r2_vals = [0.87, 0.84, 0.81, 0.74, 0.65]
    colors_m = [PALETTE["green"] if i == 0 else PALETTE["blue"] for i in range(5)]
    ax_models.barh(models, r2_vals, color=colors_m)
    ax_models.set_xlabel("R² Score", fontsize=8)
    ax_models.set_title("Model Comparison (Illustrative)", fontsize=11, fontweight="bold")
    ax_models.axvline(0.8, color="grey", linestyle="--", lw=1)
    ax_models.tick_params(labelsize=7)
    ax_models.grid(axis="x", alpha=0.3)

    # ── middle right: SHAP ────────────────────────────────────────────────────
    ax_shap = fig.add_subplot(gs[1, 2:])
    feats = ["gdd", "precip", "avg_temp", "sand_pct", "ph"]
    shaps = [0.42, 0.31, 0.28, 0.14, 0.10]
    ax_shap.barh(feats[::-1], shaps[::-1], color=PALETTE["purple"])
    ax_shap.set_xlabel("Mean |SHAP|", fontsize=8)
    ax_shap.set_title("Top-5 SHAP Features (Illustrative)", fontsize=11, fontweight="bold")
    ax_shap.tick_params(labelsize=7)
    ax_shap.grid(axis="x", alpha=0.3)

    # ── bottom: goals banner ──────────────────────────────────────────────────
    ax_goals = fig.add_subplot(gs[2, :])
    ax_goals.set_xlim(0, 1); ax_goals.set_ylim(0, 1); ax_goals.axis("off")
    goals = [
        ("Interactive\nForecasting", PALETTE["green"]),
        ("Integrated\nData", PALETTE["blue"]),
        ("Automated\nFeatures", PALETTE["purple"]),
        ("Explainability\nFirst", PALETTE["orange"]),
        ("Regional\nModels", PALETTE["teal"]),
    ]
    xs_g = np.linspace(0.10, 0.90, len(goals))
    for (text, color), x_g in zip(goals, xs_g):
        box(ax_goals, text, (x_g, 0.55), w=0.16, h=0.60, color=color, fontsize=9)

    save(fig, "30_poster_summary_overview.png")


# ══════════════════════════════════════════════════════════════════════════════
# Run all
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating 30 visuals …")
    fig01_system_architecture()
    fig02_data_pipeline()
    fig03_ml_pipeline()
    fig04_tech_stack()
    fig05_data_sources()
    fig06_feature_engineering()
    fig07_yield_trends()
    fig08_yield_distribution()
    fig09_yearly_avg_yield()
    fig10_crop_share()
    fig11_db_schema()
    fig12_api_endpoints()
    fig13_model_training_workflow()
    fig14_model_comparison()
    fig15_shap_summary()
    fig16_lime_local()
    fig17_correlation_heatmap()
    fig18_gdd_vs_yield()
    fig19_precip_vs_yield()
    fig20_ph_vs_yield()
    fig21_county_yield()
    fig22_seasonal_aggregate()
    fig23_residuals()
    fig24_prediction_error()
    fig25_explainability_framework()
    fig26_user_workflow()
    fig27_deployment()
    fig28_cross_validation()
    fig29_project_goals()
    fig30_poster_summary()
    print(f"\nDone! 30 visuals saved to {OUT_DIR}")
