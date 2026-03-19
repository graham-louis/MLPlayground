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

## Final Goal
- Create an example workflow that trains a corn yield model for North Carolina
    - Use a plot node to plot residuals of training
    - Fetch forecasted data from external source (Keep in cache but do not add to DB)
    - Use model to predict yield for 2026
    - Be able to export entire workflow as a python script


## Reorganization
Keep graph.tsx as the canonical page and orchestration surface; refactor and extend it incrementally by extracting reusable parts into frontend/src/components/graph/, add small supporting utilities, and implement new UX/features (collapsible panels, resizable nodes, edge-only deletion, node run-status, plot/external/custom nodes, export) on top of that existing file so learners can trace changes from a single, working source file to a modular, production-ready editor.

Steps

Read & keep graph.tsx as source of truth

Base file: graph.tsx
Rationale: it already contains React Flow usage, node/edge shapes, templates, inspector, run+SSE logic, and buildSpec. Building on it keeps integration with backend and preserves existing behavior for learners.
Refactor small pieces out of graph.tsx (non-breaking, stepwise)

Create components and utilities but keep GraphPage in graph.tsx. 

Minimal risk refactor: keep GraphPage in graph.tsx and extract only presentational and utility parts so students can see incremental improvement.
Preserve existing backend integration points used in graph.tsx (e.g., /api/v1/graphs/run, /api/v1/graphs/workflows, SSE endpoint) to avoid breaking server contract and to teach API-first design.
Client-side export for convenience; server-side export for authoritative, auditable scripts — teach when each is appropriate.
Custom code execution must be server-guarded; teach security-first approach (no client-side arbitrary execution).


## More Ideas
- Multiple filters in a single node.
- Nodes for getting summaries (count unique, maybe use pandas profiling)
- Run Output should not expand after each run
- Random state should not be a required variable for train model node
- Ability to drag node inspector to scale in width
- Train model node should display metrics and feature importance in a formatted way (not just JSON)
- Add persistence and auto-save so workflows don't dissapear whenever a user clicks away or refreshes the page
- Ability to run workflows up to a specific node (by user or if a node fails)
    - Enables ability to see available columns even on failed runs
- Add formatted display of parameters in nodes themselves not just node inspector
- Add ability to deploy workflows as polished decision support tool pages
    - Maybe build off of current dashboard page 
    - UI should enable user input of levers and display professional looking plots 
        - Refer to https://www.precisionsustainableag.org/decision-support-tools for decision support examples
        - Look at Grafana for professional dashboards
        - Maybe use uPlot with Grafana/ui
- Make nodes that have text input or filters be case insensitive
- Clearly label input and output slots on nodes
- Add better run status checking (which node is executing)