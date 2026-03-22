/**
 * RunSummaryPanel — "Summary" tab for a completed graph run.
 *
 * Shows at-a-glance information:
 *   • Pipeline status strip (per-node success / cached / error badges)
 *   • Execution timing breakdown
 *   • Model metrics cards (R², RMSE, sample counts)
 *   • Feature importance bar chart (horizontal)
 *   • Data shape tracker (rows × cols at each stage)
 */
import {
  Badge,
  Box,
  Flex,
  Progress,
  SimpleGrid,
  Stat,
  StatHelpText,
  StatLabel,
  StatNumber,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
} from "@chakra-ui/react"
import { useMemo } from "react"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunSummaryPanelProps {
  result: Record<string, unknown>
  nodeStatuses: Record<string, string>
}

interface MetricsInfo {
  nodeId: string
  metrics: Record<string, unknown>
}

interface DataframeShape {
  nodeId: string
  slot: string
  rows: number
  cols: number
  columns: string[]
}

interface TimingEntry {
  nodeId: string
  seconds: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_BADGE_COLOR: Record<string, string> = {
  success: "green",
  done: "green",
  cached: "purple",
  bypassed: "gray",
  error: "red",
  pending: "yellow",
  running: "blue",
}

const STATUS_ICON: Record<string, string> = {
  success: "✓",
  done: "✓",
  cached: "◷",
  bypassed: "⊘",
  error: "✕",
  pending: "·",
  running: "⟳",
}

function extractMetrics(result: Record<string, unknown>): MetricsInfo[] {
  const items: MetricsInfo[] = []
  for (const [nodeId, outputs] of Object.entries(result)) {
    if (nodeId === "_timings_" || !outputs || typeof outputs !== "object") continue
    const slots = outputs as Record<string, unknown>
    for (const [slot, rawValue] of Object.entries(slots)) {
      if (!rawValue || typeof rawValue !== "object") continue
      const v = rawValue as Record<string, unknown>
      // Detect a metrics dict: has r2, rmse, or accuracy keys
      if (
        v.r2 !== undefined ||
        v.rmse !== undefined ||
        v.accuracy !== undefined ||
        v.mean !== undefined ||
        v.scoring !== undefined
      ) {
        items.push({ nodeId, metrics: v })
      }
    }
  }
  return items
}

function extractDataframeShapes(result: Record<string, unknown>): DataframeShape[] {
  const shapes: DataframeShape[] = []
  for (const [nodeId, outputs] of Object.entries(result)) {
    if (nodeId === "_timings_" || !outputs || typeof outputs !== "object") continue
    const slots = outputs as Record<string, unknown>
    for (const [slot, rawValue] of Object.entries(slots)) {
      if (!rawValue || typeof rawValue !== "object") continue
      const v = rawValue as Record<string, unknown>
      if (v.__type__ === "dataframe" && Array.isArray(v.shape)) {
        shapes.push({
          nodeId,
          slot,
          rows: (v.shape as number[])[0] ?? 0,
          cols: (v.shape as number[])[1] ?? 0,
          columns: (v.columns as string[]) ?? [],
        })
      }
    }
  }
  return shapes
}

function extractTimings(result: Record<string, unknown>): TimingEntry[] {
  const timings = result._timings_ as Record<string, number> | undefined
  if (!timings || typeof timings !== "object") return []
  return Object.entries(timings)
    .map(([nodeId, seconds]) => ({ nodeId, seconds: Number(seconds) || 0 }))
    .sort((a, b) => b.seconds - a.seconds)
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  helpText,
  colorScheme = "green",
}: {
  label: string
  value: string
  helpText?: string
  colorScheme?: string
}) {
  return (
    <Box
      bg="white"
      border="1px solid"
      borderColor="gray.200"
      borderRadius="lg"
      p={4}
      shadow="sm"
      _hover={{ shadow: "md", borderColor: `${colorScheme}.200` }}
      transition="all 0.15s"
    >
      <Stat>
        <StatLabel fontSize="xs" color="gray.500" textTransform="uppercase" fontWeight="semibold">
          {label}
        </StatLabel>
        <StatNumber fontSize="2xl" color={`${colorScheme}.600`}>
          {value}
        </StatNumber>
        {helpText && (
          <StatHelpText fontSize="xs" color="gray.500" mb={0}>
            {helpText}
          </StatHelpText>
        )}
      </Stat>
    </Box>
  )
}

function FeatureImportanceChart({
  importances,
}: {
  importances: Record<string, number>
}) {
  const sorted = Object.entries(importances).sort((a, b) => b[1] - a[1])
  const max = sorted[0]?.[1] ?? 1

  return (
    <Box>
      <Text fontSize="sm" fontWeight="semibold" color="gray.700" mb={3}>
        Feature Importance
      </Text>
      {sorted.map(([name, val]) => (
        <Flex key={name} align="center" mb={1.5} gap={2}>
          <Text fontSize="xs" color="gray.600" w="140px" noOfLines={1} flexShrink={0} title={name}>
            {name}
          </Text>
          <Box flex={1} position="relative">
            <Progress
              value={(val / max) * 100}
              size="sm"
              colorScheme="green"
              borderRadius="full"
              bg="gray.100"
            />
          </Box>
          <Text fontSize="xs" color="gray.500" w="50px" textAlign="right" flexShrink={0}>
            {(val * 100).toFixed(1)}%
          </Text>
        </Flex>
      ))}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function RunSummaryPanel({ result, nodeStatuses }: RunSummaryPanelProps) {
  const allMetrics = useMemo(() => extractMetrics(result), [result])
  const dfShapes = useMemo(() => extractDataframeShapes(result), [result])
  const timings = useMemo(() => extractTimings(result), [result])
  const totalTime = timings.reduce((sum, t) => sum + t.seconds, 0)

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const s of Object.values(nodeStatuses)) {
      const key = s.startsWith("error") ? "error" : s
      counts[key] = (counts[key] ?? 0) + 1
    }
    return counts
  }, [nodeStatuses])

  const nodeCount = Object.keys(nodeStatuses).length

  return (
    <Box>
      {/* ── Pipeline Status Strip ─────────────────────────────────────── */}
      <Box
        bg="white"
        border="1px solid"
        borderColor="gray.200"
        borderRadius="lg"
        p={4}
        mb={5}
        shadow="sm"
      >
        <Text fontSize="sm" fontWeight="semibold" color="gray.700" mb={3}>
          Pipeline Status
        </Text>
        <Flex gap={2} flexWrap="wrap" mb={3}>
          {Object.entries(nodeStatuses).map(([nodeId, status]) => {
            const baseStatus = status.startsWith("error") ? "error" : status
            return (
              <Tooltip
                key={nodeId}
                label={`${nodeId}: ${status}`}
                placement="top"
                hasArrow
              >
                <Badge
                  colorScheme={STATUS_BADGE_COLOR[baseStatus] ?? "gray"}
                  fontSize="xs"
                  px={2}
                  py={0.5}
                  borderRadius="md"
                  cursor="default"
                >
                  {STATUS_ICON[baseStatus] ?? "·"} {nodeId}
                </Badge>
              </Tooltip>
            )
          })}
        </Flex>
        <Flex gap={4} flexWrap="wrap">
          {Object.entries(statusCounts).map(([status, count]) => (
            <Text key={status} fontSize="xs" color="gray.500">
              <Text as="span" fontWeight="semibold" color={`${STATUS_BADGE_COLOR[status] ?? "gray"}.600`}>
                {count}
              </Text>{" "}
              {status}
            </Text>
          ))}
          <Text fontSize="xs" color="gray.500">
            <Text as="span" fontWeight="semibold">{nodeCount}</Text> total nodes
          </Text>
        </Flex>
      </Box>

      {/* ── KPI Stat Cards ────────────────────────────────────────────── */}
      {allMetrics.length > 0 && (
        <Box mb={5}>
          <Text fontSize="sm" fontWeight="semibold" color="gray.700" mb={3}>
            Model Metrics
          </Text>
          {allMetrics.map((m, idx) => {
            const metrics = m.metrics
            return (
              <Box key={`${m.nodeId}-${idx}`} mb={4}>
                <Text fontSize="xs" color="gray.500" mb={2} fontFamily="mono">
                  from: {m.nodeId}
                </Text>
                <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3} mb={3}>
                  {metrics.r2 !== undefined && (
                    <StatCard
                      label="R² Score"
                      value={String(metrics.r2)}
                      helpText="1.0 = perfect fit"
                      colorScheme="green"
                    />
                  )}
                  {metrics.rmse !== undefined && (
                    <StatCard
                      label="RMSE"
                      value={String(metrics.rmse)}
                      helpText="Lower is better"
                      colorScheme="orange"
                    />
                  )}
                  {metrics.mae !== undefined && (
                    <StatCard
                      label="MAE"
                      value={String(metrics.mae)}
                      helpText="Mean absolute error"
                      colorScheme="blue"
                    />
                  )}
                  {metrics.accuracy !== undefined && (
                    <StatCard
                      label="Accuracy"
                      value={`${(Number(metrics.accuracy) * 100).toFixed(1)}%`}
                      colorScheme="green"
                    />
                  )}
                  {metrics.f1_macro !== undefined && (
                    <StatCard
                      label="F1 (macro)"
                      value={String(metrics.f1_macro)}
                      colorScheme="purple"
                    />
                  )}
                  {metrics.n_samples !== undefined && (
                    <StatCard
                      label="Samples"
                      value={String(metrics.n_samples)}
                      helpText={
                        metrics.n_train
                          ? `Train: ${metrics.n_train} · Test: ${metrics.n_test}`
                          : undefined
                      }
                      colorScheme="gray"
                    />
                  )}
                  {metrics.mean !== undefined && (
                    <StatCard
                      label={`CV ${metrics.scoring ?? "score"}`}
                      value={`${metrics.mean} ± ${metrics.std}`}
                      helpText={`${metrics.cv_folds}-fold cross-validation`}
                      colorScheme="teal"
                    />
                  )}
                  {metrics.best_model_label !== undefined && (
                    <StatCard
                      label="Best Model"
                      value={String(metrics.best_model_label)}
                      helpText="Selected by AutoML"
                      colorScheme="purple"
                    />
                  )}
                </SimpleGrid>

                {/* Feature importance if available */}
                {typeof metrics.feature_importances === "object" &&
                  metrics.feature_importances !== null && (
                    <Box
                      bg="white"
                      border="1px solid"
                      borderColor="gray.200"
                      borderRadius="lg"
                      p={4}
                      shadow="sm"
                    >
                      <FeatureImportanceChart
                        importances={metrics.feature_importances as Record<string, number>}
                      />
                    </Box>
                  )}
              </Box>
            )
          })}
        </Box>
      )}

      {/* ── Execution Timings ─────────────────────────────────────────── */}
      {timings.length > 0 && (
        <Box
          bg="white"
          border="1px solid"
          borderColor="gray.200"
          borderRadius="lg"
          p={4}
          mb={5}
          shadow="sm"
        >
          <Flex justify="space-between" align="center" mb={3}>
            <Text fontSize="sm" fontWeight="semibold" color="gray.700">
              Execution Time
            </Text>
            <Badge colorScheme="blue" fontSize="xs" px={2} py={0.5}>
              Total: {totalTime.toFixed(2)}s
            </Badge>
          </Flex>
          <Table size="sm" variant="simple">
            <Thead>
              <Tr>
                <Th fontSize="xs" p={1}>Node</Th>
                <Th fontSize="xs" p={1} isNumeric>Time (s)</Th>
                <Th fontSize="xs" p={1} w="50%"></Th>
              </Tr>
            </Thead>
            <Tbody>
              {timings.map((t) => (
                <Tr key={t.nodeId}>
                  <Td fontSize="xs" p={1} fontFamily="mono">
                    {t.nodeId}
                  </Td>
                  <Td fontSize="xs" p={1} isNumeric>
                    {t.seconds.toFixed(3)}
                  </Td>
                  <Td p={1}>
                    <Progress
                      value={totalTime > 0 ? (t.seconds / totalTime) * 100 : 0}
                      size="xs"
                      colorScheme="blue"
                      borderRadius="full"
                      bg="gray.100"
                    />
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}

      {/* ── Data Shape Tracker ────────────────────────────────────────── */}
      {dfShapes.length > 0 && (
        <Box
          bg="white"
          border="1px solid"
          borderColor="gray.200"
          borderRadius="lg"
          p={4}
          mb={5}
          shadow="sm"
        >
          <Text fontSize="sm" fontWeight="semibold" color="gray.700" mb={3}>
            Data Shape Tracker
          </Text>
          <Flex gap={0} flexWrap="wrap" align="center">
            {dfShapes.map((df, i) => (
              <Flex key={`${df.nodeId}-${df.slot}`} align="center" gap={0}>
                <Tooltip
                  label={
                    `Columns: ${df.columns.slice(0, 10).join(", ")}` +
                    (df.columns.length > 10 ? ` … +${df.columns.length - 10} more` : "")
                  }
                  placement="top"
                  hasArrow
                >
                  <Box
                    bg="gray.50"
                    border="1px solid"
                    borderColor="gray.200"
                    borderRadius="md"
                    px={3}
                    py={2}
                    textAlign="center"
                    cursor="default"
                    _hover={{ borderColor: "green.300", bg: "green.50" }}
                    transition="all 0.15s"
                  >
                    <Text fontSize="xs" fontWeight="semibold" color="gray.700" noOfLines={1}>
                      {df.nodeId}
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      {df.rows.toLocaleString()} × {df.cols}
                    </Text>
                  </Box>
                </Tooltip>
                {i < dfShapes.length - 1 && (
                  <Text color="gray.400" fontSize="lg" mx={1}>→</Text>
                )}
              </Flex>
            ))}
          </Flex>
        </Box>
      )}

      {/* ── Empty state ───────────────────────────────────────────────── */}
      {allMetrics.length === 0 && timings.length === 0 && dfShapes.length === 0 && (
        <Box
          border="2px dashed"
          borderColor="gray.200"
          borderRadius="lg"
          p={8}
          textAlign="center"
          color="gray.400"
        >
          <Text fontWeight="medium">No summary data available for this run.</Text>
          <Text fontSize="sm" mt={1}>
            Add a Trainer or Metrics node to see model performance summary.
          </Text>
        </Box>
      )}
    </Box>
  )
}
