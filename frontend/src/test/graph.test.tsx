import React from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it, vi } from "vitest"
import { Route } from "../routes/graph"
import {
  GRAPH_RESULT_RESPONSE,
  GRAPH_RUN_RESPONSE,
  GRAPH_STATUS_RESPONSE,
  GRAPH_VALIDATE_RESPONSE,
  SAVED_WORKFLOW_DETAIL,
  SAVED_WORKFLOWS_RESPONSE,
  server,
} from "./handlers"
import { renderWithProviders } from "./utils"

// @xyflow/react uses ResizeObserver and SVG features not available in jsdom.
vi.mock("@xyflow/react", () => {
  const React = require("react")
  return {
    ReactFlow: ({ children, onNodeClick, onPaneClick }: {
      children?: React.ReactNode
      onNodeClick?: (e: unknown, node: { id: string }) => void
      onPaneClick?: () => void
    }) => (
      <div data-testid="react-flow" onClick={() => onPaneClick?.()}>
        {children}
        <button
          data-testid="mock-node-click"
          onClick={(e) => { e.stopPropagation(); onNodeClick?.(e, { id: "n1" }) }}
        >
          click node
        </button>
      </div>
    ),
    Background: () => <div data-testid="rf-background" />,
    Controls: () => <div data-testid="rf-controls" />,
    MiniMap: () => <div data-testid="rf-minimap" />,
    Handle: ({ id }: { id: string }) => <div data-testid={`handle-${id}`} />,
    Position: { Left: "left", Right: "right" },
    addEdge: (connection: unknown, edges: unknown[]) => [...edges, connection],
    useNodesState: (init: unknown[]) => {
      const [nodes, setNodes] = React.useState(init)
      return [nodes, setNodes, () => {}]
    },
    useEdgesState: (init: unknown[]) => {
      const [edges, setEdges] = React.useState(init)
      return [edges, setEdges, () => {}]
    },
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    useReactFlow: () => ({
      screenToFlowPosition: (pos: { x: number; y: number }) => pos,
    }),
  }
})

// Patch scrollTo for Chakra Menu
Object.defineProperty(window.HTMLElement.prototype, "scrollTo", {
  value: () => {},
  configurable: true,
  writable: true,
})

const GraphPage = Route.options.component as React.ComponentType

// ── Helper: load the default template (opens Templates menu, clicks CSV template) ──
async function loadCsvTemplate(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(screen.getByRole("button", { name: /Templates/i })).toBeInTheDocument())
  await user.click(screen.getByRole("button", { name: /Templates/i }))
  await waitFor(() => expect(screen.getByText(/CSV → Filter → Preview/)).toBeInTheDocument())
  await user.click(screen.getByText(/CSV → Filter → Preview/))
  await waitFor(() => expect(screen.getByText(/3 nodes/)).toBeInTheDocument())
}

// ── Helper: load the yield prediction template ──
async function loadYieldTemplate(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(screen.getByRole("button", { name: /Templates/i })).toBeInTheDocument())
  await user.click(screen.getByRole("button", { name: /Templates/i }))
  await waitFor(() => expect(screen.getByText(/Yield Prediction/)).toBeInTheDocument())
  await user.click(screen.getByText(/Yield Prediction/))
  await waitFor(() => expect(screen.getByText(/9 nodes/)).toBeInTheDocument())
}

// ── Structure ──────────────────────────────────────────────────────────────

describe("Graph page – structure", () => {
  it("renders the toolbar with Validate, Run, and Templates buttons", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText("Validate")).toBeInTheDocument())
    expect(screen.getByText("▶ Run")).toBeInTheDocument()
    expect(screen.getByText(/Templates/)).toBeInTheDocument()
  })

  it("renders the Graph Editor heading", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/Graph Editor/)).toBeInTheDocument())
  })

  it("shows empty state hint when canvas is empty", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/Drag nodes from the palette/)).toBeInTheDocument())
  })

  it("shows node and edge count in toolbar", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    expect(screen.getByText(/3 nodes/)).toBeInTheDocument()
    expect(screen.getByText(/2 edges/)).toBeInTheDocument()
  })

  it("toolbar has auto-layout, save, and workflows buttons", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/⚙ Layout/)).toBeInTheDocument())
    expect(screen.getByRole("button", { name: /💾 Save/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /📂 Workflows/i })).toBeInTheDocument()
  })

  it("shows keyboard shortcut hint tooltip trigger", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByLabelText("Keyboard shortcuts")).toBeInTheDocument())
  })
})

// ── Palette ────────────────────────────────────────────────────────────────

describe("Graph page – palette", () => {
  it("loads nodes from GET /api/v1/graphs/nodes and shows them in the palette", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText("CSV Source")).toBeInTheDocument())
    expect(screen.getByText("Filter")).toBeInTheDocument()
    expect(screen.getByText("Preview")).toBeInTheDocument()
    expect(screen.getByText("Database Source")).toBeInTheDocument()
  })

  it("groups nodes by category in the palette", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText("Sources")).toBeInTheDocument())
    expect(screen.getByText("Transforms")).toBeInTheDocument()
    expect(screen.getByText("Utilities")).toBeInTheDocument()
  })

  it("shows error state when nodes API returns 500 without crashing", async () => {
    server.use(
      http.get("/api/v1/graphs/nodes", () => HttpResponse.json({ detail: "error" }, { status: 500 }))
    )
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/Node Library/)).toBeInTheDocument())
  })
})

// ── Templates ──────────────────────────────────────────────────────────────

describe("Graph page – templates", () => {
  it("shows CSV template option in the menu", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByRole("button", { name: /Templates/i })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /Templates/i }))
    await waitFor(() => expect(screen.getByText(/CSV → Filter → Preview/)).toBeInTheDocument())
  })

  it("loads CSV template: places 3 nodes and 2 edges on the canvas", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    expect(screen.getByText(/3 nodes/)).toBeInTheDocument()
    expect(screen.getByText(/2 edges/)).toBeInTheDocument()
    // Empty state hint should disappear once nodes are present
    expect(screen.queryByText(/Drag nodes from the palette/)).not.toBeInTheDocument()
  })
})

// ── Validate ───────────────────────────────────────────────────────────────

describe("Graph page – validate", () => {
  it("calls POST /api/v1/graphs/validate and shows success toast", async () => {
    const user = userEvent.setup()
    let validated = false
    server.use(
      http.post("/api/v1/graphs/validate", () => {
        validated = true
        return HttpResponse.json(GRAPH_VALIDATE_RESPONSE)
      })
    )
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText("Validate")).toBeInTheDocument())
    await user.click(screen.getByText("Validate"))
    await waitFor(() => expect(validated).toBe(true))
  })
})

// ── Template end-to-end run ────────────────────────────────────────────────

describe("Graph page – template end-to-end run", () => {
  it("loads template → runs graph → polls status → shows result", async () => {
    const user = userEvent.setup()
    let ran = false
    let polled = false
    server.use(
      http.post("/api/v1/graphs/run", () => {
        ran = true
        return HttpResponse.json(GRAPH_RUN_RESPONSE)
      }),
      http.get("/api/v1/graphs/:runId/status", () => {
        polled = true
        return HttpResponse.json(GRAPH_STATUS_RESPONSE)
      }),
      http.get("/api/v1/graphs/:runId/result", () =>
        HttpResponse.json(GRAPH_RESULT_RESPONSE)
      ),
    )
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByText("▶ Run"))
    await waitFor(() => expect(ran).toBe(true), { timeout: 5000 })
    await waitFor(() => expect(polled).toBe(true), { timeout: 5000 })
  })

  it("▶ Run button is disabled when canvas is empty", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText("▶ Run")).toBeInTheDocument())
    expect(screen.getByText("▶ Run")).toBeDisabled()
  })

  it("▶ Run button is enabled after loading a template", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    expect(screen.getByText("▶ Run")).not.toBeDisabled()
  })
})

// ── Auto-layout ────────────────────────────────────────────────────────────

describe("Graph page – auto-layout", () => {
  it("Layout button is disabled on empty canvas", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/Layout/)).toBeInTheDocument())
    expect(screen.getByText(/Layout/)).toBeDisabled()
  })

  it("Layout button is enabled after loading a template", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    expect(screen.getByText(/Layout/)).not.toBeDisabled()
  })

  it("clicking Layout button does not crash the page", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByText(/Layout/))
    // Canvas should still show the node/edge counts
    await waitFor(() => expect(screen.getByText(/3 nodes/)).toBeInTheDocument())
  })
})

// ── Save / Load workflows ──────────────────────────────────────────────────

describe("Graph page – workflows", () => {
  it("loads saved workflows list from API on mount", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/Workflows/)).toBeInTheDocument())
    // Badge shows workflow count
    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument())
  })

  it("Save button is disabled on empty canvas", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByRole("button", { name: /💾 Save/i })).toBeInTheDocument())
    expect(screen.getByRole("button", { name: /💾 Save/i })).toBeDisabled()
  })

  it("opens Save popover after loading template", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    const saveBtn = screen.getByRole("button", { name: /💾 Save/i })
    expect(saveBtn).not.toBeDisabled()
    await user.click(saveBtn)
    await waitFor(() => expect(screen.getByPlaceholderText(/Workflow name/i)).toBeInTheDocument())
  })

  it("shows workflow list in Workflows menu", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByRole("button", { name: /Workflows/i })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /Workflows/i }))
    await waitFor(() => expect(screen.getByText("My Workflow")).toBeInTheDocument())
  })

  it("saves a new workflow via POST /api/v1/graphs/workflows", async () => {
    const user = userEvent.setup()
    let saved = false
    server.use(
      http.post("/api/v1/graphs/workflows", () => {
        saved = true
        return HttpResponse.json({ ...SAVED_WORKFLOW_DETAIL, id: 5, name: "Test Save" }, { status: 201 })
      })
    )
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByRole("button", { name: /💾 Save/i }))
    await waitFor(() => expect(screen.getByPlaceholderText(/Workflow name/i)).toBeInTheDocument())
    await user.type(screen.getByPlaceholderText(/Workflow name/i), "Test Save")
    // Click the Save button inside the popover (not the toolbar one)
    const saveBtns = screen.getAllByRole("button", { name: /^Save$/ })
    await user.click(saveBtns[saveBtns.length - 1])
    await waitFor(() => expect(saved).toBe(true))
  })

  it("loads a workflow from the Workflows menu", async () => {
    const user = userEvent.setup()
    let fetched = false
    server.use(
      http.get("/api/v1/graphs/workflows/:id", () => {
        fetched = true
        return HttpResponse.json(SAVED_WORKFLOW_DETAIL)
      })
    )
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByRole("button", { name: /📂 Workflows/i })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /📂 Workflows/i }))
    await waitFor(() => expect(screen.getByText("My Workflow")).toBeInTheDocument())
    // Click the Load text button next to "My Workflow"
    const loadBtns = screen.getAllByText("Load")
    await user.click(loadBtns[0])
    await waitFor(() => expect(fetched).toBe(true))
  })
})

// ── Node inspector ─────────────────────────────────────────────────────────

describe("Graph page – node inspector", () => {
  it("shows inspector placeholder when no node is selected", async () => {
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByText(/Select a node to edit/)).toBeInTheDocument())
  })

  it("shows node detail in inspector when a node is selected via mock click", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    // The mock ReactFlow fires onNodeClick with id "n1"
    await user.click(screen.getByTestId("mock-node-click"))
    // Inspector panel should no longer show the placeholder text
    await waitFor(() =>
      expect(screen.queryByText(/Select a node to edit/)).not.toBeInTheDocument()
    )
  })
})

// ── Clear canvas ───────────────────────────────────────────────────────────

describe("Graph page – clear canvas", () => {
  it("Clear button removes all nodes and shows empty state", async () => {
    const user = userEvent.setup()
    // Mock window.confirm to auto-confirm
    vi.spyOn(window, "confirm").mockReturnValue(true)
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByRole("button", { name: /Clear/i }))
    await waitFor(() => expect(screen.getByText(/0 nodes/)).toBeInTheDocument())
    vi.restoreAllMocks()
  })
})

// ── Template param regression ──────────────────────────────────────────────

describe("Graph page – CSV template param regression", () => {
  it("template run sends file_path (not path) in csv_source params", async () => {
    const user = userEvent.setup()
    let capturedBody: unknown = null
    server.use(
      http.post("/api/v1/graphs/run", async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(GRAPH_RUN_RESPONSE)
      }),
    )
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByText("▶ Run"))
    await waitFor(() => expect(capturedBody).not.toBeNull())
    const body = capturedBody as { nodes: { instance_id: string; params: Record<string, unknown> }[] }
    const n1 = body.nodes.find((n) => n.instance_id === "n1")
    expect(n1).toBeDefined()
    expect(n1!.params).toHaveProperty("file_path")
    expect(n1!.params).not.toHaveProperty("path")
  })
})

// ── RunResultView rendering ────────────────────────────────────────────────

describe("Graph page – RunResultView", () => {
  it("renders PreviewTable when result slot has {rows: [...]}", async () => {
    const user = userEvent.setup()
    server.use(
      http.post("/api/v1/graphs/run", () => HttpResponse.json(GRAPH_RUN_RESPONSE)),
      http.get("/api/v1/graphs/:runId/status", () => HttpResponse.json(GRAPH_STATUS_RESPONSE)),
      http.get("/api/v1/graphs/:runId/result", () => HttpResponse.json(GRAPH_RESULT_RESPONSE)),
    )
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByText("▶ Run"))
    // Wait for result — should show preview table rows
    await waitFor(
      () => expect(screen.getByText(/col1/i)).toBeInTheDocument(),
      { timeout: 5000 },
    )
  })

  it("renders 'X rows × Y cols' label for DataFrame outputs", async () => {
    const user = userEvent.setup()
    server.use(
      http.post("/api/v1/graphs/run", () => HttpResponse.json(GRAPH_RUN_RESPONSE)),
      http.get("/api/v1/graphs/:runId/status", () => HttpResponse.json(GRAPH_STATUS_RESPONSE)),
      http.get("/api/v1/graphs/:runId/result", () => HttpResponse.json(GRAPH_RESULT_RESPONSE)),
    )
    renderWithProviders(<GraphPage />)
    await loadCsvTemplate(user)
    await user.click(screen.getByText("▶ Run"))
    await waitFor(
      () => expect(screen.getByText(/2 rows × 2 cols/)).toBeInTheDocument(),
      { timeout: 5000 },
    )
  })
})

// ── Yield Prediction template ──────────────────────────────────────────────

describe("Graph page – Yield Prediction template", () => {
  it("shows 'Yield Prediction' option in the Templates menu", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await waitFor(() => expect(screen.getByRole("button", { name: /Templates/i })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /Templates/i }))
    await waitFor(() => expect(screen.getByText(/Yield Prediction/)).toBeInTheDocument())
  })

  it("loads Yield Prediction template: places 9 nodes and 8 edges on the canvas", async () => {
    const user = userEvent.setup()
    renderWithProviders(<GraphPage />)
    await loadYieldTemplate(user)
    expect(screen.getByText(/9 nodes/)).toBeInTheDocument()
    expect(screen.getByText(/8 edges/)).toBeInTheDocument()
  })

  it("POST /run payload for Yield Prediction template contains correct node types", async () => {
    const user = userEvent.setup()
    let capturedBody: unknown = null
    server.use(
      http.post("/api/v1/graphs/run", async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(GRAPH_RUN_RESPONSE)
      }),
    )
    renderWithProviders(<GraphPage />)
    await loadYieldTemplate(user)
    await user.click(screen.getByText("▶ Run"))
    await waitFor(() => expect(capturedBody).not.toBeNull())
    const body = capturedBody as { nodes: { instance_id: string; node_type: string; params: Record<string, unknown> }[]; edges: unknown[] }
    // Should have 9 nodes total
    expect(body.nodes).toHaveLength(9)
    // Source nodes should use database_source
    const sourceNodes = body.nodes.filter(n => n.node_type === "database_source")
    expect(sourceNodes).toHaveLength(3)
    expect(sourceNodes.map(n => n.params.datasource_key)).toEqual(
      expect.arrayContaining(["yields", "weather", "soil"])
    )
    // Join nodes
    const joinNodes = body.nodes.filter(n => n.node_type === "join")
    expect(joinNodes).toHaveLength(2)
    // Trainer node with correct target column
    const trainerNode = body.nodes.find(n => n.node_type === "trainer")
    expect(trainerNode).toBeDefined()
    expect(trainerNode!.params.target_column).toBe("value")
    expect(trainerNode!.params.model_type).toBe("random_forest")
    // select_columns and drop_na
    expect(body.nodes.some(n => n.node_type === "select_columns")).toBe(true)
    expect(body.nodes.some(n => n.node_type === "drop_na")).toBe(true)
    // preview
    expect(body.nodes.some(n => n.node_type === "preview")).toBe(true)
    // 8 edges
    expect(body.edges).toHaveLength(8)
  })

  it("join nodes in yield template have correct 'on' params", async () => {
    const user = userEvent.setup()
    let capturedBody: unknown = null
    server.use(
      http.post("/api/v1/graphs/run", async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(GRAPH_RUN_RESPONSE)
      }),
    )
    renderWithProviders(<GraphPage />)
    await loadYieldTemplate(user)
    await user.click(screen.getByText("▶ Run"))
    await waitFor(() => expect(capturedBody).not.toBeNull())
    const body = capturedBody as { nodes: { node_type: string; params: Record<string, unknown> }[] }
    const joinNodes = body.nodes.filter(n => n.node_type === "join")
    // First join: yields + weather on year/state/county
    const weatherJoin = joinNodes.find(n => (n.params.on as string[]).includes("year"))
    expect(weatherJoin).toBeDefined()
    expect(weatherJoin!.params.on).toEqual(expect.arrayContaining(["year", "state", "county"]))
    expect(weatherJoin!.params.how).toBe("inner")
    // Second join: + soil on state/county (no year)
    const soilJoin = joinNodes.find(n => !(n.params.on as string[]).includes("year"))
    expect(soilJoin).toBeDefined()
    expect(soilJoin!.params.on).toEqual(expect.arrayContaining(["state", "county"]))
    expect(soilJoin!.params.how).toBe("left")
  })
})


