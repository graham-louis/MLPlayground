import {
  Badge,
  Box,
  Card,
  CardBody,
  CardHeader,
  Grid,
  Heading,
  Stack,
  Text,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import axios from "axios"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: () => axios.get("/api/v1/utils/health-check/").then(r => r.data),
    retry: false,
  })

  return (
    <Stack spacing={8}>
      <Box>
        <Heading size="xl" color="green.700">MLPlayground</Heading>
        <Text mt={2} color="gray.600" fontSize="lg">
          An extensible, researcher-friendly platform for agricultural machine learning.
        </Text>
        <Badge colorScheme={healthData ? "green" : "red"} mt={2}>
          API: {healthData ? "Connected" : "Disconnected"}
        </Badge>
      </Box>

      <Grid templateColumns="repeat(3, 1fr)" gap={6}>
        <Card>
          <CardHeader>
            <Heading size="md">🌽 Crop Yields</Heading>
          </CardHeader>
          <CardBody>
            <Text>Historical crop yield data from USDA NASS for states across the US. Filter by crop, state, and year range.</Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <Heading size="md">🌤️ Climate Data</Heading>
          </CardHeader>
          <CardBody>
            <Text>Annual weather metrics including temperature, precipitation, and Growing Degree Days from NASA NLDAS.</Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <Heading size="md">🌱 Soil Properties</Heading>
          </CardHeader>
          <CardBody>
            <Text>Soil characteristics (pH, organic matter, sand/clay %) from SSURGO for every county.</Text>
          </CardBody>
        </Card>
      </Grid>

      <Card>
        <CardHeader>
          <Heading size="md">About MLPlayground</Heading>
        </CardHeader>
        <CardBody>
          <Stack spacing={3}>
            <Text><strong>Researcher-Centric:</strong> Built for users who know their domain (data/science) better than they know complex software patterns.</Text>
            <Text><strong>Plug-and-Play:</strong> Adding a new dataset is as simple as dropping a single script into a folder.</Text>
            <Text><strong>Transparent:</strong> Every step of the pipeline—from data fetching to model prediction—is inspectable and explainable.</Text>
          </Stack>
        </CardBody>
      </Card>
    </Stack>
  )
}
