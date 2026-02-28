/**
 * DashboardGrid (6.1) — auto-populates a 12-column panel grid from a run result.
 *
 * One panel is rendered for every output slot of every node in the result:
 *   ◻ Plot  node  outputs ("figure")    → 6-column panel showing the chart
 *   ◻ Other node  outputs ("dataframe") → 12-column panel showing a table
 *   ◻ Model node  outputs ("model")     → 4-column panel with download link
 *   ◻ Anything else                     → 6-column raw JSON panel
 *
 * Panels with only `_timings_` (internal) or empty output are skipped.
 * The grid mirrors Grafana's `gridPos` concept: every item declares a
 * `colSpan` from 1–12.
 */
import {
  Box,
  Grid,
  GridItem,
  Text,
} from "@chakra-ui/react"
import {
  PANEL_COL_SPAN,
  PANEL_REGISTRY,
  inferPanelType,
} from "./PANEL_REGISTRY"
import { PanelChrome } from "./PanelChrome"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A flattened panel descriptor derived from a run result. */
interface PanelDescriptor {
  key: string
  nodeId: string
  slot: string
  type: string
  value: Record<string, unknown>
  downloadUrl?: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SKIP_KEYS = new Set(["_timings_"])

/** Derive a human-readable title for a panel. */
function panelTitle(nodeId: string, slot: string): string {
  return `${nodeId} / ${slot}`
}

/** Build a download URL for artifact-backed values. */
function downloadUrl(value: Record<string, unknown>): string | undefined {
  const path = value.path as string | undefined
  if (!path) return undefined
  return `/api/v1/graphs/artifacts/${path}`
}

/** Flatmap a result dict into a list of PanelDescriptors. */
function extractPanels(result: Record<string, unknown>): PanelDescriptor[] {
  const panels: PanelDescriptor[] = []
  for (const [nodeId, outputs] of Object.entries(result)) {
    if (SKIP_KEYS.has(nodeId)) continue
    if (!outputs || typeof outputs !== "object") continue
    for (const [slot, rawValue] of Object.entries(
      outputs as Record<string, unknown>,
    )) {
      if (rawValue === null || rawValue === undefined) continue
      // Only show object-typed outputs (skip primitive scalars at top level)
      if (typeof rawValue !== "object") continue
      const value = rawValue as Record<string, unknown>
      const type = inferPanelType(value)
      panels.push({
        key: `${nodeId}:${slot}`,
        nodeId,
        slot,
        type,
        value,
        downloadUrl: downloadUrl(value),
      })
    }
  }
  return panels
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DashboardGridProps {
  /** Raw `result` dict from `GET /graphs/{run_id}/result`. */
  result: Record<string, unknown>
}

export function DashboardGrid({ result }: DashboardGridProps) {
  const panels = extractPanels(result)

  if (panels.length === 0) {
    return (
      <Box
        border="2px dashed"
        borderColor="gray.300"
        borderRadius="lg"
        p={12}
        textAlign="center"
        color="gray.400"
      >
        <Text fontSize="2xl" mb={2}>📊</Text>
        <Text fontWeight="medium">No visualisable outputs in this run.</Text>
        <Text fontSize="sm" mt={1}>
          Add a Plot node or inspect per-node outputs in the Graph editor.
        </Text>
      </Box>
    )
  }

  return (
    <Grid
      templateColumns="repeat(12, 1fr)"
      gap={4}
      alignItems="start"
    >
      {panels.map((panel) => {
        const Renderer = PANEL_REGISTRY[panel.type] ?? PANEL_REGISTRY.raw
        const colSpan = PANEL_COL_SPAN[panel.type] ?? 6

        return (
          <GridItem
            key={panel.key}
            colSpan={{ base: 12, md: colSpan }}
          >
            {/* Min height keeps figure panels from collapsing while images load */}
            <Box minH={panel.type === "figure" ? "280px" : undefined}>
              <PanelChrome
                title={panelTitle(panel.nodeId, panel.slot)}
                subtitle={panel.type}
                downloadUrl={panel.downloadUrl}
                downloadFilename={`${panel.nodeId}_${panel.slot}`}
              >
                <Renderer
                  value={panel.value}
                  nodeId={panel.nodeId}
                  slot={panel.slot}
                />
              </PanelChrome>
            </Box>
          </GridItem>
        )
      })}
    </Grid>
  )
}
