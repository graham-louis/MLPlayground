import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Select,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatHelpText,
  StatLabel,
  StatNumber,
  Tab,
  Table,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  useDisclosure,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import axios from "axios"
import { useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartTooltip,
  XAxis,
  YAxis,
} from "recharts"

export const Route = createFileRoute("/explore")({
  component: ExplorePage,
})

// ── Types ──────────────────────────────────────────────────────────────────

interface DatasourceInfo {
  key: string
  label: string
  endpoint: string
  columns: string[]
  scope_params: { name: string; type: string; label: string; default?: unknown }[]
  description: string
}

// ── Constants ──────────────────────────────────────────────────────────────

const US_STATES = [
  "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
  "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
  "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
  "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
  "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
  "New Hampshire", "New Jersey", "New Mexico", "New York",
  "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
  "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
  "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
  "West Virginia", "Wisconsin", "Wyoming",
]

// ── Stats helpers ──────────────────────────────────────────────────────────

function computeStats(rows: Record<string, unknown>[], col: string) {
  const vals = rows.map((r) => Number(r[col])).filter((v) => !isNaN(v))
  if (vals.length === 0) return null
  return {
    mean: vals.reduce((a, b) => a + b, 0) / vals.length,
    min: Math.min(...vals),
    max: Math.max(...vals),
  }
}

function SummaryStats({ rows, numericCols }: { rows: Record<string, unknown>[]; numericCols: string[] }) {
  if (rows.length === 0 || numericCols.length === 0) return null
  return (
    <SimpleGrid columns={{ base: 2, md: Math.min(numericCols.length, 4) }} spacing={3} mb={4}>
      {numericCols.slice(0, 4).map((col) => {
        const s = computeStats(rows, col)
        if (!s) return null
        return (
          <Stat key={col} bg="green.50" borderRadius="md" p={3}>
            <StatLabel fontSize="xs" color="gray.600">{col}</StatLabel>
            <StatNumber fontSize="md">{s.mean.toFixed(1)}</StatNumber>
            <StatHelpText fontSize="xs">min {s.min.toFixed(1)} · max {s.max.toFixed(1)}</StatHelpText>
          </Stat>
        )
      })}
    </SimpleGrid>
  )
}

// ── Column histogram modal ─────────────────────────────────────────────────

function ColumnHistogram({
  isOpen,
  onClose,
  col,
  rows,
}: {
  isOpen: boolean
  onClose: () => void
  col: string
  rows: Record<string, unknown>[]
}) {
  const vals = rows.map((r) => Number(r[col])).filter((v) => !isNaN(v))
  if (vals.length === 0) return null

  const hasYear = col === "year"
  let chartData: { label: string | number; value: number }[]

  if (hasYear) {
    const byYear: Record<number, number[]> = {}
    for (const r of rows) {
      const yr = Number(r["year"])
      const v = Number(r[col])
      if (!isNaN(yr) && !isNaN(v) && col !== "year") {
        byYear[yr] = [...(byYear[yr] ?? []), v]
      }
    }
    // For "year" column itself, just count occurrences
    const freq: Record<number, number> = {}
    for (const v of vals) freq[v] = (freq[v] ?? 0) + 1
    chartData = Object.entries(freq)
      .map(([k, v]) => ({ label: Number(k), value: v }))
      .sort((a, b) => Number(a.label) - Number(b.label))
  } else {
    // Histogram: 20 bins
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    const bins = 20
    const binSize = (max - min) / bins || 1
    const counts = Array(bins).fill(0)
    for (const v of vals) {
      const idx = Math.min(Math.floor((v - min) / binSize), bins - 1)
      counts[idx]++
    }
    chartData = counts.map((count, i) => ({
      label: (min + i * binSize).toFixed(1),
      value: count,
    }))
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          Distribution: <code>{col}</code>
          <Text as="span" fontSize="sm" color="gray.500" fontWeight="normal" ml={2}>
            ({vals.length} values)
          </Text>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <RechartTooltip />
              <Bar dataKey="value" fill="#276749" />
            </BarChart>
          </ResponsiveContainer>
        </ModalBody>
      </ModalContent>
    </Modal>
  )
}

// ── Time series chart ──────────────────────────────────────────────────────

function TimeSeriesChart({
  rows,
  tab,
}: {
  rows: Record<string, unknown>[]
  tab: DatasourceInfo
}) {
  const yearCol = "year"
  if (!rows[0]?.[yearCol]) return null

  const valueCol = tab.key === "yields" ? "value"
    : tab.key === "weather" ? "avg_temp"
    : tab.key === "daily_weather" ? "tmax"
    : null
  if (!valueCol || !rows[0]?.[valueCol]) return null

  const byYear: Record<number, number[]> = {}
  for (const r of rows) {
    const yr = Number(r[yearCol])
    const v = Number(r[valueCol])
    if (!isNaN(yr) && !isNaN(v)) {
      byYear[yr] = [...(byYear[yr] ?? []), v]
    }
  }
  const chartData = Object.entries(byYear)
    .map(([yr, vs]) => ({ year: Number(yr), value: vs.reduce((a, b) => a + b, 0) / vs.length }))
    .sort((a, b) => a.year - b.year)

  if (chartData.length < 2) return null

  const label = tab.key === "yields" ? "Avg Yield (bu/acre)"
    : tab.key === "weather" ? "Avg Temp (°C)"
    : "Avg Tmax (°C)"

  return (
    <Box mb={4}>
      <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>{label} over time</Text>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData} margin={{ top: 4, right: 20, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={55} />
          <RechartTooltip formatter={(v: number) => v.toFixed(1)} />
          <Line type="monotone" dataKey="value" stroke="#276749" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────

function ExplorePage() {
  const [state, setState] = useState("North Carolina")
  const [county, setCounty] = useState("")
  const [crop, setCrop] = useState("")
  const [startYear, setStartYear] = useState("2000")
  const [endYear, setEndYear] = useState("2022")
  const [activeTabIdx, setActiveTabIdx] = useState(0)
  const [queryParams, setQueryParams] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [selectedCol, setSelectedCol] = useState<string | null>(null)
  const { isOpen: isHistOpen, onOpen: onHistOpen, onClose: onHistClose } = useDisclosure()

  // ── Fetch datasource registry ────────────────────────────────────────────
  const { data: datasourcesResp, isLoading: dsLoading } = useQuery({
    queryKey: ["datasources"],
    queryFn: () =>
      axios.get("/api/v1/datasources/").then((r) => r.data as { data: DatasourceInfo[]; count: number }),
  })

  const dataTabs: DatasourceInfo[] = datasourcesResp?.data ?? []
  const activeTab = dataTabs[activeTabIdx] ?? dataTabs[0]

  const { data: cropsData } = useQuery({
    queryKey: ["crops", state],
    queryFn: () =>
      axios.get("/api/v1/yields/crops", { params: { state } }).then((r) => r.data as string[]),
    enabled: !!state,
  })

  const { data: currentData, isLoading } = useQuery({
    queryKey: ["explore", activeTab?.key, queryParams],
    queryFn: () =>
      axios.get(activeTab.endpoint, { params: queryParams }).then((r) => r.data),
    enabled: submitted && !!activeTab,
  })

  const { data: ingestStatus, refetch: refetchStatus } = useQuery({
    queryKey: ["ingest-status"],
    queryFn: () =>
      axios.get("/api/v1/ingest/status").then((r) => r.data as { status: "idle" | "running" }),
    refetchInterval: (query) => (query.state.data?.status === "running" ? 3000 : false),
  })

  const ingestMutation = useMutation({
    mutationFn: () =>
      axios.post("/api/v1/ingest/trigger").then((r) => r.data as { message: string }),
    onSuccess: () => refetchStatus(),
  })

  const dailyIngestMutation = useMutation({
    mutationFn: () =>
      axios
        .post("/api/v1/ingest/trigger-daily-weather", {
          state,
          start_year: startYear ? parseInt(startYear) : 2000,
          end_year: endYear ? parseInt(endYear) : 2022,
        })
        .then((r) => r.data as { message: string }),
    onSuccess: () => refetchStatus(),
  })

  const handleFetch = () => {
    const params: Record<string, string> = { state }
    if (county) params.county = county
    if (crop && activeTab?.key === "yields") params.crop = crop
    if (startYear) params.start_year = startYear
    if (endYear) params.end_year = endYear
    setQueryParams(params)
    setSubmitted(true)
  }

  const tableRows: Record<string, unknown>[] = currentData?.data ?? []
  const columns = tableRows.length > 0 ? Object.keys(tableRows[0]) : []
  const numericCols = columns.filter((c) => typeof tableRows[0]?.[c] === "number")

  const handleColClick = (col: string) => {
    if (numericCols.includes(col)) {
      setSelectedCol(col)
      onHistOpen()
    }
  }

  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Data Explorer</Heading>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader><Heading size="md">Filters</Heading></CardHeader>
        <CardBody>
          <Flex gap={4} wrap="wrap" align="flex-end">
            <FormControl maxW="200px">
              <FormLabel>State</FormLabel>
              <Select value={state} onChange={(e) => { setState(e.target.value); setCrop("") }}>
                {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </FormControl>
            <FormControl maxW="160px">
              <FormLabel>County</FormLabel>
              <Input
                placeholder="All counties"
                value={county}
                onChange={(e) => setCounty(e.target.value)}
              />
            </FormControl>
            {activeTab?.key === "yields" && (
              <FormControl maxW="160px">
                <FormLabel>Crop</FormLabel>
                <Select value={crop} onChange={(e) => setCrop(e.target.value)} placeholder="All crops">
                  {(cropsData ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
                </Select>
              </FormControl>
            )}
            <FormControl maxW="110px">
              <FormLabel>Start Year</FormLabel>
              <Input type="number" value={startYear} onChange={(e) => setStartYear(e.target.value)} aria-label="Start Year" />
            </FormControl>
            <FormControl maxW="110px">
              <FormLabel>End Year</FormLabel>
              <Input type="number" value={endYear} onChange={(e) => setEndYear(e.target.value)} aria-label="End Year" />
            </FormControl>
            <Button colorScheme="green" onClick={handleFetch}>Load Data</Button>
          </Flex>
        </CardBody>
      </Card>

      {/* ── Data type tabs (data-driven from /api/v1/datasources/) ───────── */}
      {dsLoading ? (
        <Flex justify="center" py={6}><Spinner color="green.500" /></Flex>
      ) : (
        <Tabs
          index={activeTabIdx}
          onChange={(i) => { setActiveTabIdx(i); setSubmitted(false) }}
          colorScheme="green"
          variant="enclosed"
          isLazy
        >
          <TabList>
            {dataTabs.map((t) => (
              <Tooltip key={t.key} label={t.description} placement="top" hasArrow>
                <Tab>{t.label}</Tab>
              </Tooltip>
            ))}
          </TabList>

          <TabPanels>
            {dataTabs.map((t) => (
              <TabPanel key={t.key} p={0} pt={4}>
                {isLoading && (
                  <Flex justify="center" py={8}><Spinner size="xl" color="green.500" /></Flex>
                )}

                {!isLoading && submitted && (
                  <Card>
                    <CardHeader>
                      <Flex align="center" gap={3} wrap="wrap">
                        <Heading size="md">{t.label} Results</Heading>
                        <Badge colorScheme="green">{currentData?.count ?? 0} records</Badge>
                        {county && <Badge colorScheme="blue">{county}</Badge>}
                        {state && <Badge colorScheme="purple">{state}</Badge>}
                      </Flex>
                    </CardHeader>
                    <CardBody>
                      {tableRows.length === 0 ? (
                        <EmptyState
                          tab={t.key}
                          ingestStatus={ingestStatus}
                          ingestMutation={ingestMutation}
                          dailyIngestMutation={dailyIngestMutation}
                        />
                      ) : (
                        <>
                          <SummaryStats rows={tableRows} numericCols={numericCols} />
                          <TimeSeriesChart rows={tableRows} tab={t} />
                          <Divider my={3} />
                          <Text fontSize="xs" color="gray.500" mb={1}>
                            Showing {Math.min(tableRows.length, 200)} of {currentData?.count ?? tableRows.length} total
                          </Text>
                          <Text fontSize="xs" color="gray.400" mb={2}>
                            💡 Click a numeric column header to see its distribution.
                          </Text>
                          <Box overflowX="auto">
                            <Table size="sm" variant="striped">
                              <Thead>
                                <Tr>
                                  {columns.map((col) => (
                                    <Th
                                      key={col}
                                      cursor={numericCols.includes(col) ? "pointer" : "default"}
                                      _hover={numericCols.includes(col) ? { color: "green.600", textDecoration: "underline" } : {}}
                                      onClick={() => handleColClick(col)}
                                      title={numericCols.includes(col) ? `Click to view ${col} distribution` : undefined}
                                    >
                                      {col}
                                    </Th>
                                  ))}
                                </Tr>
                              </Thead>
                              <Tbody>
                                {tableRows.slice(0, 200).map((row, i) => (
                                  <Tr key={i}>
                                    {columns.map((col) => (
                                      <Td key={col}>{row[col] != null ? String(row[col]) : ""}</Td>
                                    ))}
                                  </Tr>
                                ))}
                              </Tbody>
                            </Table>
                          </Box>
                        </>
                      )}
                    </CardBody>
                  </Card>
                )}

                {!submitted && (
                  <Text color="gray.500" fontSize="sm" mt={2}>
                    Set filters above and click <strong>Load Data</strong> to explore {t.label.toLowerCase()} data.
                  </Text>
                )}
              </TabPanel>
            ))}
          </TabPanels>
        </Tabs>
      )}

      {/* ── Column histogram modal ───────────────────────────────────────── */}
      {selectedCol && (
        <ColumnHistogram
          isOpen={isHistOpen}
          onClose={onHistClose}
          col={selectedCol}
          rows={tableRows}
        />
      )}

      {/* ── Ingest controls ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <Heading size="md">Data Ingestion</Heading>
          <Text fontSize="sm" color="gray.500" mt={1}>
            Fetch fresh data from USDA NASS, Daymet, and SSURGO APIs and store it in the database.
            For more control, use the <strong>Ingest</strong> page.
          </Text>
        </CardHeader>
        <CardBody>
          <Stack spacing={3}>
            <Flex gap={4} wrap="wrap" align="center">
              <Stack flex={1} minW="200px">
                <Text fontWeight="medium" fontSize="sm">Full Pipeline</Text>
                <Text fontSize="xs" color="gray.500">Yields · Annual weather · Soil (all counties for selected state)</Text>
              </Stack>
              {ingestStatus?.status === "running" ? (
                <Alert status="loading" borderRadius="md" maxW="320px">
                  <AlertIcon />
                  <AlertDescription fontSize="sm">Ingestion running…</AlertDescription>
                </Alert>
              ) : (
                <Button
                  colorScheme="green"
                  variant="outline"
                  isLoading={ingestMutation.isPending}
                  loadingText="Starting…"
                  onClick={() => ingestMutation.mutate()}
                >
                  Run Full Ingest
                </Button>
              )}
            </Flex>

            <Divider />

            <Flex gap={4} wrap="wrap" align="center">
              <Stack flex={1} minW="200px">
                <Text fontWeight="medium" fontSize="sm">Daily Weather Only</Text>
                <Text fontSize="xs" color="gray.500">
                  Required for ApsimX simulations — loads Daymet daily records into the daily_weather table.
                </Text>
              </Stack>
              <Button
                colorScheme="blue"
                variant="outline"
                isLoading={dailyIngestMutation.isPending}
                loadingText="Starting…"
                onClick={() => dailyIngestMutation.mutate()}
              >
                Ingest Daily Weather
              </Button>
            </Flex>

            {(ingestMutation.isError || dailyIngestMutation.isError) && (
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                <AlertDescription fontSize="sm">
                  {(ingestMutation.error as { response?: { data?: { detail?: string } } } | null)
                    ?.response?.data?.detail ??
                    (dailyIngestMutation.error as { response?: { data?: { detail?: string } } } | null)
                      ?.response?.data?.detail ??
                    "Ingest failed to start. Check backend logs."}
                </AlertDescription>
              </Alert>
            )}
          </Stack>
        </CardBody>
      </Card>
    </Stack>
  )
}

// ── Empty state ────────────────────────────────────────────────────────────

function EmptyState({
  tab,
  ingestStatus,
  ingestMutation,
  dailyIngestMutation,
}: {
  tab: string
  ingestStatus: { status: "idle" | "running" } | undefined
  ingestMutation: { isPending: boolean; isError: boolean; error: unknown; mutate: () => void }
  dailyIngestMutation: { isPending: boolean; mutate: () => void }
}) {
  return (
    <Stack spacing={4}>
      <Alert status="info" borderRadius="md">
        <AlertIcon />
        <Box>
          <AlertTitle>No {tab.replace(/_/g, " ")} data found</AlertTitle>
          <AlertDescription fontSize="sm">
            {tab === "daily_weather"
              ? "No daily weather in the database. Click 'Ingest Daily Weather' below to load Daymet records."
              : "The database is empty for this selection. Run the ingestion pipeline to fetch data."}
          </AlertDescription>
        </Box>
      </Alert>
      {ingestStatus?.status === "running" ? (
        <Alert status="loading" borderRadius="md">
          <AlertIcon />
          <AlertDescription>Ingestion is running… reload data once it finishes.</AlertDescription>
        </Alert>
      ) : tab === "daily_weather" ? (
        <Button
          colorScheme="blue"
          isLoading={dailyIngestMutation.isPending}
          onClick={() => dailyIngestMutation.mutate()}
          width="fit-content"
        >
          Ingest Daily Weather
        </Button>
      ) : (
        <Button
          colorScheme="green"
          isLoading={ingestMutation.isPending}
          loadingText="Starting…"
          onClick={() => ingestMutation.mutate()}
          width="fit-content"
        >
          Run Data Ingestion
        </Button>
      )}
    </Stack>
  )
}
