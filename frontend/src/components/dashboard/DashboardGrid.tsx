/**
 * DashboardGrid (6.1) — auto-populates a 12-column panel grid from a run result.
 *
 * Instead of showing all node outputs at once, the user selects a **stage**
 * (node) from a dropdown and only panels for that stage are rendered.
 *
 * One panel is rendered for every output slot of the selected node:
 *   ◻ Plot  node  outputs ("figure")    → 6-column panel showing the chart
 *   ◻ Other node  outputs ("dataframe") → 12-column panel showing a table
 *   ◻ Model node  outputs ("model")     → 4-column panel with download link
 *   ◻ Anything else                     → 6-column raw JSON panel
 *
 * Panels with only `_timings_` (internal) or empty output are skipped.
 * The grid mirrors Grafana's `gridPos` concept: every item declares a
 * `colSpan` from 1–12.
 */
import { useState, useMemo, useEffect } from "react"
import {
  Box,
  Flex,
  Grid,
  GridItem,
  Select,
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

/** Extract unique stage / node IDs that have visualisable outputs. */
function extractStages(panels: PanelDescriptor[]): string[] {
  const seen = new Set<string>()
  const stages: string[] = []
  for (const p of panels) {
    if (!seen.has(p.nodeId)) {
      seen.add(p.nodeId)
      stages.push(p.nodeId)
    }
  }
  return stages
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DashboardGridProps {
  /** Raw `result` dict from `GET /graphs/{run_id}/result`. */
  result: Record<string, unknown>
}

export function DashboardGrid({ result }: DashboardGridProps) {
  const allPanels = useMemo(() => extractPanels(result), [result])
  const stages = useMemo(() => extractStages(allPanels), [allPanels])
  const [selectedStage, setSelectedStage] = useState<string>("")

  // Auto-select the first stage when data changes
  useEffect(() => {
    if (stages.length > 0 && (!selectedStage || !stages.includes(selectedStage))) {
      setSelectedStage(stages[0])
    }
  }, [stages, selectedStage])

  if (allPanels.length === 0) {
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

  const filteredPanels = allPanels.filter((p) => p.nodeId === selectedStage)

  return (
    <Box>
      {/* ── Stage selector ─────────────────────────────────────────────── */}
      <Flex
        align="center"
        gap={3}
        mb={5}
        p={3}
        bg="white"
        border="1px solid"
        borderColor="gray.200"
        borderRadius="lg"
        shadow="sm"
      >
        <Text
          fontSize="sm"
          fontWeight="semibold"
          color="gray.600"
          whiteSpace="nowrap"
          flexShrink={0}
        >
          Select the stage you want to visualize
        </Text>
        <Select
          size="sm"
          value={selectedStage}
          onChange={(e) => setSelectedStage(e.target.value)}
          maxW="360px"
          bg="gray.50"
          borderColor="gray.300"
          _hover={{ borderColor: "green.400" }}
          _focus={{ borderColor: "green.500", boxShadow: "0 0 0 1px var(--chakra-colors-green-500)" }}
          icon={
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          }
          iconColor="gray.600"
          iconSize="16px"
        >
          {stages.map((stage) => {
            // Show a count of outputs for each stage
            const count = allPanels.filter((p) => p.nodeId === stage).length
            return (
              <option key={stage} value={stage}>
                {stage} ({count} {count === 1 ? "output" : "outputs"})
              </option>
            )
          })}
        </Select>
        <Text fontSize="xs" color="gray.400">
          {stages.length} {stages.length === 1 ? "stage" : "stages"} total
        </Text>
      </Flex>

      {/* ── Panel grid for the selected stage ──────────────────────────── */}
      {filteredPanels.length === 0 ? (
        <Box
          border="2px dashed"
          borderColor="gray.200"
          borderRadius="lg"
          p={8}
          textAlign="center"
          color="gray.400"
        >
          <Text fontSize="sm">No outputs for this stage.</Text>
        </Box>
      ) : (
        <Grid
          templateColumns="repeat(12, 1fr)"
          gap={4}
          alignItems="start"
        >
          {filteredPanels.map((panel) => {
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
      )}
    </Box>
  )
}
