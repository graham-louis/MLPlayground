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
  Tr,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import axios from "axios"
import { useState } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export const Route = createFileRoute("/explore")({
  component: ExplorePage,
})

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

type DataTab = "yields" | "weather" | "soil" | "daily_weather"

const DATA_TABS: { key: DataTab; label: string; endpoint: string }[] = [
  { key: "yields",        label: "Yields",        endpoint: "/api/v1/yields/" },
  { key: "weather",       label: "Weather",       endpoint: "/api/v1/weather/" },
  { key: "soil",          label: "Soil",          endpoint: "/api/v1/soil/" },
  { key: "daily_weather", label: "Daily Weather", endpoint: "/api/v1/daily-weather/" },
]

function computeStats(rows: Record<string, unknown>[], col: string): { mean: number; min: number; max: number } | null {
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

function TimeSeriesChart({ rows, tab }: { rows: Record<string, unknown>[]; tab: DataTab }) {
  const yearCol = "year"
  if (!rows[0]?.[yearCol]) return null

  const valueCol = tab === "yields" ? "value"
    : tab === "weather" ? "avg_temp"
    : tab === "daily_weather" ? "tmax"
    : null
  if (!valueCol) return null

  // Group by year, average the value column
  const byYear: Record<number, number[]> = {}
  for (const r of rows) {
    const yr = Number(r[yearCol])
    const v = Number(r[valueCol])
    if (!isNaN(yr) && !isNaN(v)) {
      byYear[yr] = [...(byYear[yr] ?? []), v]
    }
  }
  const chartData = Object.entries(byYear)
    .map(([yr, vals]) => ({
      year: Number(yr),
      value: vals.reduce((a, b) => a + b, 0) / vals.length,
    }))
    .sort((a, b) => a.year - b.year)

  if (chartData.length < 2) return null

  const label = tab === "yields" ? "Avg Yield (bu/acre)"
    : tab === "weather" ? "Avg Temp (°C)"
    : "Avg Tmax (°C)"

  return (
    <Box mb={4}>
      <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>{label} over time</Text>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData} margin={{ top: 4, right: 20, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={55} />
          <Tooltip formatter={(v: number) => v.toFixed(1)} />
          <Line type="monotone" dataKey="value" stroke="#276749" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  )
}

function ExplorePage() {
  const [state, setState] = useState("North Carolina")
  const [county, setCounty] = useState("")
  const [crop, setCrop] = useState("")
  const [startYear, setStartYear] = useState("2000")
  const [endYear, setEndYear] = useState("2022")
  const [activeTabIdx, setActiveTabIdx] = useState(0)
  const [queryParams, setQueryParams] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)

  const activeTab = DATA_TABS[activeTabIdx]

  const { data: cropsData } = useQuery({
    queryKey: ["crops", state],
    queryFn: () =>
      axios.get("/api/v1/yields/crops", { params: { state } }).then((r) => r.data as string[]),
    enabled: !!state,
  })

  const { data: currentData, isLoading } = useQuery({
    queryKey: ["explore", activeTab.key, queryParams],
    queryFn: () =>
      axios.get(activeTab.endpoint, { params: queryParams }).then((r) => r.data),
    enabled: submitted,
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
    if (crop && activeTab.key === "yields") params.crop = crop
    if (startYear) params.start_year = startYear
    if (endYear) params.end_year = endYear
    setQueryParams(params)
    setSubmitted(true)
  }

  const tableRows: Record<string, unknown>[] = currentData?.data ?? []
  const columns = tableRows.length > 0 ? Object.keys(tableRows[0]) : []
  const numericCols = columns.filter((c) => typeof tableRows[0]?.[c] === "number")

  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Data Explorer</Heading>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <Heading size="md">Filters</Heading>
        </CardHeader>
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
            {activeTab.key === "yields" && (
              <FormControl maxW="160px">
                <FormLabel>Crop</FormLabel>
                <Select value={crop} onChange={(e) => setCrop(e.target.value)} placeholder="All crops">
                  {(cropsData ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
                </Select>
              </FormControl>
            )}
            <FormControl maxW="110px">
              <FormLabel>Start Year</FormLabel>
              <Input
                type="number"
                value={startYear}
                onChange={(e) => setStartYear(e.target.value)}
                aria-label="Start Year"
              />
            </FormControl>
            <FormControl maxW="110px">
              <FormLabel>End Year</FormLabel>
              <Input
                type="number"
                value={endYear}
                onChange={(e) => setEndYear(e.target.value)}
                aria-label="End Year"
              />
            </FormControl>
            <Button colorScheme="green" onClick={handleFetch}>
              Load Data
            </Button>
          </Flex>
        </CardBody>
      </Card>

      {/* ── Data type tabs ───────────────────────────────────────────────── */}
      <Tabs
        index={activeTabIdx}
        onChange={(i) => { setActiveTabIdx(i); setSubmitted(false) }}
        colorScheme="green"
        variant="enclosed"
        isLazy
      >
        <TabList>
          {DATA_TABS.map((t) => <Tab key={t.key}>{t.label}</Tab>)}
        </TabList>

        <TabPanels>
          {DATA_TABS.map((t) => (
            <TabPanel key={t.key} p={0} pt={4}>
              {isLoading && (
                <Flex justify="center" py={8}>
                  <Spinner size="xl" color="green.500" />
                </Flex>
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
                        {(t.key === "yields" || t.key === "weather" || t.key === "daily_weather") && (
                          <TimeSeriesChart rows={tableRows} tab={t.key} />
                        )}
                        <Divider my={3} />
                        <Text fontSize="xs" color="gray.500" mb={2}>
                          Showing {Math.min(tableRows.length, 200)} of {currentData?.count ?? tableRows.length} total
                        </Text>
                        <Box overflowX="auto">
                          <Table size="sm" variant="striped">
                            <Thead>
                              <Tr>
                                {columns.map((col) => <Th key={col}>{col}</Th>)}
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

      {/* ── Ingest controls ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <Heading size="md">Data Ingestion</Heading>
          <Text fontSize="sm" color="gray.500" mt={1}>
            Fetch fresh data from USDA NASS, Daymet, and SSURGO APIs and store it in the database.
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
                  {county && <> Specify a county above to scope the ingest.</>}
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

function EmptyState({
  tab,
  ingestStatus,
  ingestMutation,
  dailyIngestMutation,
}: {
  tab: DataTab
  ingestStatus: { status: "idle" | "running" } | undefined
  ingestMutation: { isPending: boolean; isError: boolean; error: unknown; mutate: () => void }
  dailyIngestMutation: { isPending: boolean; mutate: () => void }
}) {
  return (
    <Stack spacing={4}>
      <Alert status="info" borderRadius="md">
        <AlertIcon />
        <Box>
          <AlertTitle>No {tab.replace("_", " ")} data found</AlertTitle>
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
