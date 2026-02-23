import {
  Box,
  Container,
  Flex,
  Heading,
  Link,
  Text,
} from "@chakra-ui/react"
import { Outlet, createRootRoute } from "@tanstack/react-router"

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return (
    <Box minH="100vh" bg="gray.50">
      <Box as="nav" bg="green.700" color="white" py={4} px={6} shadow="md">
        <Flex align="center" justify="space-between" maxW="1200px" mx="auto">
          <Heading size="md">🌱 MLPlayground</Heading>
          <Flex gap={6}>
            <Link href="/" color="white" fontWeight="medium">Home</Link>
            <Link href="/explore" color="white" fontWeight="medium">Data Explorer</Link>
            <Link href="/model" color="white" fontWeight="medium">Model</Link>
          </Flex>
        </Flex>
      </Box>
      <Container maxW="1200px" py={8}>
        <Outlet />
      </Container>
    </Box>
  )
}
