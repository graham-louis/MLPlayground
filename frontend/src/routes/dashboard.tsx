/**
 * Dashboard route (6.1) — /dashboard
 *
 * Shows the results of a selected graph run as a grid of panels (charts,
 * tables, model artefacts).  Powered by DashboardGrid, PanelChrome, and
 * PANEL_REGISTRY — adding a new panel type requires zero changes here.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────┐
 *   │  Header: title + "Open in Graph" shortcut                 │
 *   ├──────────────┬───────────────────────────────────────────┤
 *   │ Run list     │  DashboardGrid for the selected run        │
 *   │ (scrollable) │                                           │
 *   └──────────────┴───────────────────────────────────────────┘
 */
import {
  Badge,
  Box,
  Flex,
  Grid,
  Heading,
  Link,
  Select,
  Spinner,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Text,
  Tooltip,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import axios from "axios"
import { useState } from "react"
import { DashboardGrid } from "../components/dashboard/DashboardGrid"
import { RunSummaryPanel } from "../components/dashboard/RunSummaryPanel"

export const Route = createFileRoute("/dashboard")({
  component: DashboardPage,
})

// ---------------------------------------------------------------------------
// Types (matching backend RunSummary / ResultResponse models)
// ---------------------------------------------------------------------------

interface RunSummary {
  run_id: string
  status: "pending" | "running" | "success" | "error"
  created_at: string
  updated_at: string
  error?: string | null
}

interface ResultResponse {
  run_id: string
  status: string
  result: Record<string, unknown>
  node_statuses: Record<string, string>
}

// ---------------------------------------------------------------------------
// Status colour helper
// ---------------------------------------------------------------------------

const STATUS_COLOR: Record<string, string> = {
  success: "green",
  error: "red",
  running: "blue",
  pending: "yellow",
}

// ---------------------------------------------------------------------------
// RunList sidebar
// ---------------------------------------------------------------------------

function RunList({
  runs,
  selectedId,
  onSelect,
}: {
  runs: RunSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  if (runs.length === 0) {
    return (
      <Box p={4} textAlign="center" color="gray.400">
        <Text fontSize="sm">No runs yet.</Text>
        <Text fontSize="xs" mt={1}>
          Run a workflow in the{" "}
          <Link href="/graph" color="green.600" fontWeight="medium">
            Graph editor
          </Link>
          .
        </Text>
      </Box>
    )
  }

  return (
    <Stack spacing={0}>
      {runs.map((run) => {
        const isSelected = run.run_id === selectedId
        const date = new Date(run.created_at)
        const dateStr = date.toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
        return (
          <Box
            key={run.run_id}
            px={3}
            py={2.5}
            cursor="pointer"
            bg={isSelected ? "green.50" : "white"}
            borderLeft="3px solid"
            borderLeftColor={isSelected ? "green.500" : "transparent"}
            borderBottom="1px solid"
            borderBottomColor="gray.100"
            _hover={{ bg: isSelected ? "green.50" : "gray.50" }}
            transition="background 0.1s"
            onClick={() => onSelect(run.run_id)}
          >
            <Flex align="center" justify="space-between" mb={0.5}>
              <Badge
                colorScheme={STATUS_COLOR[run.status] ?? "gray"}
                fontSize="2xs"
                px={1.5}
              >
                {run.status}
              </Badge>
              <Text fontSize="2xs" color="gray.400">{dateStr}</Text>
            </Flex>
            <Text
              fontSize="xs"
              color="gray.600"
              fontFamily="mono"
              noOfLines={1}
              title={run.run_id}
            >
              {run.run_id.slice(0, 8)}…
            </Text>
            {run.error && (
              <Tooltip label={run.error} placement="right" hasArrow>
                <Text fontSize="2xs" color="red.400" noOfLines={1} cursor="help">
                  {run.error}
                </Text>
              </Tooltip>
            )}
          </Box>
        )
      })}
    </Stack>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

function DashboardPage() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  // ── Recent runs ────────────────────────────────────────────────────────────
  const {
    data: runs = [],
    isLoading: runsLoading,
  } = useQuery<RunSummary[]>({
    queryKey: ["dashboard-runs"],
    queryFn: () =>
      axios.get("/api/v1/graphs/runs?limit=50").then((r) => r.data),
    // Auto-select the most recent successful run on first load
    select: (data) => {
      if (!selectedRunId) {
        const first = data.find((r) => r.status === "success")
        if (first) setSelectedRunId(first.run_id)
      }
      return data
    },
    refetchInterval: 15_000,
  })

  // ── Selected run result ────────────────────────────────────────────────────
  const selectedRun = runs.find((r) => r.run_id === selectedRunId)
  const canFetch = !!selectedRunId && selectedRun?.status === "success"

  const {
    data: runResult,
    isLoading: resultLoading,
    error: resultError,
  } = useQuery<ResultResponse>({
    queryKey: ["dashboard-result", selectedRunId],
    queryFn: () =>
      axios.get(`/api/v1/graphs/${selectedRunId}/result`).then((r) => r.data),
    enabled: canFetch,
    staleTime: 60_000,
  })

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <Box h="calc(100vh - 64px)" display="flex" flexDirection="column" bg="gray.50">
      {/* ── Top header ─────────────────────────────────────────────────────── */}
      <Box
        bg="white"
        borderBottom="1px solid"
        borderColor="gray.200"
        px={6}
        py={3}
        flexShrink={0}
      >
        <Flex align="center" justify="space-between">
          <Box>
            <Heading size="md" color="gray.800">
              📊 Results Dashboard
            </Heading>
            <Text fontSize="xs" color="gray.500" mt={0.5}>
              Visual summary of the last graph run — charts, tables, and model artefacts.
            </Text>
          </Box>
          <Flex align="center" gap={4}>
            {/* Mobile-friendly run picker (in addition to sidebar) */}
            {runs.length > 0 && (
              <Select
                size="sm"
                w="280px"
                value={selectedRunId ?? ""}
                onChange={(e) => setSelectedRunId(e.target.value || null)}
                display={{ base: "block", lg: "none" }}
              >
                <option value="">— select a run —</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    [{r.status}] {r.run_id.slice(0, 8)}…{" "}
                    {new Date(r.created_at).toLocaleString()}
                  </option>
                ))}
              </Select>
            )}
            <Link href="/graph" color="green.600" fontWeight="medium" fontSize="sm">
              ← Graph editor
            </Link>
          </Flex>
        </Flex>
      </Box>

      {/* ── Body: sidebar + content ───────────────────────────────────────── */}
      <Grid
        templateColumns={{ base: "1fr", lg: "220px 1fr" }}
        flex={1}
        overflow="hidden"
      >
        {/* Left sidebar — run list */}
        <Box
          bg="white"
          borderRight="1px solid"
          borderColor="gray.200"
          overflowY="auto"
          display={{ base: "none", lg: "block" }}
        >
          <Box
            px={3}
            py={2}
            borderBottom="1px solid"
            borderColor="gray.200"
            bg="gray.50"
          >
            <Text fontSize="xs" fontWeight="semibold" color="gray.600" textTransform="uppercase">
              Recent Runs
            </Text>
          </Box>
          {runsLoading ? (
            <Flex p={4} justify="center">
              <Spinner size="sm" color="green.500" />
            </Flex>
          ) : (
            <RunList
              runs={runs}
              selectedId={selectedRunId}
              onSelect={setSelectedRunId}
            />
          )}
        </Box>

        {/* Main panel area */}
        <Box overflowY="auto" p={5}>
          {/* No run selected */}
          {!selectedRunId && !runsLoading && (
            <Flex align="center" justify="center" h="100%" minH="300px">
              <Box textAlign="center" color="gray.400">
                <Text fontSize="3xl" mb={3}>📈</Text>
                <Text fontWeight="medium" fontSize="lg">
                  Select a run from the sidebar
                </Text>
                <Text fontSize="sm" mt={1}>
                  or run a workflow in the{" "}
                  <Link href="/graph" color="green.600" fontWeight="medium">
                    Graph editor
                  </Link>
                </Text>
              </Box>
            </Flex>
          )}

          {/* Run selected but still pending/running */}
          {selectedRunId && selectedRun && selectedRun.status !== "success" && (
            <Flex align="center" justify="center" h="100%" minH="300px">
              <Box textAlign="center" color="gray.500">
                {selectedRun.status === "error" ? (
                  <>
                    <Text fontSize="3xl" mb={3}>❌</Text>
                    <Text fontWeight="medium">Run failed</Text>
                    <Text fontSize="sm" mt={1} color="red.400">
                      {selectedRun.error ?? "Unknown error"}
                    </Text>
                  </>
                ) : (
                  <>
                    <Spinner color="green.500" size="lg" mb={3} />
                    <Text fontWeight="medium">
                      Run is {selectedRun.status}…
                    </Text>
                    <Text fontSize="sm" mt={1}>
                      Results will appear here once complete.
                    </Text>
                  </>
                )}
              </Box>
            </Flex>
          )}

          {/* Loading result */}
          {resultLoading && (
            <Flex align="center" justify="center" h="100%" minH="300px">
              <Spinner color="green.500" size="lg" />
            </Flex>
          )}

          {/* Error fetching result */}
          {resultError && (
            <Box
              p={6}
              bg="red.50"
              border="1px solid"
              borderColor="red.200"
              borderRadius="lg"
            >
              <Text color="red.600" fontWeight="medium">
                Failed to load run results
              </Text>
              <Text color="red.500" fontSize="sm" mt={1}>
                {String(resultError)}
              </Text>
            </Box>
          )}

          {/* Panels */}
          {runResult && !resultLoading && (
            <>
              <Flex align="center" justify="space-between" mb={4} flexWrap="wrap" gap={2}>
                <Box>
                  <Text fontWeight="semibold" color="gray.700">
                    Run{" "}
                    <Text as="span" fontFamily="mono" fontSize="sm">
                      {runResult.run_id}
                    </Text>
                  </Text>
                  <Text fontSize="xs" color="gray.500">
                    {Object.keys(runResult.node_statuses ?? {}).length} nodes ·{" "}
                    {new Date(
                      runs.find((r) => r.run_id === runResult.run_id)
                        ?.created_at ?? "",
                    ).toLocaleString()}
                  </Text>
                </Box>
              </Flex>

              <Tabs colorScheme="green" size="sm" defaultIndex={0}>
                <TabList mb={4} bg="white" p={1} borderRadius="lg" border="1px solid" borderColor="gray.200" w="fit-content">
                  <Tab _selected={{ bg: "green.500", color: "white" }} fontWeight="semibold" fontSize="sm">
                    Visualize
                  </Tab>
                  <Tab _selected={{ bg: "green.500", color: "white" }} fontWeight="semibold" fontSize="sm">
                    Summary
                  </Tab>
                </TabList>
                <TabPanels>
                  <TabPanel p={0}>
                    <DashboardGrid result={runResult.result} />
                  </TabPanel>
                  <TabPanel p={0}>
                    <RunSummaryPanel
                      result={runResult.result}
                      nodeStatuses={runResult.node_statuses ?? {}}
                    />
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </>
          )}
        </Box>
      </Grid>
    </Box>
  )
}
