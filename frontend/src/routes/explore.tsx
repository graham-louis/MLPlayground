import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Select,
  Spinner,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import axios from "axios"
import { useState } from "react"

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

function ExplorePage() {
  const [state, setState] = useState("North Carolina")
  const [crop, setCrop] = useState("")
  const [startYear, setStartYear] = useState("2000")
  const [endYear, setEndYear] = useState("2022")
  const [activeTab, setActiveTab] = useState<"yields" | "weather" | "soil">("yields")
  const [queryParams, setQueryParams] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)

  const { data: cropsData } = useQuery({
    queryKey: ["crops", state],
    queryFn: () =>
      axios
        .get("/api/v1/yields/crops", { params: { state } })
        .then((r) => r.data as string[]),
    enabled: !!state,
  })

  const { data: yieldsData, isLoading: yieldsLoading } = useQuery({
    queryKey: ["yields", queryParams],
    queryFn: () =>
      axios
        .get("/api/v1/yields/", { params: queryParams })
        .then((r) => r.data),
    enabled: submitted && activeTab === "yields",
  })

  const { data: weatherData, isLoading: weatherLoading } = useQuery({
    queryKey: ["weather", queryParams],
    queryFn: () =>
      axios
        .get("/api/v1/weather/", { params: queryParams })
        .then((r) => r.data),
    enabled: submitted && activeTab === "weather",
  })

  const { data: soilData, isLoading: soilLoading } = useQuery({
    queryKey: ["soil", queryParams],
    queryFn: () =>
      axios
        .get("/api/v1/soil/", { params: queryParams })
        .then((r) => r.data),
    enabled: submitted && activeTab === "soil",
  })

  const handleFetch = () => {
    const params: Record<string, string> = { state }
    if (crop) params.crop = crop
    if (startYear) params.start_year = startYear
    if (endYear) params.end_year = endYear
    setQueryParams(params)
    setSubmitted(true)
  }

  const isLoading = yieldsLoading || weatherLoading || soilLoading
  const currentData =
    activeTab === "yields"
      ? yieldsData
      : activeTab === "weather"
        ? weatherData
        : soilData

  const tableRows = currentData?.data ?? []
  const columns = tableRows.length > 0 ? Object.keys(tableRows[0]) : []

  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Data Explorer</Heading>

      <Card>
        <CardHeader>
          <Heading size="md">Filters</Heading>
        </CardHeader>
        <CardBody>
          <Flex gap={4} wrap="wrap">
            <FormControl maxW="200px">
              <FormLabel>State</FormLabel>
              <Select value={state} onChange={(e) => setState(e.target.value)}>
                {US_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </Select>
            </FormControl>
            <FormControl maxW="200px">
              <FormLabel>Crop</FormLabel>
              <Select value={crop} onChange={(e) => setCrop(e.target.value)} placeholder="All crops">
                {(cropsData ?? []).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </Select>
            </FormControl>
            <FormControl maxW="120px">
              <FormLabel>Start Year</FormLabel>
              <Input type="number" value={startYear} onChange={(e) => setStartYear(e.target.value)} />
            </FormControl>
            <FormControl maxW="120px">
              <FormLabel>End Year</FormLabel>
              <Input type="number" value={endYear} onChange={(e) => setEndYear(e.target.value)} />
            </FormControl>
            <FormControl maxW="150px">
              <FormLabel>Data Type</FormLabel>
              <Select value={activeTab} onChange={(e) => setActiveTab(e.target.value as "yields" | "weather" | "soil")}>
                <option value="yields">Yields</option>
                <option value="weather">Weather</option>
                <option value="soil">Soil</option>
              </Select>
            </FormControl>
          </Flex>
          <Button mt={4} colorScheme="green" onClick={handleFetch}>
            Load Data
          </Button>
        </CardBody>
      </Card>

      {isLoading && (
        <Flex justify="center" py={8}>
          <Spinner size="xl" color="green.500" />
        </Flex>
      )}

      {!isLoading && submitted && (
        <Card>
          <CardHeader>
            <Heading size="md">
              Results{" "}
              <Text as="span" fontSize="sm" color="gray.500">
                ({currentData?.count ?? 0} records)
              </Text>
            </Heading>
          </CardHeader>
          <CardBody overflowX="auto">
            {tableRows.length === 0 ? (
              <Text color="gray.500">No data found. Try adjusting your filters or run the data ingestion pipeline first.</Text>
            ) : (
              <Table size="sm" variant="striped">
                <Thead>
                  <Tr>
                    {columns.map((col) => (
                      <Th key={col}>{col}</Th>
                    ))}
                  </Tr>
                </Thead>
                <Tbody>
                  {tableRows.slice(0, 100).map((row: Record<string, unknown>, i: number) => (
                    <Tr key={i}>
                      {columns.map((col) => (
                        <Td key={col}>{row[col] != null ? String(row[col]) : ""}</Td>
                      ))}
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </CardBody>
        </Card>
      )}
    </Stack>
  )
}
