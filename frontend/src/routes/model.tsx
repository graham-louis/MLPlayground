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
  Select,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatHelpText,
  StatLabel,
  StatNumber,
  Text,
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

const MODEL_OPTIONS = [
  { value: "random_forest",      label: "Random Forest" },
  { value: "gradient_boosting",  label: "Gradient Boosting" },
  { value: "linear_regression",  label: "Linear Regression" },
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

// colour for the importance bar chart (green gradient)
const BAR_COLOURS = ["#276749", "#38a169", "#48bb78", "#68d391", "#9ae6b4", "#c6f6d5"]

// ── Component ──────────────────────────────────────────────────────────────

function ModelPage() {
  const [state, setState] = useState("North Carolina")
  const [crop, setCrop] = useState("")
  const [modelType, setModelType] = useState("random_forest")
  const [startYear, setStartYear] = useState("2000")
  const [endYear, setEndYear] = useState("2022")
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(
    ALL_FEATURES.map((f) => f.key)
  )

  // Fetch crops available for the selected state
  const { data: crops = [] } = useQuery<string[]>({
    queryKey: ["crops", state],
    queryFn: () =>
      axios.get("/api/v1/yields/crops", { params: { state } }).then((r) => r.data),
    enabled: !!state,
  })

  // Model training mutation
  const trainMutation = useMutation<TrainResult, { response?: { data?: { detail?: string } } }>({
    mutationFn: () =>
      axios
        .post("/api/v1/models/train", {
          state,
          crop,
          model_type: modelType,
          start_year: parseInt(startYear),
          end_year: parseInt(endYear),
          features: selectedFeatures,
        })
        .then((r) => r.data as TrainResult),
  })

  const result = trainMutation.data
  const errorMsg =
    trainMutation.error?.response?.data?.detail ??
    "Training failed. Check that you have ingested data for this state and crop."

  const weatherFeatures = ALL_FEATURES.filter((f) => f.group === "Weather")
  const soilFeatures    = ALL_FEATURES.filter((f) => f.group === "Soil")

  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Model Training</Heading>

      {/* ── Configuration form ─────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <Heading size="md">Configure Your Model</Heading>
        </CardHeader>
        <CardBody>
          <Stack spacing={5}>
            {/* Target selection */}
            <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
              <FormControl>
                <FormLabel>State</FormLabel>
                <Select value={state} onChange={(e) => { setState(e.target.value); setCrop("") }}>
                  {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Crop (target)</FormLabel>
                <Select
                  value={crop}
                  onChange={(e) => setCrop(e.target.value)}
                  placeholder="Select a crop…"
                >
                  {crops.map((c) => <option key={c} value={c}>{c}</option>)}
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Start Year</FormLabel>
                <Select value={startYear} onChange={(e) => setStartYear(e.target.value)}>
                  {Array.from({ length: 43 }, (_, i) => 1980 + i).map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>End Year</FormLabel>
                <Select value={endYear} onChange={(e) => setEndYear(e.target.value)}>
                  {Array.from({ length: 43 }, (_, i) => 1980 + i).map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </Select>
              </FormControl>
            </SimpleGrid>

            {/* Model type */}
            <FormControl>
              <FormLabel>Model Type</FormLabel>
              <Select value={modelType} onChange={(e) => setModelType(e.target.value)} maxW="300px">
                {MODEL_OPTIONS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </Select>
            </FormControl>

            <Divider />

            {/* Feature selection */}
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
                  <CheckboxGroup
                    value={selectedFeatures}
                    onChange={(vals) => setSelectedFeatures(vals as string[])}
                  >
                    <Stack spacing={2}>
                      {weatherFeatures.map((f) => (
                        <Checkbox key={f.key} value={f.key}>{f.label}</Checkbox>
                      ))}
                    </Stack>
                  </CheckboxGroup>
                </Box>
                <Box>
                  <Text fontWeight="medium" mb={2} color="green.700">🌱 Soil</Text>
                  <CheckboxGroup
                    value={selectedFeatures}
                    onChange={(vals) => setSelectedFeatures(vals as string[])}
                  >
                    <Stack spacing={2}>
                      {soilFeatures.map((f) => (
                        <Checkbox key={f.key} value={f.key}>{f.label}</Checkbox>
                      ))}
                    </Stack>
                  </CheckboxGroup>
                </Box>
              </SimpleGrid>
            </Box>

            <Button
              colorScheme="green"
              size="lg"
              isLoading={trainMutation.isPending}
              loadingText="Training model…"
              isDisabled={!crop || selectedFeatures.length === 0}
              onClick={() => trainMutation.mutate()}
              alignSelf="flex-start"
            >
              Train Model
            </Button>

            {!crop && (
              <Text color="orange.500" fontSize="sm">
                ⚠️ Select a crop above to enable training.
              </Text>
            )}
          </Stack>
        </CardBody>
      </Card>

      {/* ── Loading state ──────────────────────────────────────────────── */}
      {trainMutation.isPending && (
        <Flex justify="center" py={8}>
          <Stack align="center" spacing={3}>
            <Spinner size="xl" color="green.500" />
            <Text color="gray.500">Training… this may take a moment.</Text>
          </Stack>
        </Flex>
      )}

      {/* ── Error state ────────────────────────────────────────────────── */}
      {trainMutation.isError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          <AlertDescription>{errorMsg}</AlertDescription>
        </Alert>
      )}

      {/* ── Results ────────────────────────────────────────────────────── */}
      {result && (
        <Stack spacing={4}>
          {/* Metric summary cards */}
          <Card>
            <CardHeader>
              <Flex align="center" gap={3}>
                <Heading size="md">Results</Heading>
                <Badge colorScheme="green" fontSize="sm">
                  {MODEL_OPTIONS.find((m) => m.value === result.model_type)?.label}
                </Badge>
                <Badge colorScheme="blue" fontSize="sm">
                  {result.crop} · {result.state}
                </Badge>
              </Flex>
            </CardHeader>
            <CardBody>
              <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                <Stat>
                  <StatLabel>R² Score</StatLabel>
                  <StatNumber color={result.r2 >= 0.7 ? "green.600" : result.r2 >= 0.4 ? "orange.500" : "red.500"}>
                    {(result.r2 * 100).toFixed(1)}%
                  </StatNumber>
                  <StatHelpText>
                    {result.r2 >= 0.7 ? "Good fit" : result.r2 >= 0.4 ? "Moderate fit" : "Poor fit"}
                  </StatHelpText>
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

          {/* Feature importances */}
          <Card>
            <CardHeader>
              <Heading size="md">Feature Importances</Heading>
              <Text fontSize="sm" color="gray.500" mt={1}>
                Which variables had the most influence on the prediction?
              </Text>
            </CardHeader>
            <CardBody>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={result.feature_importances}
                  layout="vertical"
                  margin={{ top: 4, right: 30, left: 130, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    fontSize={12}
                  />
                  <YAxis
                    type="category"
                    dataKey="feature"
                    width={125}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(f) =>
                      ALL_FEATURES.find((x) => x.key === f)?.label ?? f
                    }
                  />
                  <Tooltip
                    formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Importance"]}
                    labelFormatter={(f) =>
                      ALL_FEATURES.find((x) => x.key === f)?.label ?? f
                    }
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
      )}
    </Stack>
  )
}
