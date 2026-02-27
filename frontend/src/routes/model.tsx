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
  Checkbox,
  CheckboxGroup,
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
  TabList,
  TabPanel,
  TabPanels,
  Table,
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
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export const Route = createFileRoute("/model")({
  component: ModelPage,
})

// ── Types ──────────────────────────────────────────────────────────────────

interface FeatureImportance {
  feature: string
  importance: number
}

interface TrainResult {
  run_id?: string
  model_type: string
  n_samples: number
  n_train: number
  n_test: number
  r2: number
  rmse: number
  feature_importances: FeatureImportance[]
  state: string
  crop: string
  start_year: number
  end_year: number
  county?: string
}

interface PredictResult {
  predicted_yield: number
  model_type: string
  training_r2: number
  training_rmse: number
  units: string
}

interface ModelTypeInfo {
  key: string
  label: string
  kind: string
  description: string
  supports_predict: boolean
}

interface ModelRunRecord {
  id: number
  run_id: string
  model_type: string
  feature_columns: string   // JSON
  filters: string           // JSON
  r2: number | null
  rmse: number | null
  n_samples: number | null
  created_at: string
}

// ── Constants ──────────────────────────────────────────────────────────────

const ALL_FEATURES = [
  { key: "avg_temp",       label: "Avg Temperature (°C)",      group: "Weather" },
  { key: "precipitation",  label: "Total Precipitation (mm)",  group: "Weather" },
  { key: "gdd",            label: "Growing Degree Days",        group: "Weather" },
  { key: "vp",             label: "Vapour Pressure (Pa)",       group: "Weather" },
  { key: "srad",           label: "Solar Radiation (W/m²)",     group: "Weather" },
  { key: "ph",             label: "Soil pH",                    group: "Soil" },
  { key: "organic_matter", label: "Organic Matter (%)",         group: "Soil" },
  { key: "sand_pct",       label: "Sand Content (%)",           group: "Soil" },
  { key: "clay_pct",       label: "Clay Content (%)",           group: "Soil" },
]

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

const BAR_COLOURS = ["#276749", "#38a169", "#48bb78", "#68d391", "#9ae6b4", "#c6f6d5"]
const YEAR_OPTIONS = Array.from({ length: 43 }, (_, i) => 1980 + i)

// ── Shared config hook ─────────────────────────────────────────────────────

function useModelConfig() {
  const [state, setState] = useState("North Carolina")
  const [crop, setCrop] = useState("")
  const [modelType, setModelType] = useState("random_forest")
  const [startYear, setStartYear] = useState("2000")
  const [endYear, setEndYear] = useState("2022")
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(ALL_FEATURES.map((f) => f.key))

  const { data: crops = [] } = useQuery<string[]>({
    queryKey: ["crops", state],
    queryFn: () =>
      axios.get("/api/v1/data/yields/distinct/crop", { params: { state } }).then((r) => r.data),
    enabled: !!state,
  })

  // Fetch model types from registry
  const { data: modelTypes = [] } = useQuery<ModelTypeInfo[]>({
    queryKey: ["model-types"],
    queryFn: () => axios.get("/api/v1/models/types").then((r) => r.data),
  })

  return { state, setState, crop, setCrop, modelType, setModelType,
    startYear, setStartYear, endYear, setEndYear,
    selectedFeatures, setSelectedFeatures, crops, modelTypes }
}

// ── Page ───────────────────────────────────────────────────────────────────

function ModelPage() {
  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Model Training</Heading>
      <Tabs colorScheme="green" variant="enclosed" isLazy>
        <TabList>
          <Tab>Train &amp; Evaluate</Tab>
          <Tab>Predict Yield</Tab>
          <Tab>Saved Models</Tab>
        </TabList>
        <TabPanels>
          <TabPanel p={0} pt={4}><TrainTab /></TabPanel>
          <TabPanel p={0} pt={4}><PredictTab /></TabPanel>
          <TabPanel p={0} pt={4}><SavedModelsTab /></TabPanel>
        </TabPanels>
      </Tabs>
    </Stack>
  )
}

// ── Train tab ──────────────────────────────────────────────────────────────

function TrainTab() {
  const cfg = useModelConfig()

  const trainMutation = useMutation<TrainResult, { response?: { data?: { detail?: string } } }>({
    mutationFn: () =>
      axios.post("/api/v1/models/train", {
        state: cfg.state,
        crop: cfg.crop,
        model_type: cfg.modelType,
        start_year: parseInt(cfg.startYear),
        end_year: parseInt(cfg.endYear),
        features: cfg.selectedFeatures,
      }).then((r) => r.data as TrainResult),
  })

  const result = trainMutation.data
  const errorMsg =
    trainMutation.error?.response?.data?.detail ??
    "Training failed. Check that you have ingested data for this state and crop."

  return (
    <Stack spacing={4}>
      <ConfigForm cfg={cfg} />

      <Button
        colorScheme="green"
        size="lg"
        isLoading={trainMutation.isPending}
        loadingText="Training model…"
        isDisabled={!cfg.crop || cfg.selectedFeatures.length === 0}
        onClick={() => trainMutation.mutate()}
        alignSelf="flex-start"
      >
        Train Model
      </Button>

      {!cfg.crop && (
        <Text color="orange.500" fontSize="sm">⚠️ Select a crop above to enable training.</Text>
      )}

      {trainMutation.isPending && (
        <Flex justify="center" py={8}>
          <Stack align="center" spacing={3}>
            <Spinner size="xl" color="green.500" />
            <Text color="gray.500">Training… this may take a moment.</Text>
          </Stack>
        </Flex>
      )}

      {trainMutation.isError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          <AlertDescription>{errorMsg}</AlertDescription>
        </Alert>
      )}

      {result && (
        <>
          {result.run_id && (
            <Alert status="success" borderRadius="md">
              <AlertIcon />
              <AlertDescription fontSize="sm">
                Model saved (run ID: <code>{result.run_id.slice(0, 8)}…</code>).
                Find it in the <strong>Saved Models</strong> tab.
              </AlertDescription>
            </Alert>
          )}
          <TrainResults result={result} modelTypes={cfg.modelTypes} />
        </>
      )}
    </Stack>
  )
}

// ── Predict tab ────────────────────────────────────────────────────────────

function PredictTab() {
  const cfg = useModelConfig()
  const [inputValues, setInputValues] = useState<Record<string, string>>({})

  const supportedModels = cfg.modelTypes.filter((m) => m.supports_predict)
  const effectiveModel = supportedModels.find((m) => m.key === cfg.modelType)
    ? cfg.modelType
    : (supportedModels[0]?.key ?? "random_forest")

  const predictMutation = useMutation<PredictResult, { response?: { data?: { detail?: string } } }>({
    mutationFn: () => {
      const parsed: Record<string, number> = {}
      for (const [k, v] of Object.entries(inputValues)) {
        const n = parseFloat(v)
        if (!isNaN(n)) parsed[k] = n
      }
      return axios.post("/api/v1/models/predict", {
        state: cfg.state,
        crop: cfg.crop,
        model_type: effectiveModel,
        train_start_year: parseInt(cfg.startYear),
        train_end_year: parseInt(cfg.endYear),
        features: cfg.selectedFeatures,
        input_values: parsed,
      }).then((r) => r.data as PredictResult)
    },
  })

  const result = predictMutation.data
  const errorMsg =
    predictMutation.error?.response?.data?.detail ??
    "Prediction failed. Ensure data is ingested for the selected state and crop."

  return (
    <Stack spacing={4}>
      <Alert status="info" borderRadius="md">
        <AlertIcon />
        <AlertDescription fontSize="sm">
          The model is trained on historical data for the selected state/crop/years, then applied
          to the feature values you enter below. Great for counterfactual questions.
          You can also load a pre-trained model from the <strong>Saved Models</strong> tab.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader><Heading size="md">Training Scope</Heading></CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <FormControl>
              <FormLabel>State</FormLabel>
              <Select value={cfg.state} onChange={(e) => { cfg.setState(e.target.value); cfg.setCrop("") }}>
                {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>Crop (target)</FormLabel>
              <Select value={cfg.crop} onChange={(e) => cfg.setCrop(e.target.value)} placeholder="Select a crop…">
                {cfg.crops.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>Train Start Year</FormLabel>
              <Select value={cfg.startYear} onChange={(e) => cfg.setStartYear(e.target.value)}>
                {YEAR_OPTIONS.map((y) => <option key={y} value={y}>{y}</option>)}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>Train End Year</FormLabel>
              <Select value={cfg.endYear} onChange={(e) => cfg.setEndYear(e.target.value)}>
                {YEAR_OPTIONS.map((y) => <option key={y} value={y}>{y}</option>)}
              </Select>
            </FormControl>
          </SimpleGrid>
          <FormControl mt={4} maxW="300px">
            <FormLabel>Model Type</FormLabel>
            <Select value={effectiveModel} onChange={(e) => cfg.setModelType(e.target.value)}>
              {supportedModels.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </Select>
          </FormControl>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Heading size="md">Input Feature Values</Heading>
          <Text fontSize="sm" color="gray.500" mt={1}>Leave blank to use the training-set mean.</Text>
        </CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 2, md: 3 }} spacing={4}>
            {ALL_FEATURES.filter((f) => cfg.selectedFeatures.includes(f.key)).map((f) => (
              <FormControl key={f.key}>
                <FormLabel fontSize="sm">{f.label}</FormLabel>
                <Input
                  type="number"
                  placeholder="use mean"
                  value={inputValues[f.key] ?? ""}
                  onChange={(e) => setInputValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  size="sm"
                />
              </FormControl>
            ))}
          </SimpleGrid>
        </CardBody>
      </Card>

      <Button
        colorScheme="green" size="lg"
        isLoading={predictMutation.isPending} loadingText="Predicting…"
        isDisabled={!cfg.crop}
        onClick={() => predictMutation.mutate()}
        alignSelf="flex-start"
      >
        Predict Yield
      </Button>

      {!cfg.crop && <Text color="orange.500" fontSize="sm">⚠️ Select a crop to enable prediction.</Text>}

      {predictMutation.isPending && (
        <Flex justify="center" py={6}><Spinner size="xl" color="green.500" /></Flex>
      )}

      {predictMutation.isError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon /><AlertDescription>{errorMsg}</AlertDescription>
        </Alert>
      )}

      {result && <PredictResultCard result={result} modelTypes={cfg.modelTypes} />}
    </Stack>
  )
}

// ── Saved Models tab ──────────────────────────────────────────────────────

function SavedModelsTab() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [inputValues, setInputValues] = useState<Record<string, string>>({})

  const { data: runsResp, isLoading } = useQuery({
    queryKey: ["model-runs"],
    queryFn: () =>
      axios.get("/api/v1/models/").then((r) => r.data as { data: ModelRunRecord[]; count: number }),
  })
  const runs = runsResp?.data ?? []

  const selectedRun = runs.find((r) => r.run_id === selectedRunId)
  const selectedFeatures: string[] = selectedRun
    ? JSON.parse(selectedRun.feature_columns)
    : []

  const predictMutation = useMutation<PredictResult, { response?: { data?: { detail?: string } } }>({
    mutationFn: () => {
      const parsed: Record<string, number> = {}
      for (const [k, v] of Object.entries(inputValues)) {
        const n = parseFloat(v)
        if (!isNaN(n)) parsed[k] = n
      }
      return axios
        .post(`/api/v1/models/${selectedRunId}/predict`, { input_values: parsed })
        .then((r) => r.data as PredictResult)
    },
  })

  return (
    <Stack spacing={4}>
      <Alert status="info" borderRadius="md">
        <AlertIcon />
        <AlertDescription fontSize="sm">
          Select a previously trained model and run predictions without retraining.
          Models are persisted on disk and reloaded on demand.
        </AlertDescription>
      </Alert>

      {isLoading ? (
        <Flex justify="center" py={8}><Spinner color="green.500" /></Flex>
      ) : runs.length === 0 ? (
        <Alert status="warning" borderRadius="md">
          <AlertIcon />
          <AlertDescription>No saved models yet. Train a model on the <strong>Train &amp; Evaluate</strong> tab first.</AlertDescription>
        </Alert>
      ) : (
        <Card>
          <CardHeader><Heading size="md">Saved Runs ({runs.length})</Heading></CardHeader>
          <CardBody overflowX="auto">
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Model</Th>
                  <Th>Filters</Th>
                  <Th>R²</Th>
                  <Th>RMSE</Th>
                  <Th>Samples</Th>
                  <Th>Date</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {runs.map((run) => {
                  const filters = JSON.parse(run.filters)
                  return (
                    <Tr key={run.run_id} bg={selectedRunId === run.run_id ? "green.50" : undefined}>
                      <Td><Badge colorScheme="green">{run.model_type}</Badge></Td>
                      <Td fontSize="xs">{filters.state} · {filters.crop} · {filters.start_year}–{filters.end_year}</Td>
                      <Td>{run.r2 != null ? (run.r2 * 100).toFixed(1) + "%" : "—"}</Td>
                      <Td>{run.rmse != null ? run.rmse.toFixed(2) : "—"}</Td>
                      <Td>{run.n_samples ?? "—"}</Td>
                      <Td fontSize="xs">{run.created_at.slice(0, 10)}</Td>
                      <Td>
                        <Button
                          size="xs"
                          colorScheme="green"
                          variant={selectedRunId === run.run_id ? "solid" : "outline"}
                          onClick={() => { setSelectedRunId(run.run_id); setInputValues({}) }}
                        >
                          {selectedRunId === run.run_id ? "Selected" : "Select"}
                        </Button>
                      </Td>
                    </Tr>
                  )
                })}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {selectedRun && (
        <Card>
          <CardHeader>
            <Flex align="center" gap={3}>
              <Heading size="md">Predict with {selectedRun.model_type}</Heading>
              <Badge colorScheme="green">{selectedRun.run_id.slice(0, 8)}…</Badge>
            </Flex>
            <Text fontSize="xs" color="gray.500" mt={1}>Leave blank to use 0.0 as default.</Text>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 2, md: 3 }} spacing={4}>
              {selectedFeatures.map((f) => {
                const meta = ALL_FEATURES.find((x) => x.key === f)
                return (
                  <FormControl key={f}>
                    <FormLabel fontSize="sm">{meta?.label ?? f}</FormLabel>
                    <Input
                      type="number"
                      size="sm"
                      placeholder="0"
                      value={inputValues[f] ?? ""}
                      onChange={(e) => setInputValues((prev) => ({ ...prev, [f]: e.target.value }))}
                    />
                  </FormControl>
                )
              })}
            </SimpleGrid>

            <Button
              mt={4}
              colorScheme="green"
              isLoading={predictMutation.isPending}
              loadingText="Predicting…"
              onClick={() => predictMutation.mutate()}
            >
              Predict
            </Button>

            {predictMutation.isError && (
              <Alert status="error" mt={3} borderRadius="md">
                <AlertIcon />
                <AlertDescription fontSize="sm">
                  {(predictMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                    "Prediction failed."}
                </AlertDescription>
              </Alert>
            )}

            {predictMutation.data && (
              <Box mt={4}>
                <Divider mb={3} />
                <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                  <Stat>
                    <StatLabel>Predicted Yield</StatLabel>
                    <StatNumber color="green.600">{predictMutation.data.predicted_yield.toFixed(1)}</StatNumber>
                    <StatHelpText>{predictMutation.data.units}</StatHelpText>
                  </Stat>
                  <Stat>
                    <StatLabel>Training R²</StatLabel>
                    <StatNumber>{(predictMutation.data.training_r2 * 100).toFixed(1)}%</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Training RMSE</StatLabel>
                    <StatNumber>{predictMutation.data.training_rmse.toFixed(2)}</StatNumber>
                    <StatHelpText>bu/acre</StatHelpText>
                  </Stat>
                </SimpleGrid>
              </Box>
            )}
          </CardBody>
        </Card>
      )}
    </Stack>
  )
}

// ── Config form ────────────────────────────────────────────────────────────

function ConfigForm({ cfg }: { cfg: ReturnType<typeof useModelConfig> }) {
  const weatherFeatures = ALL_FEATURES.filter((f) => f.group === "Weather")
  const soilFeatures    = ALL_FEATURES.filter((f) => f.group === "Soil")
  const selectedModelMeta = cfg.modelTypes.find((m) => m.key === cfg.modelType)

  return (
    <Card>
      <CardHeader><Heading size="md">Configure Your Model</Heading></CardHeader>
      <CardBody>
        <Stack spacing={5}>
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <FormControl>
              <FormLabel>State</FormLabel>
              <Select value={cfg.state} onChange={(e) => { cfg.setState(e.target.value); cfg.setCrop("") }}>
                {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>Crop (target)</FormLabel>
              <Select value={cfg.crop} onChange={(e) => cfg.setCrop(e.target.value)} placeholder="Select a crop…">
                {cfg.crops.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>Start Year</FormLabel>
              <Select value={cfg.startYear} onChange={(e) => cfg.setStartYear(e.target.value)}>
                {YEAR_OPTIONS.map((y) => <option key={y} value={y}>{y}</option>)}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel>End Year</FormLabel>
              <Select value={cfg.endYear} onChange={(e) => cfg.setEndYear(e.target.value)}>
                {YEAR_OPTIONS.map((y) => <option key={y} value={y}>{y}</option>)}
              </Select>
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Model Type</FormLabel>
            <Select value={cfg.modelType} onChange={(e) => cfg.setModelType(e.target.value)} maxW="400px">
              {cfg.modelTypes.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </Select>
          </FormControl>

          {selectedModelMeta && (
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <AlertDescription fontSize="sm">{selectedModelMeta.description}</AlertDescription>
            </Alert>
          )}

          <Divider />

          <Box>
            <Text fontWeight="semibold" mb={3}>
              Features to include{" "}
              <Text as="span" color="gray.500" fontWeight="normal" fontSize="sm">
                (tick the variables you want the model to learn from)
              </Text>
            </Text>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Box>
                <Text fontWeight="medium" mb={2} color="blue.700">🌤️ Weather</Text>
                <CheckboxGroup value={cfg.selectedFeatures} onChange={(v) => cfg.setSelectedFeatures(v as string[])}>
                  <Stack spacing={2}>
                    {weatherFeatures.map((f) => <Checkbox key={f.key} value={f.key}>{f.label}</Checkbox>)}
                  </Stack>
                </CheckboxGroup>
              </Box>
              <Box>
                <Text fontWeight="medium" mb={2} color="green.700">🌱 Soil</Text>
                <CheckboxGroup value={cfg.selectedFeatures} onChange={(v) => cfg.setSelectedFeatures(v as string[])}>
                  <Stack spacing={2}>
                    {soilFeatures.map((f) => <Checkbox key={f.key} value={f.key}>{f.label}</Checkbox>)}
                  </Stack>
                </CheckboxGroup>
              </Box>
            </SimpleGrid>
          </Box>
        </Stack>
      </CardBody>
    </Card>
  )
}

// ── Train results panel ────────────────────────────────────────────────────

function TrainResults({ result, modelTypes }: { result: TrainResult; modelTypes: ModelTypeInfo[] }) {
  const modelLabel = modelTypes.find((m) => m.key === result.model_type)?.label ?? result.model_type

  return (
    <Stack spacing={4}>
      <Card>
        <CardHeader>
          <Flex align="center" gap={3}>
            <Heading size="md">Results</Heading>
            <Badge colorScheme="green" fontSize="sm">{modelLabel}</Badge>
            <Badge colorScheme="blue" fontSize="sm">{result.crop} · {result.state}</Badge>
          </Flex>
        </CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
            <Stat>
              <StatLabel>R² Score</StatLabel>
              <StatNumber color={result.r2 >= 0.7 ? "green.600" : result.r2 >= 0.4 ? "orange.500" : "red.500"}>
                {(result.r2 * 100).toFixed(1)}%
              </StatNumber>
              <StatHelpText>{result.r2 >= 0.7 ? "Good fit" : result.r2 >= 0.4 ? "Moderate" : "Poor fit"}</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>RMSE</StatLabel>
              <StatNumber>{result.rmse.toFixed(2)}</StatNumber>
              <StatHelpText>bu/acre error</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Training rows</StatLabel>
              <StatNumber>{result.n_train}</StatNumber>
              <StatHelpText>county-years</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Test rows</StatLabel>
              <StatNumber>{result.n_test}</StatNumber>
              <StatHelpText>held out</StatHelpText>
            </Stat>
          </SimpleGrid>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Heading size="md">Feature Importances</Heading>
        </CardHeader>
        <CardBody>
          <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={result.feature_importances}
                layout="vertical"
                margin={{ top: 4, right: 30, left: 130, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} fontSize={12} />
                <YAxis
                  type="category" dataKey="feature" width={125}
                  tick={{ fontSize: 12 }}
                  tickFormatter={(f) => ALL_FEATURES.find((x) => x.key === f)?.label ?? f}
                />
                <Tooltip
                  formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Importance"]}
                  labelFormatter={(f) => ALL_FEATURES.find((x) => x.key === f)?.label ?? f}
                />
                <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                  {result.feature_importances.map((_, i) => (
                    <Cell key={i} fill={BAR_COLOURS[i % BAR_COLOURS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
        </CardBody>
      </Card>
    </Stack>
  )
}

// ── Predict result card ────────────────────────────────────────────────────

function PredictResultCard({ result, modelTypes }: { result: PredictResult; modelTypes: ModelTypeInfo[] }) {
  return (
    <Card>
      <CardHeader>
        <Flex align="center" gap={3}>
          <Heading size="md">Prediction Result</Heading>
          <Badge colorScheme="green">
            {modelTypes.find((m) => m.key === result.model_type)?.label ?? result.model_type}
          </Badge>
        </Flex>
      </CardHeader>
      <CardBody>
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
          <Stat>
            <StatLabel>Predicted Yield</StatLabel>
            <StatNumber color="green.600">{result.predicted_yield.toFixed(1)}</StatNumber>
            <StatHelpText>{result.units}</StatHelpText>
          </Stat>
          <Stat>
            <StatLabel>Training R²</StatLabel>
            <StatNumber color={result.training_r2 >= 0.7 ? "green.600" : result.training_r2 >= 0.4 ? "orange.500" : "red.500"}>
              {(result.training_r2 * 100).toFixed(1)}%
            </StatNumber>
            <StatHelpText>model fit</StatHelpText>
          </Stat>
          <Stat>
            <StatLabel>Training RMSE</StatLabel>
            <StatNumber>{result.training_rmse.toFixed(2)}</StatNumber>
            <StatHelpText>bu/acre</StatHelpText>
          </Stat>
        </SimpleGrid>
      </CardBody>
    </Card>
  )
}
