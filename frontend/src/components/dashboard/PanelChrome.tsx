/**
 * PanelChrome — uniform wrapper for every dashboard panel (6.3).
 *
 * Provides:
 *   - Title bar with subtitle, download button, and fullscreen toggle
 *   - Loading spinner overlay when `isLoading` is true
 *   - Error banner when `error` is non-null
 *   - Fullscreen modal on the "⤢" button
 */
import {
  Box,
  Flex,
  IconButton,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Text,
  Tooltip,
  useDisclosure,
} from "@chakra-ui/react"
import type { ReactNode } from "react"

export interface PanelChromeProps {
  title: string
  subtitle?: string
  isLoading?: boolean
  error?: string | null
  /** If provided, renders a download icon that links to this URL. */
  downloadUrl?: string
  downloadFilename?: string
  children: ReactNode
}

export function PanelChrome({
  title,
  subtitle,
  isLoading = false,
  error,
  downloadUrl,
  downloadFilename,
  children,
}: PanelChromeProps) {
  const { isOpen, onOpen, onClose } = useDisclosure()

  const body = error ? (
    <Box p={3} bg="red.50" borderRadius="md" border="1px solid" borderColor="red.200">
      <Text color="red.600" fontSize="sm" fontWeight="medium">Error</Text>
      <Text color="red.500" fontSize="xs" mt={1}>{error}</Text>
    </Box>
  ) : (
    children
  )

  return (
    <>
      {/* ── Panel card ────────────────────────────────────────────────── */}
      <Box
        bg="white"
        border="1px solid"
        borderColor="gray.200"
        borderRadius="lg"
        overflow="hidden"
        display="flex"
        flexDirection="column"
        shadow="sm"
        _hover={{ shadow: "md", borderColor: "gray.300" }}
        transition="box-shadow 0.15s, border-color 0.15s"
        h="100%"
      >
        {/* Title bar */}
        <Flex
          align="center"
          justify="space-between"
          px={3}
          py={2}
          bg="gray.50"
          borderBottom="1px solid"
          borderColor="gray.200"
          flexShrink={0}
          gap={2}
        >
          <Box overflow="hidden" flex={1} minW={0}>
            <Text
              fontWeight="semibold"
              fontSize="sm"
              noOfLines={1}
              color="gray.700"
              title={title}
            >
              {title}
            </Text>
            {subtitle && (
              <Text fontSize="xs" color="gray.400" noOfLines={1}>
                {subtitle}
              </Text>
            )}
          </Box>

          <Flex gap={1} flexShrink={0}>
            {downloadUrl && (
              <Tooltip label="Download" placement="top" hasArrow>
                <a href={downloadUrl} download={downloadFilename ?? "download"}>
                  <IconButton
                    as="span"
                    aria-label="Download"
                    icon={<Text fontSize="sm" lineHeight={1}>↓</Text>}
                    size="xs"
                    variant="ghost"
                    colorScheme="gray"
                  />
                </a>
              </Tooltip>
            )}
            <Tooltip label="Fullscreen" placement="top" hasArrow>
              <IconButton
                aria-label="Fullscreen"
                icon={<Text fontSize="sm" lineHeight={1}>⤢</Text>}
                size="xs"
                variant="ghost"
                colorScheme="gray"
                onClick={onOpen}
              />
            </Tooltip>
          </Flex>
        </Flex>

        {/* Body */}
        <Box flex={1} overflow="auto" p={3} position="relative">
          {isLoading && (
            <Flex
              position="absolute"
              inset={0}
              align="center"
              justify="center"
              bg="whiteAlpha.800"
              zIndex={1}
              borderRadius="md"
            >
              <Spinner color="green.500" size="md" />
            </Flex>
          )}
          {body}
        </Box>
      </Box>

      {/* ── Fullscreen modal ──────────────────────────────────────────── */}
      <Modal isOpen={isOpen} onClose={onClose} size="5xl" scrollBehavior="inside">
        <ModalOverlay />
        <ModalContent maxW="95vw" maxH="95vh">
          <ModalHeader fontSize="md" pb={2}>
            {title}
            {subtitle && (
              <Text as="span" fontWeight="normal" fontSize="sm" color="gray.500" ml={2}>
                — {subtitle}
              </Text>
            )}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6} overflowY="auto">
            {error ? (
              <Text color="red.500">{error}</Text>
            ) : (
              children
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </>
  )
}
