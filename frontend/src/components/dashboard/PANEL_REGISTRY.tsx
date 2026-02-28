/**
 * Panel registry (6.2) — maps serialized output `__type__` values to React components.
 *
 * Adding a new panel type:
 *   1. Create a component implementing `PanelRendererProps`.
 *   2. Add an entry to `PANEL_REGISTRY` below.
 *   3. Zero frontend wiring elsewhere — `DashboardGrid` discovers it automatically.
 *
 * Supported types:
 *   "figure"    — base64-encoded PNG from PlotNode
 *   "dataframe" — paginated preview table from any DataFrame-outputting node
 *   "model"     — sklearn-compatible model (shows path + download)
 *   "raw"       — fallback for any other JSON-serialisable value
 */
import {
  Badge,
  Box,
  Button,
  Flex,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react"
import type { FC } from "react"
import { useState } from "react"

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface PanelRendererProps {
  /** The raw serialised value object from the run result JSON. */
  value: Record<string, unknown>
  /** The graph node instance ID that produced this output. */
  nodeId: string
  /** The output slot name (e.g. "figure", "dataframe"). */
  slot: string
}

export type PanelRenderer = FC<PanelRendererProps>

// ---------------------------------------------------------------------------
// Figure panel — renders base64 PNG produced by PlotNode
// ---------------------------------------------------------------------------

const FigurePanel: PanelRenderer = ({ value, slot }) => {
  const fig = value as { data: string; format?: string }
  if (!fig.data) {
    return <Text fontSize="sm" color="gray.400">No image data.</Text>
  }
  return (
    <Box textAlign="center" overflow="hidden">
      <img
        src={`data:image/${fig.format ?? "png"};base64,${fig.data}`}
        alt={`${slot} chart`}
        style={{ maxWidth: "100%", display: "inline-block", borderRadius: "4px" }}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// DataFrame panel — paginated preview table
// ---------------------------------------------------------------------------

const PAGE_SIZE = 15

const DataframePanel: PanelRenderer = ({ value }) => {
  const df = value as {
    shape: number[]
    columns: string[]
    preview_rows: Record<string, unknown>[]
    path?: string
  }
  const [page, setPage] = useState(0)
  const rows = df.preview_rows ?? []
  const cols = df.columns ?? Object.keys(rows[0] ?? {})
  const total = rows.length
  const pageRows = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  if (cols.length === 0) {
    return <Text fontSize="sm" color="gray.400">Empty DataFrame.</Text>
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={2} flexWrap="wrap" gap={2}>
        <Text fontSize="xs" color="gray.500">
          {df.shape?.[0] ?? rows.length} rows × {df.shape?.[1] ?? cols.length} cols
          {total < (df.shape?.[0] ?? total) ? ` (showing first ${total})` : ""}
        </Text>
        {df.path && (
          <Badge
            as="a"
            href={`/api/v1/graphs/artifacts/${df.path}`}
            colorScheme="blue"
            fontSize="xs"
            cursor="pointer"
            px={2}
            py={0.5}
          >
            ↓ Download parquet
          </Badge>
        )}
      </Flex>

      <Box overflowX="auto">
        <Table size="xs" variant="simple">
          <Thead>
            <Tr>
              {cols.map((col) => (
                <Th key={col} fontSize="xs" p={1} whiteSpace="nowrap">
                  {col}
                </Th>
              ))}
            </Tr>
          </Thead>
          <Tbody>
            {pageRows.map((row, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: preview rows
              <Tr key={i}>
                {cols.map((col, j) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: preview cells
                  <Td key={j} fontSize="xs" p={1} whiteSpace="nowrap">
                    {String(row[col] ?? "")}
                  </Td>
                ))}
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>

      {total > PAGE_SIZE && (
        <Flex align="center" gap={2} mt={2}>
          <Button
            size="xs"
            isDisabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            ‹
          </Button>
          <Text fontSize="xs" color="gray.500">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </Text>
          <Button
            size="xs"
            isDisabled={(page + 1) * PAGE_SIZE >= total}
            onClick={() => setPage((p) => p + 1)}
          >
            ›
          </Button>
        </Flex>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Model panel — sklearn model reference with download link
// ---------------------------------------------------------------------------

const ModelPanel: PanelRenderer = ({ value }) => {
  const m = value as { path: string }
  return (
    <Box>
      <Text fontSize="sm" color="gray.600" mb={2}>
        🤖 Trained model artifact
      </Text>
      {m.path && (
        <Badge
          as="a"
          href={`/api/v1/graphs/artifacts/${m.path}`}
          colorScheme="purple"
          fontSize="xs"
          cursor="pointer"
          px={2}
          py={0.5}
        >
          ↓ Download model (.pkl)
        </Badge>
      )}
      <Text fontSize="xs" color="gray.400" mt={2} fontFamily="mono">
        {m.path}
      </Text>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Raw panel — fallback for unknown / primitive types
// ---------------------------------------------------------------------------

const RawPanel: PanelRenderer = ({ value }) => {
  return (
    <Box
      as="pre"
      fontSize="xs"
      color="gray.700"
      whiteSpace="pre-wrap"
      wordBreak="break-all"
      fontFamily="mono"
      bg="gray.50"
      p={2}
      borderRadius="md"
      overflow="auto"
      maxH="300px"
    >
      {JSON.stringify(value, null, 2)}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Registry — maps __type__ → component
// ---------------------------------------------------------------------------

export const PANEL_REGISTRY: Record<string, PanelRenderer> = {
  figure: FigurePanel,
  dataframe: DataframePanel,
  model: ModelPanel,
  raw: RawPanel,
}

/** Infer the human-readable type label for a raw panel value. */
export function inferPanelType(value: unknown): string {
  if (value && typeof value === "object") {
    const t = (value as Record<string, unknown>).__type__
    if (typeof t === "string") return t
  }
  return "raw"
}

/** Suggested grid column span for each panel type (out of 12). */
export const PANEL_COL_SPAN: Record<string, number> = {
  figure: 6,
  dataframe: 12,
  model: 4,
  raw: 6,
}
