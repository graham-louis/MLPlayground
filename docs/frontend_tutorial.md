# Frontend Tutorial — Graph Editor (built on `graph.tsx`)

This tutorial teaches how to extend and improve the existing graph editor in `frontend/src/routes/graph.tsx` to implement the features listed in `features.md` (collapsible panels, resizable nodes, edge-only deletion, run-status UI, plot/external/custom nodes, export, auto-layout). It is written as a guided implementation plan for learners who want to modify the codebase incrementally and learn React architecture, state design, third-party integration, and backend API coordination.

**Prerequisites**
- Node.js + npm installed
- Familiarity with React (hooks), TypeScript, and basic CSS
- Knowledge of the repo: frontend lives under `frontend/` and backend under `backend/app/`.

Open the existing page: `frontend/src/routes/graph.tsx`. This file is the canonical orchestration surface: it contains React Flow usage, node/edge state, node templates, inspector UI, run logic (TanStack Query), SSE polling, and the buildSpec that the backend expects. All work in this tutorial is explicitly built on top of `graph.tsx` so you can trace behavior and preserve backend contracts.

Why start with `graph.tsx`?
- It's the single-page orchestration that already implements palette, inspector, run/export flow, and SSE integration. Reusing it minimizes API mismatches and helps learners focus on UI, not wiring.

Overview of tutorial sections
- 1. Project setup and dependencies
- 2. Small, non-breaking refactors: extract presentational components
- 3. Add collapsible, responsive panels
- 4. Make nodes stable-size and add manual resize handles
- 5. Improve edge interactions (delete edges independently, larger hit areas)
- 6. Node run-status visuals and backend sync (SSE/polling)
- 7. Plot node, ExternalData node, CustomCode node
- 8. Export workflow to Python (client quick-export + server authoritative export)
- 9. Auto-layout options (LR, TB, compact)
- 10. Tests, performance, security, and exercises

1) Project setup & dependencies

- Install additional libraries used in this tutorial (only if you need them):

```bash
cd frontend
npm install reactflow dagre chart.js file-saver
```

- Keep `graph.tsx` running as-is while you iterate. Run the frontend dev server with `npm run dev` from `frontend/` and the backend with `docker-compose up --build` or `uvicorn backend.app.main:app --reload`.

2) Small, non-breaking refactors (learning: incremental extraction)

Goal: make `graph.tsx` easier to reason about by extracting presentational parts into `frontend/src/components/graph/` while leaving `GraphPage` logic untouched. Do this in many tiny commits so you can revert easily.

Suggested initial extractions (one per commit):
- `GraphNodeComponent` → `components/graph/GraphNode.tsx` (visual node, header, handles, dot)
- `NodePalette` → `components/graph/NodePalette.tsx` (searchable palette grouped by category)
- `FlowWithDrop` → `components/graph/GraphCanvas.tsx` (React Flow provider usage, drag-drop handlers)
- `computeAutoLayout` → `components/graph/layout.ts` (initial naive layout; later swap for dagre)

Teaching notes: show how to preserve types and props. Keep behavior identical; import new components back into `graph.tsx`.

3) Collapsible, responsive panels

Goal: make the graph canvas expand when side/right/bottom panels collapse.

Implementation sketch:
- Add `components/graph/PanelLayout.tsx` implementing a CSS Grid with 3 columns (left palette, center canvas, right inspector) and an optional bottom row for results/preview.
- Panels expose a `collapsed` boolean; toggles update local `useState` in `GraphPage` so persistence is shallow. When collapsed, the grid template adjusts so the canvas column uses remaining space.

Why this design?
- Centralizing grid logic keeps `graph.tsx` simple and demonstrates responsive layout with CSS Grid and ARIA `aria-expanded` patterns.

4) Node sizing and manual resize

Problem: nodes grow when list content grows (e.g., `Select Features` node). Solution: constrain node width and let inner content scroll; provide a manual resize handle.

Implementation:
- In `GraphNode.tsx`, read optional `data.size` and apply `style={{ width: data.size?.w ?? defaultW, height: data.size?.h }}`.
- Add a small `div` handle that listens for pointer events and updates the node's `data.size` via `setNodes` (the same `setNodes` used in `graph.tsx`). Persisting size in `data` means the size survives saves/exports.
- For long lists, use `overflow:auto` inside the node content rather than letting the node expand.

Teaching notes: show controlled component patterns and storing UI state in the model vs ephemeral local state.

5) Edge interactions

Goals: delete edges without deleting nodes, increase connection hit area.

Implementation:
- Use the existing context menu code in `FlowWithDrop` / `GraphCanvas` to add a "Delete edge" item that calls `setEdges(edges.filter(e => e.id !== targetId))`.
- Make connection handles visually larger by rendering an additional invisible target element (bigger circle with `pointer-events:all; opacity:0`) around the real handle.
- Add keyboard listener in `GraphPage` to delete selected edge(s) when `Delete` is pressed.

Teaching notes: event propagation, hit area UX, and keyboard accessibility.

6) Node run-status visuals & backend sync

Existing behavior: `graph.tsx` already has TanStack Query usage to POST `/api/v1/graphs/run`, SSE stream `/api/v1/graphs/{runId}/stream`, and per-node status mapping onto nodes.

Enhancements:
- Move rendering of the status dot into `GraphNode.tsx` (reading `data.runStatus`).
- Add a `setNodeStatus(nodeId, status)` helper in `graph.tsx` used by SSE `onmessage` to update `nodes` with `setNodes(prev => prev.map(n => n.id === nodeId ? {...n, data:{...n.data, runStatus: status}}:n))`.
- Add clear visual states: running, success, error, cached; and small tooltips.

Teaching notes: optimistic UI patterns and the trade-offs between SSE and polling (both already present in the codebase).

7) New node types: Plot, ExternalData, CustomCode

Plot node
- `PlotNode` fetches artifact paths or numerical arrays returned from a node's outputs. Use a charting library (Chart.js) to render residuals. Backend should expose artifacts under `artifacts/` or via an endpoint — call the same API patterns used in `graph.tsx` queries.

ExternalData node
- UI toggles `persistToDB`. When toggled off, the frontend caches the fetched data in `data.params._cached` and does not send it to backend when building `spec`. Implement fetch via existing datasources endpoints (e.g., `/api/v1/graphs/datasource-info/` and appropriate datasource endpoints).

CustomCode node
- Stores code in `data.params.code`. Important: never execute arbitrary user code on the client for security. When executing, send to backend with `{ sandbox: true }` and require server-side validation/sandboxing. Add a clear warning in the UI.

Teaching notes: emphasize secure-by-default behavior and server-side guards (like restricted subprocesses, resource limits, or disabled network access).

8) Export workflow to Python

Two modes:
- Quick client-side export: map each `node_type` to a small Python template and topologically order nodes on the client; join templates and download with `file-saver`.
- Authoritative server export: POST the spec to `/api/v1/graphs/export` which uses backend node registry to construct a canonical, runnable Python script and optionally save it to `artifacts/`.

Key implementation points:
- Use topological sort when generating code to ensure dependencies are respected.
- Prefer server-side export for production because backend knows how nodes map to Python APIs and can validate security concerns (CustomCode, paths, artifact references).

9) Auto-layout options (LR, TB, compact)

Replace or augment `computeAutoLayout` with a `dagre`-powered layout in `components/graph/layout.ts`. Provide a small toolbar control in `graph.tsx` offering `Left→Right`, `Top→Bottom`, and `Compact` modes that call the layout function and `setNodes` with updated positions.

Teaching notes: explain the difference between naive topological column assignment and force-directed / layered DAG layouts.

10) Tests, performance, security, and exercises

Testing
- Add unit tests for reducer-like logic (node add/delete, edge add/delete) and component tests for `GraphNode` and `NodePalette`. Follow the existing frontend tests under `frontend/test/`.

Performance
- For large node libraries, virtualize the palette list.
- Debounce heavy updates like auto-layout and use `React.memo` to prevent unnecessary re-renders.

Security
- Never run arbitrary client-supplied Python without a sandbox.
- Ensure file uploads (see `FilePathUpload`) validate file types and sizes.

Exercises for learners
- 1: Extract `GraphNodeComponent` to a separate file and add a resize handle.
- 2: Add a "Delete edge" context-menu action and support `Delete` key.
- 3: Implement a simple client-side exporter that maps `trainer` node to a short Python function and downloads the script.

Where to look in the repo
- `frontend/src/routes/graph.tsx` — start here; all orchestration lives here.
- `frontend/test/` — component/unit test examples.
- `backend/app/api/routes/graphs.py` — run/export/validate endpoints; extend here for server-side export and sandbox flags.

Next steps
- Follow the incremental extraction plan: make one small change, run the app, and verify no behavior changes. Then proceed to add the UX improvements described.

If you want, I can now create the initial component templates (non-breaking) for `GraphNode`, `NodePalette`, and `GraphCanvas` and a small example export utility. Tell me which file to scaffold first.

---
Revision note: this guide is intentionally built on top of `graph.tsx` to minimize API friction and to provide a single source of truth for learners. It references ComfyUI patterns (collapsible sidebars, node palette, resizable nodes) as UX inspiration; keep design decisions simple and explain trade-offs as you implement them.
