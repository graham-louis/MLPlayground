# Features or fixes to add
-  Graph editor should span entire width of browser window
- Node library, bottom preview, and right preview should be collapsable
- Edges should be able to be deleted without needing to delete nodes
- Nodes should not get larger if the text inside them get larger (example: the Select Features node gets wider as more features are added to the list)
- Users should be able to scale node size manually
- Provide better indication of run status (nodes that have successfully run should be obviously marked as such)
- Add nodes for creating plots
- Add ability to download workflow as a python script
- Add ability to add nodes with custom python code
- Add node for dropping specific columns
- Add ability to bypass nodes
- Automatic layout should have options for LR, Top to bottom, and compact
- Add better tool tips to node parameters
- Make edge connection points on nodes larger and easier to click
- Add a node for fetching data from external sources (NOAA forecasted weather)

## More Ideas
- Multiple filters in a single node.
- Nodes for getting summaries (count unique, maybe use pandas profiling)
- Run Output should not expand after each run
- Random state should not be a required variable for train model node
- Train model node should display metrics and feature importance in a formatted way (not just JSON)

## Final Goal
- Create an example workflow that trains a corn yield model for North Carolina
    - Use a plot node to plot residuals of training
    - Fetch forecasted data from external source (Keep in cache but do not add to DB)
    - Use model to predict yield for 2026
    - Be able to export entire workflow as a python script


Keep graph.tsx as the canonical page and orchestration surface; refactor and extend it incrementally by extracting reusable parts into frontend/src/components/graph/, add small supporting utilities, and implement new UX/features (collapsible panels, resizable nodes, edge-only deletion, node run-status, plot/external/custom nodes, export) on top of that existing file so learners can trace changes from a single, working source file to a modular, production-ready editor.

Steps

Read & keep graph.tsx as source of truth

Base file: graph.tsx
Rationale: it already contains React Flow usage, node/edge shapes, templates, inspector, run+SSE logic, and buildSpec. Building on it keeps integration with backend and preserves existing behavior for learners.
Refactor small pieces out of graph.tsx (non-breaking, stepwise)

Create components and utilities but keep GraphPage in graph.tsx. Move code in small commits so learners see progressive refactor.
New files to add:
frontend/src/components/graph/GraphCanvas.tsx — extract FlowWithDrop and React Flow setup (provider usage remains in graph.tsx).
frontend/src/components/graph/GraphNode.tsx — extract GraphNodeComponent (node visual, header, handles).
frontend/src/components/graph/NodePalette.tsx — extract node palette UI.
frontend/src/components/graph/NodeInspector.tsx — extract inspector form.
frontend/src/components/graph/ResultsPane.tsx — extract run result UI.
frontend/src/components/graph/layout.ts — move computeAutoLayout and later add dagre/ELK wrappers.
frontend/src/components/graph/exporter.ts — client-side export helpers (templating, topological sort wrapper).
How to refactor: move code blocks (preserve types/interfaces), export small props-based components, and import back into graph.tsx. Keep GraphPage logic unchanged during each small commit.
Add dependencies and small infra edits

Update package.json to include:
reactflow (or reactflow ecosystem package used in repo)
dagre (layout)
a chart lib: chart.js or recharts
file-saver for downloads
Add a small frontend/src/utils/api.ts to centralize axios calls used in graph.tsx.
Teaching point: show why adding deps is a careful decision; prefer small, well-documented libs.
Implement collapsible panels & layout responsiveness (on top of graph.tsx skeleton)

Add CollapsiblePanel and PanelLayout components in frontend/src/components/graph/PanelLayout.tsx.
Replace inline layout in graph.tsx return with PanelLayout that composes NodePalette, GraphCanvas, NodeInspector, ResultsPane.
Behavior: toggles alter CSS Grid template; when collapsed, canvas fills remaining width.
Teaching point: responsive CSS Grid + aria-expanded for accessibility.
Add node sizing & manual resize handles (non-intrusive)

Update GraphNode.tsx to read/set data.size and apply minW, maxW constraints (the file already sets minW).
Add ResizableHandle that modifies node.data.params.size or node.data.size via setNodes update in graph.tsx.
Also enforce internal scroll for long arrays (fix "Select Features node grows"): constrain node width in CSS, use scroll for lists.
Teaching: controlled component sizing, storing size in node data for persistence.
Edge deletion without node deletion

Use existing edge context menu logic in FlowWithDrop (extracted to GraphCanvas) and extend: context menu item "Delete edge" calls setEdges to remove single edge; add keyboard handler for Delete when an edge is selected.
Increase connection handle hit area (in GraphNode.tsx) by rendering larger, invisible elements around handles.
Teaching: event handling, hit targets, keyboard accessibility.
Node run-status visuals & backend integration (use existing run flow)

Keep current buildSpec, runMutation, SSE/polling logic in graph.tsx.
Move per-node status dot rendering into GraphNode.tsx (read data.runStatus).
Add setNodeStatus(nodeId, status) helper in graph.tsx and reuse in SSE onmessage to update nodes via setNodes.
Teaching: mapping backend run-state to UI, optimistic updates, use of TanStack Query in graph.tsx.
Plot node, ExternalData node, CustomCode node — build as new nodeInfo types in palette and probe backend endpoints

Add new node renderers under frontend/src/components/graph/nodes/:
PlotNode.tsx — loads artifact by path from backend (via artifact endpoints) and renders chart.
ExternalDataNode.tsx — fetches forecast via existing datasource endpoints (e.g., /api/v1/graphs/datasource-info/... or /api/v1/graphs/datasource/*) and stores result in node params; provide persistToDB toggle.
CustomCodeNode.tsx — stores code in data.params.code. Execution: UI sends code in buildSpec only when sandbox:true and backend must guard execution.
Backend changes: extend graphs.py to support artifact serving and a guarded /graphs/run option for sandboxed code execution.
Teaching: security trade-offs; how to design server guardrails.
Workflow export as Python (client + server)

Client: implement exporter utility ([frontend/src/components/graph/exporter.ts]) that maps node types to Python snippets and performs topological ordering using computeAutoLayout helper or real DAG sort; provide "Quick Export" button in the editor toolbar that downloads script via file-saver.
Server: add /api/v1/graphs/export in [backend/app/api/routes/graphs.py] to perform canonical export using backend node registry for authoritative templates, and optionally save to artifacts.
Teaching: string templating vs AST, deterministic ordering, server vs client responsibilities.
Auto-layout options (LR, TB, compact)

Replace or augment computeAutoLayout in [frontend/src/components/graph/layout.ts] with dagre-based layout; expose LR, TB, and compact modes in a toolbar control in graph.tsx.
Teaching: layout algorithms, why dagre beats naive topological positioning for complex graphs.
Tests, docs, and step commits

Add tests mirroring current frontend/test/graph.test.tsx patterns: unit tests for reducer-like changes in graph.tsx (e.g., add node, delete edge), and component tests for GraphNode and NodePalette.
Add a learning guide GRAPH_TUTORIAL.md describing: starting from graph.tsx, how to refactor into components, why each design choice was made, and exercises (add new node type, implement websocket, add undo/redo).
Teaching point: iterative refactor, small commits, maintain feature parity.
Verification

Start frontend:
Start backend:
Smoke tests to run after each refactor step:
Graph page loads and behavior unchanged.
Drag node from palette → canvas; connect nodes; delete an edge via context menu.
Resize a node; inspect that data.size persists after save/export.
Run a workflow; node dots update via SSE/polling (existing logic in graph.tsx).
Quick-export generates a syntactically plausible Python file.
Decisions & rationale (focused on using graph.tsx)

Minimal risk refactor: keep GraphPage in graph.tsx and extract only presentational and utility parts so students can see incremental improvement.
Preserve existing backend integration points used in graph.tsx (e.g., /api/v1/graphs/run, /api/v1/graphs/workflows, SSE endpoint) to avoid breaking server contract and to teach API-first design.
Client-side export for convenience; server-side export for authoritative, auditable scripts — teach when each is appropriate.
Custom code execution must be server-guarded; teach security-first approach (no client-side arbitrary execution).
Files to create or edit (concrete list)

Edit: graph.tsx — keep GraphPage, refactor imports to new components incrementally.
Add: frontend/src/components/graph/GraphCanvas.tsx
Add: frontend/src/components/graph/GraphNode.tsx
Add: frontend/src/components/graph/NodePalette.tsx
Add: frontend/src/components/graph/NodeInspector.tsx
Add: frontend/src/components/graph/ResultsPane.tsx
Add: frontend/src/components/graph/layout.ts
Add: frontend/src/components/graph/exporter.ts
Add: frontend/src/components/graph/nodes/PlotNode.tsx, ExternalDataNode.tsx, CustomCodeNode.tsx
Edit/extend: package.json — add dependencies
Edit/extend: graphs.py — export endpoint, artifact serving, sandbox flag handling
Add docs: GRAPH_TUTORIAL.md