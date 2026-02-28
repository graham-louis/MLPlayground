import {
  Box,
  Container,
  Flex,
  Heading,
  Link,
} from "@chakra-ui/react"
import { Outlet, createRootRoute, useRouterState } from "@tanstack/react-router"

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  const { location } = useRouterState()
  const isFullBleed = location.pathname === "/graph" || location.pathname === "/dashboard"

  return (
    <Box
      h={isFullBleed ? "100vh" : undefined}
      minH={isFullBleed ? undefined : "100vh"}
      overflow={isFullBleed ? "hidden" : undefined}
      bg="gray.50"
      display="flex"
      flexDirection="column"
    >
      <Box as="nav" bg="green.700" color="white" py={4} px={6} shadow="md" flexShrink={0}>
        <Flex align="center" justify="space-between" maxW={isFullBleed ? "none" : "1200px"} mx="auto">
          <Heading size="md">🌱 MLPlayground</Heading>
          <Flex gap={6}>
            <Link href="/graph" color="white" fontWeight="medium">Graph</Link>
            <Link href="/dashboard" color="white" fontWeight="medium">Dashboard</Link>
            <Link href="/" color="white" fontWeight="medium">Home</Link>
            <Link href="/explore" color="white" fontWeight="medium">Data Explorer</Link>
            <Link href="/model" color="white" fontWeight="medium">Model</Link>
            <Link href="/ingest" color="white" fontWeight="medium">Ingest</Link>
          </Flex>
        </Flex>
      </Box>
      {isFullBleed ? (
        <Box flex={1} display="flex" flexDirection="column" overflow="hidden">
          <Outlet />
        </Box>
      ) : (
        <Container maxW="1200px" py={8}>
          <Outlet />
        </Container>
      )}
    </Box>
  )
}
