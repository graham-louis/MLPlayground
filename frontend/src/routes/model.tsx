import {
  Card,
  CardBody,
  CardHeader,
  Heading,
  Stack,
  Text,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/model")({
  component: ModelPage,
})

function ModelPage() {
  return (
    <Stack spacing={6}>
      <Heading size="lg" color="green.700">Model Training</Heading>
      <Card>
        <CardHeader>
          <Heading size="md">AutoML Pipeline</Heading>
        </CardHeader>
        <CardBody>
          <Stack spacing={3}>
            <Text>
              Select a dataset from the Data Explorer, then train a machine learning model to predict crop yields.
            </Text>
            <Text color="gray.500">
              Supported models: Linear Regression, Random Forest, Gradient Boosting, and more via PyCaret integration.
            </Text>
            <Text color="orange.500">
              ⚠️ Model training requires data to be loaded first. Navigate to Data Explorer to load data.
            </Text>
          </Stack>
        </CardBody>
      </Card>
    </Stack>
  )
}
