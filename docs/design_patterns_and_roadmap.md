# Design Patterns & Integration Roadmap

This document catalogues useful design patterns drawn from three reference codebases —
**Node-RED / n8n / NoFlo** (node-based data-processing UIs) and **Grafana** (dashboard +
node-graph visualization) — then maps them to concrete, prioritised changes in MLPlayground.
All planned changes are cross-referenced against [README.md](../README.md) (core goals) and
[features.md](../features.md) (open feature/fix list).

---

## 1. Design Patterns from Node-Based UI Applications

### 1.1 Node-RED — Low-code flow editor

| Pattern | Description |
|---|---|
| **Palettes as plugin registries** | All node types live in a discoverable registry exposed via HTTP. The frontend fetches the list and renders category-grouped palettes. Adding a new node requires zero frontend changes. |
| **Wire (edge) lifecycle** | Wires are first-class objects with their own visual states (active, error, pending). Deleting a wire does not require deleting endpoint nodes. Wires store `{ source, sourcePort, target, targetPort }`. |
| **Per-node status badges** | Each node renders a small status indicator (dot or label) set by the runtime after each execution. Three states: `idle`, `running`, `success/error`. |
| **Collapsible side panel** | The node library lives in a resizable left drawer; the properties/debug inspector lives in a resizable right drawer. Both can be collapsed independently without losing viewport width. |
| **Fixed-size node chrome** | Node containers have a fixed minimum width/height with a scroll-able list inside. Long labels inside the node are trucated with a tooltip; the container never expands. |

### 1.2 n8n — Visual workflow automation (TypeScript/React)

| Pattern | Description |
|---|---|
| **Credential / data-source abstraction** | External connections are managed as typed credential objects and referenced by name. Nodes declare which credential types they support; the editor renders the matching form automatically. |
| **Bypass / disable nodes** | Any node can be toggled off. The executor skips disabled nodes and routes data around them (pass-through or null output), enabling quick experimentation without deleting nodes. |
| **Node groups & sub-workflows** | A set of selected nodes can be collapsed into a "sub-workflow" group node, reducing visual clutter for complex pipelines. |
| **Canvas-native Python/JS code node** | A built-in "Code" node type embeds a Monaco editor for inline user scripts. The script receives the upstream data as a python/JSON variable and returns a new data object. |
| **Execution log drawer** | A bottom panel shows a per-run, per-node execution timeline with duration, input/output data preview, and error traces. |
| **Export as JSON / import** | The entire workflow is serializable to a JSON document that captures all node positions, edges, and parameter values. This document can be re-imported or shared. |

### 1.3 NoFlo — Flow-based programming runtime (JavaScript)

| Pattern | Description |
|---|---|
| **FBP protocol** | A clean runtime protocol (`fbp-protocol`) decouples the editor UI from the execution engine. The editor communicates via WebSocket messages: `graph:add-node`, `graph:add-edge`, `network:start`, `network:status`, etc. |
| **Graph serialization (FBP JSON)** | Graphs are stored as `{ processes: {}, connections: [], inports: {}, outports: {} }`. This is a language-agnostic standard readily adopted for export-as-script scenarios. |
| **Type-safe connections** | Ports declare the data type they carry (`dataframe`, `model`, `number`). The editor prevents incompatible-type connections with a visual cue before the user releases the drag. |

---

## 2. Design Patterns from Grafana

### 2.1 Collapsible splitter panes (`useSnappingSplitter`)

Grafana's panel editor uses a `useSnappingSplitter` hook that wraps a CSS-grid/flexbox
split container. Each pane has:

- **`initialSize`** (pixels or ratio)
- **`collapseBelowPixels`** — auto-collapses when the user drags below a threshold
- **`collapsed` state** — persisted to `localStorage` so the preference survives page reloads
- An expand button rendered inside the collapsed pane

This pattern is directly applicable to collapsing the node library, bottom preview, and
right parameter inspector in MLPlayground's graph editor.

```tsx
// Grafana source: PanelEditorRenderer.tsx
const { containerProps, primaryProps, secondaryProps, splitterProps, splitterState, onToggleCollapse } =
  useSnappingSplitter({
    direction: 'row',
    dragPosition: 'end',
    initialSize: 330,
    usePixels: true,
    collapsed: isInitiallyCollapsed,
    collapseBelowPixels: MIN_PANE_WIDTH,
  });
```

### 2.2 Plugin panel architecture (`PanelPlugin` + `VizPanel`)

Grafana separates the _plugin manifest_ (id, display name, logo, options schema) from the
_runtime instance_ (`VizPanel`). Key ideas:

- `PanelPlugin` registers an **options schema** (Pydantic-style field definitions). The
  editor derives its form UI from the schema automatically.
- `VizPanel` holds live state (`title`, `pluginId`, `options`, `fieldConfig`) and is
  serializable to a save-model with `toSaveModel()`.
- `PanelChrome` wraps every visualization and provides: loading spinner, error banner,
  title bar, hover menu — independent of the visualization itself.

The _MLPlayground analogy_: each graph node has a `BaseNode` manifest (Python backend) and a
`GraphNodeData` runtime object (React frontend). Adding a `chrome` component that renders
run-status, error messages, and tooltips uniformly around every node type would follow this
pattern exactly.

### 2.3 Node Graph panel (SVG + D3 + layout workers)

Grafana's built-in **Node Graph** visualization (`public/app/plugins/panel/nodeGraph/`)
handles rendering of directed graphs where nodes are data-processing steps:

| Sub-pattern | Detail |
|---|---|
| **Layout algorithms in Web Workers** | Force (D3), Layered (Sugiyama/MSAGL), and Grid algorithms all run off the main thread. The `useLayout` hook manages the worker lifecycle and caches completed layouts keyed by data signature. |
| **Layout cache by signature** | `createDataSignature(nodes, edges)` hashes node/edge count + sentinel IDs. If the signature hasn't changed the cached positions are reused, avoiding expensive re-layout on re-render. |
| **`NodeDatum` / `EdgeDatum` types** | Every rendered node carries `id`, `title`, `subTitle`, `mainStat`, `secondaryStat`, `arcSections` (pie segments for multi-label status), `highlighted`, `nodeRadius`. Edges carry `thickness`, `color`, `strokeDasharray`. These provide a rich visual vocabulary without changing the rendering pipeline. |
| **HoverState active/inactive/default** | Hovering a node or edge dims all unrelated elements to `inactive`, drawing the user's eye. This tri-state model is more informative than a binary hover toggle. |
| **`DashboardLayoutManager` interface** | Layouts implement `addPanel`, `removePanel`, `duplicatePanel`, `getVizPanels`, `toSaveModel()`, `cloneLayout()`, `getOptions()`. This clean interface enables multiple layout strategies (grid, auto-grid, rows) behind a single editor. |
| **`DataPipeline` executor (Go)** | `pkg/expr/graph.go` represents the execution graph as `[]Node` where each `Node` has `NeedsVars() []string` (input refs) and `Execute()`. The runtime does a topological-sort pass to schedule execution. This mirrors MLPlayground's backend graph runner. |

### 2.4 Dashboard panel menu / context menu

Grafana's `panelMenuBehavior` pattern:

- Context menu items are assembled _lazily_ (the menu is not built until opened).
- Extension points are defined as named `PluginExtensionPoints`; third-party code can inject
  menu items without touching core code.
- Menu items can be async (e.g. `createAlert` fetches rule values before navigating).

In MLPlayground's context this maps cleanly to a right-click context menu on each node with
actions: **Run from here**, **Bypass**, **Rename**, **Duplicate**, **Delete**, **View last
output**, **Export node as Python script**.

### 2.5 Auto-layout options (LR, TB, compact)

The Grafana node graph exposes a `LayoutAlgorithm` enum `{ Force, Layered, Grid }` in its
panel options. The `layeredLayout.js` driver sets `LayerDirectionEnum.LR` by default via
`SugiyamaLayoutSettings`. Adding TB and compact as selectable options is a one-line config
change per algorithm variant.

---

## 3. Synthesis: Integration Plan for MLPlayground

The goal is to enrich the graph editor while keeping the platform **domain-agnostic**,
**data-driven**, and **minimally-friction** (README goals 1–4). All changes below map
directly to items in `features.md`.

### Priority 1 — Core UX fixes (unblocking daily use)

| # | Feature | Pattern source | `features.md` item | Notes |
|---|---|---|---|---|
| 1.1 | **Graph editor fills full browser width** | CSS layout | ✓ listed | Remove fixed-width wrapper in `graph.tsx`; use `height: 100vh` flex container. |
| 1.2 | **Collapsible side panels** | Grafana `useSnappingSplitter` | ✓ listed | Implement a `useSplitPane` hook (drag + snap + localStorage persist) for the node library (left), parameter inspector (right), and output preview (bottom). |
| 1.3 | **Edge deletion without node deletion** | Node-RED wire lifecycle | ✓ listed | ReactFlow already supports edge deletion via `onEdgesDelete`; add a visible delete button on hovered edges and a keyboard-shortcut handler (`Delete` / `Backspace`). |
| 1.4 | **Fixed-size node chrome; no auto-grow** | Node-RED fixed chrome | ✓ listed | Set `maxWidth` / `overflow: hidden` + a tooltip or scroll area for long content in `GraphNode`. Model after Grafana's `PanelChrome`. |
| 1.5 | **Manual node resize** | n8n / ReactFlow `NodeResizer` | ✓ listed | Enable `<NodeResizer>` from `@xyflow/react` on each node. Persist width/height in `GraphNodeData`. |
| 1.6 | **Larger, easier connection handles** | Node-RED UX | ✓ listed | Increase ReactFlow `Handle` size in CSS to `14px`, add hover-expand via `::after` pseudo-element. |

### Priority 2 — Execution & status feedback

| # | Feature | Pattern source | `features.md` item | Notes |
|---|---|---|---|---|
| 2.1 | **Rich per-node run-status badge** | Node-RED status dots + Grafana `NodeDatum.arcSections` | ✓ listed | Add a `<RunStatusBadge>` component inside each node chrome: idle (grey), running (spinner), success (green check), error (red X with tooltip). Pull from `node_statuses` in `RunStatus`. |
| 2.2 | **Execution log drawer (bottom panel)** | n8n execution log | new | Bottom collapsible pane showing per-run, per-node: duration, row count in/out, preview of first 5 rows, error traceback. |
| 2.3 | **Bypass nodes** | n8n bypass | ✓ listed | Add `bypassed: boolean` to `GraphNodeData`. Backend executor checks `bypassed` and routes the first upstream output directly to downstream nodes. Frontend renders bypassed nodes with reduced opacity and a dashed border. |

### Priority 3 — New node types

| # | Feature | Pattern source | `features.md` item | Notes |
|---|---|---|---|---|
| 3.1 | **Plot node** | Grafana `PanelPlugin` | ✓ listed | New `PlotNode` (backend Python): receives a DataFrame, generates a Matplotlib/Plotly figure, serializes as base64 PNG or JSON spec, and returns it. Frontend renders inline. Sub-types: scatter, line, histogram, residual plot. |
| 3.2 | **Custom Python code node** | n8n Code node | ✓ listed | New `PythonCodeNode`: embeds a Monaco editor in the node's parameter panel. Execute via a sandboxed Python executor on the backend (`exec()` with restricted globals). Input DF available as `df`, output must assign `result`. |
| 3.3 | **Drop columns node** | — | ✓ listed | Simple transform node: parameter is a multi-select of column names from upstream schema. |
| 3.4 | **External data source node (NOAA)** | n8n credential abstraction | ✓ listed | New `NOAAForecastNode`: fetches NOAA API forecasted weather for a given state/year. Cache to local file (not DB per `features.md`). Parameters: `state`, `year`, `variable`. |

### Priority 4 — Auto-layout & graph navigation

| # | Feature | Pattern source | `features.md` item | Notes |
|---|---|---|---|---|
| 4.1 | **Auto-layout: LR / TB / compact** | Grafana `SugiyamaLayoutSettings` + `LayoutAlgorithm` enum | ✓ listed | Integrate `@dagrejs/dagre` (already a transitive ReactFlow dep). Expose three buttons in the toolbar: Left→Right, Top→Bottom, Compact (force-directed). Call `layoutNodes(nodes, edges, direction)` then call ReactFlow's `fitView`. |
| 4.2 | **Layout cache** | Grafana `LayoutCache` + data signature | — | After auto-layout runs, cache positions in `sessionStorage` keyed by a hash of node/edge counts + IDs. Restore on page reload. |

### Priority 5 — Export & portability

| # | Feature | Pattern source | `features.md` item | Notes |
|---|---|---|---|---|
| 5.1 | **Export workflow as Python script** | NoFlo FBP JSON + n8n export | ✓ listed | Backend endpoint `POST /api/v1/graphs/export/python` accepts a `graph_spec` JSON and returns a `.py` file. Generate imports, instantiate nodes in topological order, wire via function calls. |
| 5.2 | **Save / load workflow (JSON)** | n8n workflow JSON | already present | Already implemented via `/api/v1/graphs/workflows`. Surface a "Share" button that copies the raw JSON to clipboard. |

### Priority 6 — Dashboard integration (Grafana-inspired)

| # | Feature | Pattern source | `features.md` item | Notes |
|---|---|---|---|---|
| 6.1 | **Results dashboard route** | Grafana `DashboardLayoutManager` + `VizPanel` | Final Goal | A new `/dashboard` route that auto-populates panels from the last successful graph run: one panel per Plot node output + one table per DataFrame output. Panels use a 12-column grid layout (mirroring Grafana's `gridPos`). |
| 6.2 | **Reusable panel type registry** | Grafana `PanelPlugin` registry | — | `PANEL_REGISTRY` in the frontend maps `panelType → React component`. Adding a new chart type requires one registry entry; the dashboard builder discovers it automatically. |
| 6.3 | **Panel chrome** | Grafana `PanelChrome` | — | Uniform wrapper for every dashboard panel: title bar, loading spinner, error banner, download button, fullscreen toggle. |
| 6.4 | **Tooltips on node parameters** | Grafana options schema `description` field | ✓ listed | `params_schema` already supports a `description` field on each property. Render it as a `<Tooltip>` label next to each form input in the node parameter panel. |

---

## 4. Architecture Changes Required

### 4.1 Frontend (`frontend/src/`)

```
frontend/src/
├── components/
│   ├── graph/
│   │   ├── NodeChrome.tsx          # NEW: wraps every node with status badge + resize
│   │   ├── RunStatusBadge.tsx      # NEW: idle/running/success/error indicator
│   │   ├── ExecutionDrawer.tsx     # NEW: bottom collapsible log drawer
│   │   ├── PythonCodeEditor.tsx    # NEW: Monaco-based inline code node editor
│   │   └── AutoLayoutToolbar.tsx   # NEW: LR / TB / compact layout buttons
│   └── dashboard/
│       ├── DashboardGrid.tsx       # NEW: 12-col panel grid (like Grafana gridPos)
│       ├── PanelChrome.tsx         # NEW: uniform panel wrapper
│       └── PANEL_REGISTRY.ts       # NEW: panelType → React component map
├── hooks/
│   ├── useSplitPane.ts             # NEW: collapsible splitter (Grafana-inspired)
│   └── useAutoLayout.ts            # NEW: dagre layout + cache
└── routes/
    ├── graph.tsx                   # MODIFY: full-width, splitter panes, new node types
    └── dashboard.tsx               # NEW: results dashboard route
```

### 4.2 Backend (`backend/app/`)

```
backend/app/
├── nodes/
│   ├── node_plot.py               # NEW: PlotNode (matplotlib/plotly)
│   ├── node_python_code.py        # NEW: PythonCodeNode (exec sandbox)
│   ├── node_drop_columns.py       # NEW: DropColumnsNode
│   └── node_noaa_forecast.py      # NEW: NOAAForecastNode (cached HTTP)
└── api/routes/
    └── graphs.py                  # MODIFY: add /export/python endpoint
```

### 4.3 Python export endpoint

The `POST /api/v1/graphs/export/python` endpoint performs a topological sort of the graph
spec and emits:

```python
# Auto-generated by MLPlayground
import pandas as pd
from app.nodes.node_csv_source import CSVSourceNode
from app.nodes.node_filter import FilterNode

# Step 1 — CSV Source
n1 = CSVSourceNode()
df_n1 = n1.execute(file_path="/app/data/sample.csv")

# Step 2 — Filter
n2 = FilterNode()
df_n2 = n2.execute(dataframe=df_n1, column="year", operator=">", value="2010")
```

This satisfies the `features.md` final goal of exporting the full workflow as a Python
script.

---

## 5. Alignment with Original Project Goals

| README goal | How changes align |
|---|---|
| **Domain-agnostic** | No agriculture-specific code is added. New nodes (Plot, Code, NOAA) are as generic as current nodes; NOAA is parameterised by state/variable, not hard-coded to crops. |
| **Data-driven UI** | Node types, dashboard panels, and auto-layout options all auto-discover from registries. Zero manual frontend wiring for new node or panel types. |
| **Transparent** | The execution log drawer and Python export ensure every step is inspectable and reproducible outside the UI. |
| **Minimal friction** | New node types still require exactly one Python file. The `BaseNode.__init_subclass__` hook auto-registers everything. |

---

## 6. Suggested Implementation Order

```
Sprint 1 (core UX)         → 1.1, 1.2, 1.3, 1.4, 1.6
Sprint 2 (status + UX)     → 1.5, 2.1, 2.3, 4.1, 6.4
Sprint 3 (new nodes)       → 3.1, 3.3, 3.4, 2.2
Sprint 4 (export + code)   → 5.1, 3.2
Sprint 5 (dashboard)       → 6.1, 6.2, 6.3, 4.2
```

The **Final Goal** in `features.md` (corn yield model for NC with residual plot, NOAA
forecast, 2026 prediction, Python export) is fully addressable after Sprint 4, with the
dashboard view available after Sprint 5.
