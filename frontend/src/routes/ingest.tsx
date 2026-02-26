import {
  Alert,
  AlertDescription,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  CheckboxGroup,
  Checkbox,
  Divider,
  Flex,
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  Progress,
  SimpleGrid,
  Spinner,
  Stack,
  Tag,
  Text,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import axios from "axios"
import { useEffect, useState } from "react"

export const Route = createFileRoute("/ingest")({
  component: IngestPage,
})

// ── Types ──────────────────────────────────────────────────────────────────

interface ScopeParam {
  name: string
  type: string
  label: string
  default?: unknown
  placeholder?: string
}

interface DatasourceInfo {
  key: string
  label: string
  endpoint: string
  columns: string[]
  scope_params: ScopeParam[]
  description: string
}

interface JobStatus {
  job_id: string
  status: "queued" | "running" | "done" | "error"
  progress: number
  message: string
  errors: string[]
}

// ── Page ───────────────────────────────────────────────────────────────────

function IngestPage() {
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [scopeValues, setScopeValues] = useState<Record<string, string>>({})
  const [jobId, setJobId] = useState<string | null>(null)

  // Fetch registered datasources from the registry
  const { data: dsResp, isLoading: dsLoading } = useQuery({
    queryKey: ["datasources"],
    queryFn: () =>
      axios.get("/api/v1/datasources/").then((r) => r.data as { data: DatasourceInfo[]; count: number }),
  })
  const allSources: DatasourceInfo[] = dsResp?.data ?? []

  // Derive union of scope_params from all selected sources
  const selectedDefs = allSources.filter((s) => selectedSources.includes(s.key))
  const scopeParamMap: Map<string, ScopeParam> = new Map()
  for (const ds of selectedDefs) {
    for (const p of ds.scope_params) {
      if (!scopeParamMap.has(p.name)) scopeParamMap.set(p.name, p)
    }
  }
  const scopeParams = Array.from(scopeParamMap.values())

  // Poll job status
  const { data: jobStatus } = useQuery({
    queryKey: ["ingest-job", jobId],
    queryFn: () =>
      axios.get(`/api/v1/ingest/status/${jobId}`).then((r) => r.data as JobStatus),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === "queued" || status === "running" ? 2000 : false
    },
  })

  // Trigger generic ingest
  const runMutation = useMutation({
    mutationFn: () => {
      const scope: Record<string, unknown> = {}
      for (const p of scopeParams) {
        const val = scopeValues[p.name] ?? String(p.default ?? "")
        if (p.type === "string_list") {
          scope[p.name] = val.split(",").map((s) => s.trim()).filter(Boolean)
        } else if (p.type === "integer") {
          scope[p.name] = parseInt(val)
        } else {
          scope[p.name] = val
        }
      }
      return axios
        .post("/api/v1/ingest/run", { sources: selectedSources, scope })
        .then((r) => r.data as JobStatus)
    },
    onSuccess: (data) => setJobId(data.job_id),
  })

  // Pre-fill scope defaults when selection changes
  useEffect(() => {
    setScopeValues((prev) => {
      const next = { ...prev }
      for (const p of scopeParams) {
        if (!(p.name in next) && p.default !== undefined) {
          const def = p.default
          next[p.name] = Array.isArray(def) ? def.join(", ") : String(def)
        }
      }
      return next
    })
  }, [selectedSources]) // eslint-disable-line react-hooks/exhaustive-deps

  const isRunning = jobStatus?.status === "queued" || jobStatus?.status === "running"
  const isDone = jobStatus?.status === "done"
  const hasErrors = (jobStatus?.errors?.length ?? 0) > 0

  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Data Ingestion</Heading>
      <Text color="gray.600" fontSize="sm">
        Select one or more data sources and configure the ingestion scope. The platform will fetch
        fresh data from each source's API and store it in the database.
      </Text>

      {/* ── Source selection ──────────────────────────────────────────────── */}
      <Card>
        <CardHeader><Heading size="md">1. Select Data Sources</Heading></CardHeader>
        <CardBody>
          {dsLoading ? (
            <Spinner color="green.500" />
          ) : (
            <CheckboxGroup
              value={selectedSources}
              onChange={(v) => setSelectedSources(v as string[])}
            >
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
                {allSources.map((ds) => (
                  <Box
                    key={ds.key}
                    borderWidth={1}
                    borderRadius="md"
                    p={3}
                    borderColor={selectedSources.includes(ds.key) ? "green.400" : "gray.200"}
                    bg={selectedSources.includes(ds.key) ? "green.50" : "white"}
                    transition="all 0.15s"
                  >
                    <Checkbox value={ds.key} fontWeight="medium">
                      {ds.label}
                    </Checkbox>
                    <Text fontSize="xs" color="gray.500" mt={1} ml={6}>{ds.description}</Text>
                    <Flex mt={2} ml={6} gap={1} flexWrap="wrap">
                      {ds.columns.slice(0, 5).map((c) => (
                        <Tag key={c} size="sm" colorScheme="gray" variant="subtle">{c}</Tag>
                      ))}
                      {ds.columns.length > 5 && (
                        <Tag size="sm" colorScheme="gray" variant="subtle">+{ds.columns.length - 5}</Tag>
                      )}
                    </Flex>
                  </Box>
                ))}
              </SimpleGrid>
            </CheckboxGroup>
          )}
        </CardBody>
      </Card>

      {/* ── Scope parameters (driven by selected sources) ─────────────────── */}
      {selectedSources.length > 0 && (
        <Card>
          <CardHeader><Heading size="md">2. Configure Scope</Heading></CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
              {scopeParams.map((p) => (
                <FormControl key={p.name}>
                  <FormLabel fontSize="sm">{p.label}</FormLabel>
                  <Input
                    size="sm"
                    placeholder={p.placeholder ?? String(p.default ?? "")}
                    value={scopeValues[p.name] ?? ""}
                    onChange={(e) => setScopeValues((prev) => ({ ...prev, [p.name]: e.target.value }))}
                  />
                  {p.type === "string_list" && (
                    <FormHelperText fontSize="xs">Comma-separated, e.g. "North Carolina, Iowa"</FormHelperText>
                  )}
                </FormControl>
              ))}
            </SimpleGrid>
          </CardBody>
        </Card>
      )}

      {/* ── Run ───────────────────────────────────────────────────────────── */}
      <Flex gap={4} align="center">
        <Button
          colorScheme="green"
          size="lg"
          isDisabled={selectedSources.length === 0 || isRunning}
          isLoading={runMutation.isPending}
          loadingText="Starting…"
          onClick={() => { setJobId(null); runMutation.mutate() }}
        >
          Start Ingestion
        </Button>
        {selectedSources.length > 0 && (
          <Text fontSize="sm" color="gray.500">
            {selectedSources.length} source{selectedSources.length > 1 ? "s" : ""} selected
          </Text>
        )}
      </Flex>

      {runMutation.isError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          <AlertDescription fontSize="sm">
            {(runMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              "Failed to start ingestion. Check backend logs."}
          </AlertDescription>
        </Alert>
      )}

      {/* ── Job status ────────────────────────────────────────────────────── */}
      {jobStatus && (
        <Card>
          <CardHeader>
            <Flex align="center" gap={3}>
              <Heading size="md">Ingestion Progress</Heading>
              <Badge
                colorScheme={
                  isDone ? "green" : hasErrors && !isRunning ? "red" : isRunning ? "blue" : "gray"
                }
              >
                {jobStatus.status}
              </Badge>
            </Flex>
          </CardHeader>
          <CardBody>
            <Stack spacing={3}>
              <Progress
                value={Math.round(jobStatus.progress * 100)}
                colorScheme={isDone ? "green" : "blue"}
                size="sm"
                borderRadius="full"
                hasStripe={isRunning}
                isAnimated={isRunning}
              />
              <Text fontSize="sm" color="gray.600">{jobStatus.message}</Text>

              {isDone && !hasErrors && (
                <Alert status="success" borderRadius="md">
                  <AlertIcon />
                  <AlertDescription>Ingestion completed successfully.</AlertDescription>
                </Alert>
              )}

              {hasErrors && (
                <>
                  <Divider />
                  <Text fontWeight="medium" fontSize="sm" color="red.600">
                    {jobStatus.errors.length} error{jobStatus.errors.length > 1 ? "s" : ""}:
                  </Text>
                  <Box
                    maxH="160px"
                    overflowY="auto"
                    fontSize="xs"
                    fontFamily="mono"
                    bg="red.50"
                    p={3}
                    borderRadius="md"
                  >
                    {jobStatus.errors.map((e, i) => <Text key={i} color="red.700">{e}</Text>)}
                  </Box>
                </>
              )}
            </Stack>
          </CardBody>
        </Card>
      )}
    </Stack>
  )
}
