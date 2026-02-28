import {
  Badge,
  Box,
  Button,
  Collapse,
  Divider,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  IconButton,
  Input,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Popover,
  PopoverArrow,
  PopoverBody,
  PopoverContent,
  PopoverTrigger,
  Select,
  Spinner,
  Stack,
  Switch,
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
  Tooltip,
  Tr,
  Wrap,
  WrapItem,
  useToast,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MiniMap,
  NodeResizer,
  Position,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  getBezierPath,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import dagre from "@dagrejs/dagre"
import axios from "axios"
import { useCallback, useEffect, useRef, useState } from "react"

export const Route = createFileRoute("/graph")({
  component: GraphPage,
})

// ── Types ──────────────────────────────────────────────────────────────────

interface JsonSchemaProperty {
  type?: string
  title?: string
  description?: string
  default?: unknown
  enum?: string[]
  items?: { type: string }
}

interface JsonSchema {
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
  title?: string
  type?: string
}

interface NodeInfo {
  node_id: string
  display_name: string
  category: string
  endpoint: string
  description: string
  inputs: string[]
  outputs: string[]
  params: string[]
  params_schema: JsonSchema
}

// Data attached to each ReactFlow node.
interface GraphNodeData {
  nodeInfo: NodeInfo
  params: Record<string, unknown>
  runStatus?: string
  label?: string        // user-provided custom name
  bypassed?: boolean
  [key: string]: unknown
}

interface DatasourceColumn {
  name: string
  type_str: string
}

interface DatasourceInfo {
  key: string
  columns: DatasourceColumn[]
  query_params: string[]
}

interface WorkflowSummary {
  id: number
  name: string
  description?: string
  created_at: string
  updated_at: string
}

interface WorkflowDetail extends WorkflowSummary {
  graph_spec: string
}

type GraphFlowNode = Node<GraphNodeData>

interface RunStatus {
  run_id: string
  status: "pending" | "running" | "success" | "error"
  node_statuses?: Record<string, string>
  error?: string
  created_at?: string
  updated_at?: string
}

interface ContextMenuState {
  x: number
  y: number
  nodeId: string
}

interface RunResult {
  run_id: string
  status: string
  result?: Record<string, unknown>
}

// ── Template workflows ─────────────────────────────────────────────────────

// These seed the canvas with a small pre-built graph to help users get started.

const TEMPLATES: Record<string, { nodes: GraphFlowNode[]; edges: Edge[] }> = {
  "CSV → Filter": {
    nodes: [
      {
        id: "n1",
        type: "graphNode",
        position: { x: 50, y: 150 },
        data: {
          nodeInfo: {
            node_id: "csv_source", display_name: "CSV Source", category: "Sources",
            endpoint: "", description: "Load CSV", inputs: [], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: { file_path: { type: "string", title: "File Path", default: "/app/data/sample.csv" } },
              required: ["file_path"],
            },
          },
          params: { file_path: "/app/data/sample.csv" },
        },
      },
      {
        id: "n2",
        type: "graphNode",
        position: { x: 300, y: 150 },
        data: {
          nodeInfo: {
            node_id: "filter", display_name: "Filter", category: "Transforms",
            endpoint: "", description: "Filter rows", inputs: ["dataframe"], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                column: { type: "string", title: "Column" },
                operator: { type: "string", title: "Operator", enum: ["==", "!=", ">", "<", ">=", "<="] },
                value: { type: "string", title: "Value" },
              },
              required: ["column", "operator", "value"],
            },
          },
          params: { column: "year", operator: ">", value: "2010" },
        },
      },
    ],
    edges: [
      { id: "e1-2", source: "n1", sourceHandle: "dataframe", target: "n2", targetHandle: "dataframe" },
    ],
  },

  "Yield Prediction (Weather + Soil)": {
    nodes: [
      {
        id: "t1",
        type: "graphNode",
        position: { x: 50, y: 50 },
        data: {
          nodeInfo: {
            node_id: "database_source", display_name: "Yields", category: "Sources",
            endpoint: "", description: "Crop yields", inputs: [], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                datasource_key: { type: "string", title: "Datasource" },
                filters_json: { type: "string", title: "Filters (JSON)", default: "{}" },
                limit: { type: "integer", title: "Limit", default: 5000 },
              },
              required: ["datasource_key"],
            },
          },
          params: { datasource_key: "yields", filters_json: "{}", limit: 5000 },
        },
      },
      {
        id: "t2",
        type: "graphNode",
        position: { x: 50, y: 220 },
        data: {
          nodeInfo: {
            node_id: "database_source", display_name: "Weather", category: "Sources",
            endpoint: "", description: "Annual weather", inputs: [], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                datasource_key: { type: "string", title: "Datasource" },
                filters_json: { type: "string", title: "Filters (JSON)", default: "{}" },
                limit: { type: "integer", title: "Limit", default: 5000 },
              },
              required: ["datasource_key"],
            },
          },
          params: { datasource_key: "weather", filters_json: "{}", limit: 5000 },
        },
      },
      {
        id: "t3",
        type: "graphNode",
        position: { x: 50, y: 390 },
        data: {
          nodeInfo: {
            node_id: "database_source", display_name: "Soil", category: "Sources",
            endpoint: "", description: "Soil properties", inputs: [], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                datasource_key: { type: "string", title: "Datasource" },
                filters_json: { type: "string", title: "Filters (JSON)", default: "{}" },
                limit: { type: "integer", title: "Limit", default: 5000 },
              },
              required: ["datasource_key"],
            },
          },
          params: { datasource_key: "soil", filters_json: "{}", limit: 5000 },
        },
      },
      {
        id: "t4",
        type: "graphNode",
        position: { x: 330, y: 130 },
        data: {
          nodeInfo: {
            node_id: "join", display_name: "Join Yields+Weather", category: "Transforms",
            endpoint: "", description: "Join on year/state/county", inputs: ["left", "right"], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                on: { type: "array", items: { type: "string" }, title: "On" },
                how: { type: "string", title: "How", enum: ["inner", "left", "right", "outer"], default: "inner" },
              },
              required: ["on"],
            },
          },
          params: { on: ["year", "state", "county"], how: "inner" },
        },
      },
      {
        id: "t5",
        type: "graphNode",
        position: { x: 610, y: 200 },
        data: {
          nodeInfo: {
            node_id: "join", display_name: "Join + Soil", category: "Transforms",
            endpoint: "", description: "Join with soil on state/county", inputs: ["left", "right"], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                on: { type: "array", items: { type: "string" }, title: "On" },
                how: { type: "string", title: "How", enum: ["inner", "left", "right", "outer"], default: "inner" },
              },
              required: ["on"],
            },
          },
          params: { on: ["state", "county"], how: "left" },
        },
      },
      {
        id: "t6",
        type: "graphNode",
        position: { x: 890, y: 200 },
        data: {
          nodeInfo: {
            node_id: "select_columns", display_name: "Select Features", category: "Transforms",
            endpoint: "", description: "Keep relevant columns", inputs: ["dataframe"], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                columns: { type: "array", items: { type: "string" }, title: "Columns" },
              },
              required: ["columns"],
            },
          },
          params: {
            columns: ["year", "state", "county", "crop", "value",
              "avg_temp", "precipitation", "gdd", "ph", "organic_matter", "sand_pct", "clay_pct"],
          },
        },
      },
      {
        id: "t7",
        type: "graphNode",
        position: { x: 1120, y: 200 },
        data: {
          nodeInfo: {
            node_id: "drop_na", display_name: "Drop NA", category: "Transforms",
            endpoint: "", description: "Remove rows with missing values", inputs: ["dataframe"], outputs: ["dataframe"],
            params: [], params_schema: {
              properties: {
                columns: { type: "array", items: { type: "string" }, title: "Columns", default: [] },
              },
            },
          },
          params: { columns: [] },
        },
      },
      {
        id: "t9",
        type: "graphNode",
        position: { x: 1350, y: 150 },
        data: {
          nodeInfo: {
            node_id: "trainer", display_name: "Train Yield Model", category: "Modeling",
            endpoint: "", description: "Random forest yield predictor", inputs: ["dataframe"],
            outputs: ["model", "metrics", "artifact_path", "feature_names"],
            params: [], params_schema: {
              properties: {
                model_type: { type: "string", title: "Model Type", enum: ["linear_regression", "random_forest", "gradient_boosting"], default: "random_forest" },
                target_column: { type: "string", title: "Target Column", default: "crop_yield" },
                feature_columns: { type: "array", items: { type: "string" }, title: "Feature Columns", default: [] },
                test_size: { type: "number", title: "Test Size", default: 0.2 },
                random_state: { type: "integer", title: "Random State", default: 42 },
              },
            },
          },
          params: {
            model_type: "random_forest",
            target_column: "value",
            feature_columns: ["avg_temp", "precipitation", "gdd", "ph", "organic_matter", "sand_pct", "clay_pct"],
            test_size: 0.2,
            random_state: 42,
          },
        },
      },
    ],
    edges: [
      { id: "et1-t4", source: "t1", sourceHandle: "dataframe", target: "t4", targetHandle: "left" },
      { id: "et2-t4", source: "t2", sourceHandle: "dataframe", target: "t4", targetHandle: "right" },
      { id: "et4-t5", source: "t4", sourceHandle: "dataframe", target: "t5", targetHandle: "left" },
      { id: "et3-t5", source: "t3", sourceHandle: "dataframe", target: "t5", targetHandle: "right" },
      { id: "et5-t6", source: "t5", sourceHandle: "dataframe", target: "t6", targetHandle: "dataframe" },
      { id: "et6-t7", source: "t6", sourceHandle: "dataframe", target: "t7", targetHandle: "dataframe" },
      { id: "et7-t9", source: "t7", sourceHandle: "dataframe", target: "t9", targetHandle: "dataframe" },
    ],
  },

  "NOAA Weather → Plot": {
    nodes: [
      {
        id: "r1",
        type: "graphNode",
        position: { x: 60, y: 160 },
        data: {
          nodeInfo: {
            node_id: "remote_fetch",
            display_name: "NOAA Annual Weather",
            category: "Sources",
            endpoint: "",
            description: "Fetch NOAA GSOY data for a US state",
            inputs: [],
            outputs: ["dataframe"],
            params: ["datasource_key", "scope_params_json"],
            params_schema: {
              properties: {
                datasource_key: {
                  type: "string",
                  title: "Datasource Key",
                  description: "Registered ingest datasource key",
                  default: "noaa_gsoy",
                },
                scope_params_json: {
                  type: "string",
                  title: "Scope Params (JSON)",
                  description: "Keys match the datasource's scope_params",
                  default: "{}",
                },
              },
              required: ["datasource_key"],
            },
          },
          params: {
            datasource_key: "noaa_gsoy",
            scope_params_json: JSON.stringify({
              state: "NC",
              start_year: 2015,
              end_year: 2022,
              variables: ["TAVG", "PRCP"],
            }),
          },
          label: "NOAA Weather (NC)",
        },
      },
      {
        id: "r2",
        type: "graphNode",
        position: { x: 340, y: 80 },
        data: {
          nodeInfo: {
            node_id: "plot",
            display_name: "Avg Temperature over Time",
            category: "Visualization",
            endpoint: "",
            description: "Line chart of TAVG by year",
            inputs: ["dataframe"],
            outputs: ["figure"],
            params: ["plot_type", "x_column", "y_column", "color_column", "title"],
            params_schema: {
              properties: {
                plot_type: { type: "string", title: "Plot Type", enum: ["scatter", "line", "histogram", "bar", "box"], default: "line" },
                x_column:  { type: "string", title: "X Column",  default: "" },
                y_column:  { type: "string", title: "Y Column",  default: "" },
                color_column: { type: "string", title: "Colour Column", default: "" },
                title: { type: "string", title: "Title", default: "" },
              },
            },
          },
          params: {
            plot_type: "line",
            x_column: "year",
            y_column: "tavg",
            color_column: "station",
            title: "Average Annual Temperature — NC",
          },
          label: "Temp over Time",
        },
      },
      {
        id: "r3",
        type: "graphNode",
        position: { x: 340, y: 280 },
        data: {
          nodeInfo: {
            node_id: "plot",
            display_name: "Precipitation over Time",
            category: "Visualization",
            endpoint: "",
            description: "Bar chart of PRCP by year",
            inputs: ["dataframe"],
            outputs: ["figure"],
            params: ["plot_type", "x_column", "y_column", "color_column", "title"],
            params_schema: {
              properties: {
                plot_type: { type: "string", title: "Plot Type", enum: ["scatter", "line", "histogram", "bar", "box"], default: "bar" },
                x_column:  { type: "string", title: "X Column",  default: "" },
                y_column:  { type: "string", title: "Y Column",  default: "" },
                color_column: { type: "string", title: "Colour Column", default: "" },
                title: { type: "string", title: "Title", default: "" },
              },
            },
          },
          params: {
            plot_type: "bar",
            x_column: "year",
            y_column: "prcp",
            color_column: "",
            title: "Annual Precipitation — NC",
          },
          label: "Precip over Time",
        },
      },
    ],
    edges: [
      { id: "er1-r2", source: "r1", sourceHandle: "dataframe", target: "r2", targetHandle: "dataframe" },
      { id: "er1-r3", source: "r1", sourceHandle: "dataframe", target: "r3", targetHandle: "dataframe" },
    ],
  },
}

// ── Custom ReactFlow node component ───────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  Sources: "#2b6cb0",
  Transforms: "#276749",
  Modeling: "#6b46c1",
  Evaluation: "#c05621",
  Utilities: "#4a5568",
  Unknown: "#718096",
}

// ── Run status badge ───────────────────────────────────────────────────────

function RunStatusBadge({ status }: { status?: string }) {
  if (!status) return null
  if (status === "running") {
    return (
      <Box position="absolute" top="4px" right="4px" zIndex={1}>
        <Spinner size="xs" color="yellow.400" speed="0.7s" />
      </Box>
    )
  }
  const cfg: Record<string, { icon: string; color: string }> = {
    done:     { icon: "✓", color: "green.500" },
    success:  { icon: "✓", color: "green.500" },
    cached:   { icon: "◷", color: "purple.400" },
    error:    { icon: "✕", color: "red.500" },
    pending:  { icon: "·", color: "gray.400" },
    bypassed: { icon: "⊘", color: "gray.400" },
  }
  const c = cfg[status] ?? { icon: "·", color: "gray.400" }
  return (
    <Tooltip label={status} placement="top" hasArrow>
      <Box
        position="absolute"
        top="4px"
        right="4px"
        w="16px"
        h="16px"
        borderRadius="full"
        display="flex"
        alignItems="center"
        justifyContent="center"
        zIndex={1}
        cursor="default"
      >
        <Text fontSize="10px" fontWeight="bold" color={c.color} lineHeight={1}>
          {c.icon}
        </Text>
      </Box>
    </Tooltip>
  )
}

// ── Param label with optional description tooltip (6.4) ────────────────────

function ParamLabel({ label, description }: { label: string; description?: string }) {
  if (!description) {
    return <FormLabel fontSize="xs" mb={1}>{label}</FormLabel>
  }
  return (
    <FormLabel fontSize="xs" mb={1}>
      <Tooltip label={description} placement="top" hasArrow>
        <Text as="span" cursor="help" borderBottom="1px dashed" borderColor="gray.400">
          {label}
        </Text>
      </Tooltip>
    </FormLabel>
  )
}

function GraphNodeComponent({ id, data, selected }: NodeProps<GraphFlowNode>) {
  const { nodeInfo, runStatus, label, bypassed } = data
  const headerColor = CATEGORY_COLORS[nodeInfo.category] ?? CATEGORY_COLORS.Unknown
  const [editing, setEditing] = useState(false)
  const [editVal, setEditVal] = useState("")

  function startEdit() {
    setEditVal(String(label ?? nodeInfo.display_name))
    setEditing(true)
  }

  function commitEdit(e: React.KeyboardEvent | React.FocusEvent) {
    if ("key" in e && e.key === "Escape") {
      setEditing(false)
      return
    }
    // Dispatch a custom event so GraphPage can hear it without prop drilling
    const evt = new CustomEvent("graph:rename-node", {
      detail: { nodeId: (e.target as HTMLElement).closest("[data-nodeid]")?.getAttribute("data-nodeid"), label: editVal },
      bubbles: true,
    })
      ; (e.target as HTMLElement).dispatchEvent(evt)
    setEditing(false)
  }

  return (
    <>
      <NodeResizer
        minWidth={160}
        minHeight={70}
        isVisible={!!selected}
        lineStyle={{ borderColor: "#63b3ed", borderWidth: 1 }}
        handleStyle={{ width: 8, height: 8, borderRadius: "50%", background: "#63b3ed" }}
      />
      <Box
        bg="white"
        border={selected ? "2px solid #63b3ed" : bypassed ? "2px dashed #a0aec0" : "1px solid #cbd5e0"}
        borderRadius="md"
        boxShadow={selected ? "0 0 0 3px rgba(99,179,237,0.4)" : "sm"}
        w="100%"
        h="100%"
        minW="160px"
        overflow="hidden"
        fontSize="sm"
        position="relative"
        data-nodeid={id}
        opacity={bypassed ? 0.45 : 1}
        transition="opacity 0.15s"
      >
        <RunStatusBadge status={runStatus} />
      {/* Renders an input handle for each slot on the left edge */}
      {nodeInfo.inputs.map((slot, i) => (
        <Handle
          key={`in-${slot}`}
          type="target"
          position={Position.Left}
          id={slot}
          style={{ top: 40 + i * 22, background: headerColor, width: 14, height: 14, border: "2px solid white" }}
          title={slot}
        />
      ))}

      <Box bg={headerColor} px={3} py={1} onDoubleClick={startEdit} cursor="default">
        {editing ? (
          <Input
            size="xs"
            autoFocus
            value={editVal}
            onChange={(e) => setEditVal(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === "Enter") commitEdit(e) }}
            bg="whiteAlpha.900"
            color="gray.800"
            border="none"
            px={0}
            h="auto"
          />
        ) : (
          <Text color="white" fontWeight="bold" fontSize="xs" noOfLines={1} title="Double-click to rename">
            {String(label ?? nodeInfo.display_name)}
          </Text>
        )}
      </Box>
      <Box px={3} py={2}>
        <Text fontSize="xs" color="gray.500">{nodeInfo.category}</Text>
        {Object.entries(data.params as Record<string, unknown>).slice(0, 3).map(([k, v]) => (
          <Tooltip key={k} label={`${k}: ${String(v)}`} placement="right" hasArrow openDelay={400}>
            <Text fontSize="xs" noOfLines={1} color="gray.700">
              <b>{k}:</b> {String(v)}
            </Text>
          </Tooltip>
        ))}
      </Box>

      {/* Source handle for each output on the right edge */}
      {nodeInfo.outputs.map((slot, i) => (
        <Handle
          key={`out-${slot}`}
          type="source"
          position={Position.Right}
          id={slot}
          style={{ top: 40 + i * 22, background: headerColor, width: 14, height: 14, border: "2px solid white" }}
          title={slot}
        />
      ))}
    </Box>
    </>
  )
}

const nodeTypes = { graphNode: GraphNodeComponent }

// ── Custom deletable edge ─────────────────────────────────────────────────

function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  markerEnd,
  style,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })
  const { setEdges } = useReactFlow()

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: selected ? "#63b3ed" : "#b0bec5",
          strokeWidth: selected ? 2.5 : 1.5,
        }}
      />
      <EdgeLabelRenderer>
        <Box
          position="absolute"
          transform={`translate(-50%, -50%) translate(${labelX}px,${labelY}px)`}
          pointerEvents="all"
          opacity={selected ? 1 : 0}
          transition="opacity 0.15s"
          className="nodrag nopan"
        >
          <IconButton
            aria-label="Delete edge"
            icon={<Text fontSize="sm" lineHeight={1}>×</Text>}
            size="xs"
            colorScheme="red"
            borderRadius="full"
            w="18px"
            h="18px"
            minW="18px"
            onClick={() => setEdges((eds) => eds.filter((e) => e.id !== id))}
          />
        </Box>
      </EdgeLabelRenderer>
    </>
  )
}

const edgeTypes = { default: DeletableEdge }

// ── Palette ────────────────────────────────────────────────────────────────

function NodePalette({ nodeList }: { nodeList: NodeInfo[] }) {
  const [search, setSearch] = useState("")

  const filtered = search.trim()
    ? nodeList.filter(
      (n) =>
        n.display_name.toLowerCase().includes(search.toLowerCase()) ||
        n.description.toLowerCase().includes(search.toLowerCase()),
    )
    : nodeList

  const grouped = filtered.reduce<Record<string, NodeInfo[]>>((acc, n) => {
    ; (acc[n.category] ??= []).push(n)
    return acc
  }, {})

  function handleDragStart(e: React.DragEvent, nodeInfo: NodeInfo) {
    e.dataTransfer.setData("application/graphnode", JSON.stringify(nodeInfo))
    e.dataTransfer.effectAllowed = "move"
  }

  return (
    <Box flex={1} bg="white" overflowY="auto" p={2}>
      <Text fontWeight="bold" fontSize="sm" mb={2} color="gray.700">Node Library</Text>
      <Input
        size="xs"
        placeholder="Search nodes…"
        mb={2}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {Object.keys(grouped).length === 0 && (
        <Text fontSize="xs" color="gray.400">No nodes match.</Text>
      )}
      {Object.entries(grouped).map(([category, nodes]) => (
        <Box key={category} mb={3}>
          <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" mb={1}>
            {category}
          </Text>
          {nodes.map((n) => (
            <Box
              key={n.node_id}
              draggable
              onDragStart={(e) => handleDragStart(e, n)}
              p={2}
              mb={1}
              bg="gray.50"
              borderRadius="md"
              border="1px solid"
              borderColor="gray.200"
              cursor="grab"
              _hover={{ bg: "blue.50", borderColor: "blue.300" }}
              fontSize="xs"
            >
              <Text fontWeight="medium">{n.display_name}</Text>
              {n.description && (
                <Text color="gray.500" noOfLines={1}>{n.description}</Text>
              )}
            </Box>
          ))}
        </Box>
      ))}
    </Box>
  )
}

// ── Inspector ──────────────────────────────────────────────────────────────
// Renders a typed form for each property defined in the node's JSON Schema.

/** File upload button for file_path fields — uploads to the server, returns path. */
function FilePathUpload({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const toast = useToast()

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append("file", file)
      const r = await axios.post("/api/v1/graphs/upload", form, { headers: { "Content-Type": "multipart/form-data" } })
      onChange(r.data.path)
    } catch {
      toast({ title: "Upload failed", status: "error", duration: 3000 })
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  return (
    <Flex gap={1}>
      <input ref={fileRef} type="file" style={{ display: "none" }} onChange={handleFile} />
      <Input size="sm" value={value} onChange={(e) => onChange(e.target.value)} placeholder="/app/data/sample.csv" flex={1} />
      <Tooltip label="Upload a file">
        <IconButton
          aria-label="Upload file"
          icon={<Text fontSize="sm">↑</Text>}
          size="sm"
          isLoading={uploading}
          onClick={() => fileRef.current?.click()}
        />
      </Tooltip>
    </Flex>
  )
}

/** Dynamic filter form for database_source — fetches columns and renders per-column inputs. */
function DatasourceFilterForm({
  datasourceKey,
  filtersJson,
  onChange,
}: {
  datasourceKey: string
  filtersJson: string
  onChange: (json: string) => void
}) {
  const { data: info, isLoading } = useQuery<DatasourceInfo>({
    queryKey: ["datasource-info", datasourceKey],
    queryFn: () => axios.get(`/api/v1/graphs/datasource-info/${datasourceKey}`).then((r) => r.data),
    enabled: !!datasourceKey,
  })

  let filters: Record<string, string> = {}
  try { filters = JSON.parse(filtersJson || "{}") } catch { /* ignore */ }

  function update(col: string, val: string) {
    const next = { ...filters }
    if (val) { next[col] = val } else { delete next[col] }
    onChange(JSON.stringify(next))
  }

  if (!datasourceKey) return <Text fontSize="xs" color="gray.400">Select a datasource first.</Text>
  if (isLoading) return <Spinner size="xs" />

  const filterable = info?.query_params ?? []

  return (
    <Stack spacing={2}>
      <Text fontSize="xs" fontWeight="semibold" color="gray.500">Filters (optional)</Text>
      {filterable.map((col) => (
        <FormControl key={col} size="sm">
          <FormLabel fontSize="xs">{col}</FormLabel>
          <Input
            size="sm"
            placeholder={`filter by ${col}`}
            value={filters[col] ?? ""}
            onChange={(e) => update(col, e.target.value)}
          />
        </FormControl>
      ))}
      {filterable.length === 0 && (
        <Text fontSize="xs" color="gray.400">No filterable columns.</Text>
      )}
    </Stack>
  )
}

function DatasourceKeySelect({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const { data: keys = [] } = useQuery<string[]>({
    queryKey: ["datasource-keys"],
    queryFn: () => axios.get("/api/v1/graphs/datasource-keys").then((r) => r.data),
  })
  return (
    <Select size="sm" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">— select datasource —</option>
      {keys.map((k) => (
        <option key={k} value={k}>
          {k}
        </option>
      ))}
    </Select>
  )
}

// ── Column toggle selector ──────────────────────────────────────────────────
// Renders upstream dataframe columns as click-to-toggle buttons, with a
// freeform text input for adding column names not present in the run result.

function ColumnToggleSelect({
  value,
  availableColumns,
  onChange,
}: {
  value: string[]
  availableColumns: string[]
  onChange: (v: string[]) => void
}) {
  const [custom, setCustom] = useState("")
  const selectedSet = new Set(value)

  function toggle(col: string) {
    if (selectedSet.has(col)) onChange(value.filter((c) => c !== col))
    else onChange([...value, col])
  }

  function addCustom() {
    const col = custom.trim()
    if (!col) return
    if (!selectedSet.has(col)) onChange([...value, col])
    setCustom("")
  }

  // Items that are selected but not in the known column list
  const extras = value.filter((c) => !availableColumns.includes(c))

  return (
    <Box>
      {availableColumns.length > 0 ? (
        <Wrap spacing={1} mb={2}>
          {availableColumns.map((col) => (
            <WrapItem key={col}>
              <Button
                size="xs"
                colorScheme={selectedSet.has(col) ? "blue" : "gray"}
                variant={selectedSet.has(col) ? "solid" : "outline"}
                onClick={() => toggle(col)}
                fontWeight={selectedSet.has(col) ? "semibold" : "normal"}
              >
                {col}
              </Button>
            </WrapItem>
          ))}
        </Wrap>
      ) : (
        <Text fontSize="2xs" color="gray.400" mb={1}>
          Run the graph to see available columns
        </Text>
      )}

      {/* Selected columns not present in the available list */}
      {extras.length > 0 && (
        <Wrap spacing={1} mb={2}>
          {extras.map((col) => (
            <WrapItem key={col}>
              <Badge
                colorScheme="blue"
                cursor="pointer"
                title="Click to remove"
                onClick={() => toggle(col)}
                fontSize="xs"
                px={2}
                py={0.5}
                borderRadius="md"
              >
                {col} ×
              </Badge>
            </WrapItem>
          ))}
        </Wrap>
      )}

      {/* Freeform entry */}
      <Flex gap={1} mt={1}>
        <Input
          size="xs"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault()
              addCustom()
            }
          }}
          placeholder="add column…"
          flex={1}
        />
        <IconButton
          aria-label="Add column"
          icon={<Text fontSize="xs" lineHeight={1}>+</Text>}
          size="xs"
          onClick={addCustom}
        />
      </Flex>
    </Box>
  )
}

// ── Single-column selector ───────────────────────────────────────────────────
// Dropdown populated from upstream columns; falls back to free text when no
// upstream run result is available yet.

function ColumnSingleSelect({
  value,
  availableColumns,
  onChange,
  placeholder,
}: {
  value: string
  availableColumns: string[]
  onChange: (v: string) => void
  placeholder?: string
}) {
  if (availableColumns.length === 0) {
    return (
      <Input
        size="sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "column name"}
      />
    )
  }
  return (
    <Select
      size="sm"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {value && !availableColumns.includes(value) && (
        <option value={value}>{value}</option>
      )}
      <option value="">— select column —</option>
      {availableColumns.map((col) => (
        <option key={col} value={col}>{col}</option>
      ))}
    </Select>
  )
}

function NodeInspector({
  node,
  runResult,
  onChange,
  allEdges,
}: {
  node: GraphFlowNode | null
  runResult?: RunResult | undefined
  onChange: (nodeId: string, params: Record<string, unknown>) => void
  allEdges: Edge[]
}) {
  if (!node) {
    return (
      <Box w="220px" bg="white" borderLeft="1px solid" borderColor="gray.200" p={3}>
        <Text fontSize="sm" color="gray.400">Select a node to edit its parameters.</Text>
      </Box>
    )
  }

  const { nodeInfo, params } = node.data
  const schema = nodeInfo.params_schema
  const properties = schema?.properties ?? {}
  const currentNode = node

  // Collect columns from all upstream nodes' dataframe outputs in the last run
  const availableColumns: string[] = []
  if (runResult?.result) {
    const upstreamIds = allEdges.filter((e) => e.target === node.id).map((e) => e.source)
    for (const upId of upstreamIds) {
      const outputs = runResult.result[upId]
      if (!outputs || typeof outputs !== "object") continue
      for (const slot of Object.values(outputs as Record<string, unknown>)) {
        if (slot && typeof slot === "object" && (slot as Record<string, unknown>).__type__ === "dataframe") {
          const cols = (slot as Record<string, unknown>).columns
          if (Array.isArray(cols)) {
            for (const col of cols) {
              if (typeof col === "string" && !availableColumns.includes(col)) availableColumns.push(col)
            }
          }
        }
      }
    }
  }

  function update(key: string, value: unknown) {
    onChange(currentNode.id, { ...(params as Record<string, unknown>), [key]: value })
  }

  return (
    <Box w="220px" bg="white" borderLeft="1px solid" borderColor="gray.200" p={3} overflowY="auto">
      <Text fontWeight="bold" fontSize="sm" mb={1}>{nodeInfo.display_name}</Text>
      <Text fontSize="xs" color="gray.500" mb={3}>{nodeInfo.description}</Text>

      <Stack spacing={3}>
        {Object.entries(properties).map(([key, prop]) => {
          const value = (params as Record<string, unknown>)[key]
          const label = prop.title ?? key

          // file_path → text + upload button
          if (key === "file_path") {
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <FilePathUpload
                  value={String(value ?? prop.default ?? "")}
                  onChange={(v) => update(key, v)}
                />
              </FormControl>
            )
          }

          // filters_json → rendered as dynamic filter form (database_source only)
          if (key === "filters_json") {
            const dsKey = String((params as Record<string, unknown>).datasource_key ?? "")
            return (
              <Box key={key}>
                <DatasourceFilterForm
                  datasourceKey={dsKey}
                  filtersJson={String(value ?? "{}")}
                  onChange={(v) => update(key, v)}
                />
              </Box>
            )
          }

          // Single-column string fields → column selector
          const isColumnKey = key === "column" || key.endsWith("_column")
          if (prop.type === "string" && isColumnKey) {
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <ColumnSingleSelect
                  value={String(value ?? prop.default ?? "")}
                  availableColumns={availableColumns}
                  onChange={(v) => update(key, v)}
                  placeholder={prop.description}
                />
              </FormControl>
            )
          }

          // datasource_key → dynamically populated select
          if (key === "datasource_key") {
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <DatasourceKeySelect
                  value={String(value ?? "")}
                  onChange={(v) => update(key, v)}
                />
              </FormControl>
            )
          }

          // Enum → Select dropdown
          if (prop.enum) {
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <Select
                  size="sm"
                  value={String(value ?? prop.default ?? "")}
                  onChange={(e) => update(key, e.target.value)}
                >
                  {prop.enum.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </Select>
              </FormControl>
            )
          }

          // Boolean → Switch
          if (prop.type === "boolean") {
            return (
              <FormControl key={key} display="flex" alignItems="center" size="sm">
                <FormLabel fontSize="xs" mb={0} mr={2}>
                  {prop.description ? (
                    <Tooltip label={prop.description} placement="top" hasArrow>
                      <Text as="span" cursor="help" borderBottom="1px dashed" borderColor="gray.400">{label}</Text>
                    </Tooltip>
                  ) : label}
                </FormLabel>
                <Switch
                  size="sm"
                  isChecked={Boolean(value ?? prop.default)}
                  onChange={(e) => update(key, e.target.checked)}
                />
              </FormControl>
            )
          }

          // Number/integer → number input
          if (prop.type === "integer" || prop.type === "number") {
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <Input
                  size="sm"
                  type="number"
                  value={String(value ?? prop.default ?? "")}
                  onChange={(e) => update(key, prop.type === "integer" ? parseInt(e.target.value) : parseFloat(e.target.value))}
                />
              </FormControl>
            )
          }

          // Array of strings → column toggle selector
          if (prop.type === "array" && (prop.items?.type === "string" || !prop.items?.type)) {
            const arrVal: string[] = Array.isArray(value)
              ? (value as unknown[]).map(String)
              : Array.isArray(prop.default)
                ? (prop.default as unknown[]).map(String)
                : []
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <ColumnToggleSelect
                  value={arrVal}
                  availableColumns={availableColumns}
                  onChange={(v) => update(key, v)}
                />
              </FormControl>
            )
          }

          // Array of non-strings → comma-separated fallback
          if (prop.type === "array") {
            const arrVal = Array.isArray(value)
              ? (value as unknown[]).join(", ")
              : Array.isArray(prop.default)
                ? (prop.default as unknown[]).join(", ")
                : String(value ?? "")
            return (
              <FormControl key={key} size="sm">
                <ParamLabel label={label} description={prop.description} />
                <Input
                  size="sm"
                  value={arrVal}
                  onChange={(e) =>
                    update(
                      key,
                      e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter((s) => s.length > 0),
                    )
                  }
                  placeholder="comma-separated values"
                />
              </FormControl>
            )
          }

          // String or unknown → text input
          return (
            <FormControl key={key} size="sm">
              <ParamLabel label={label} description={prop.description} />
              <Input
                size="sm"
                value={String(value ?? prop.default ?? "")}
                onChange={(e) => update(key, e.target.value)}
                placeholder={prop.description ?? ""}
              />
            </FormControl>
          )
        })}
      </Stack>

      {Object.keys(properties).length === 0 && (
        <Text fontSize="xs" color="gray.400">No parameters.</Text>
      )}

      <Box mt={4} pt={3} borderTop="1px solid" borderColor="gray.100">
        <Text fontSize="xs" color="gray.500" fontWeight="semibold" mb={1}>Inputs</Text>
        {nodeInfo.inputs.map((s) => <Badge key={s} mr={1} mb={1} colorScheme="blue" fontSize="xs">{s}</Badge>)}
        {nodeInfo.inputs.length === 0 && <Text fontSize="xs" color="gray.400">none</Text>}
        <Text fontSize="xs" color="gray.500" fontWeight="semibold" mt={2} mb={1}>Outputs</Text>
        {nodeInfo.outputs.map((s) => <Badge key={s} mr={1} mb={1} colorScheme="green" fontSize="xs">{s}</Badge>)}
        {nodeInfo.outputs.length === 0 && <Text fontSize="xs" color="gray.400">none</Text>}

        {!!(runResult?.result?.[node.id]) && (
          <Box mt={3} pt={3} borderTop="1px dashed" borderColor="gray.200">
            <Text fontSize="xs" color="gray.500" fontWeight="semibold" mb={2}>Last Run Output</Text>
            <RunResultView result={{ [node.id]: runResult.result[node.id] }} hideNodeId />
          </Box>
        )}
      </Box>
    </Box>
  )
}

// ── Execution Log pane ─────────────────────────────────────────────────────

function ExecutionLogPane({
  result,
  nodeStatuses,
  nodes,
}: {
  result: Record<string, unknown> | undefined
  nodeStatuses: Record<string, string> | undefined
  nodes: GraphFlowNode[]
}) {
  const timings = (result?.["_timings_"] ?? {}) as Record<string, number>
  const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]))

  // Show all nodes that have a status, preserving the graph order where possible
  const rows = nodes
    .filter((n) => nodeStatuses?.[n.id] !== undefined)
    .concat(
      // include any extra ids present in statuses that aren't in `nodes` (edge case)
      Object.keys(nodeStatuses ?? {})
        .filter((id) => !nodes.some((n) => n.id === id))
        .map((id) => ({ id, data: { nodeInfo: { display_name: id }, params: {}, runStatus: undefined } } as unknown as GraphFlowNode))
    )

  if (rows.length === 0) {
    return <Text fontSize="xs" color="gray.400" p={2}>No execution data yet.</Text>
  }

  return (
    <Box overflowX="auto">
      <Table size="xs" variant="simple">
        <Thead>
          <Tr>
            <Th fontSize="xs" p={2}>Node</Th>
            <Th fontSize="xs" p={2}>Status</Th>
            <Th fontSize="xs" p={2} isNumeric>Duration (s)</Th>
            <Th fontSize="xs" p={2}>Output</Th>
          </Tr>
        </Thead>
        <Tbody>
          {rows.map((node) => {
            const status = nodeStatuses?.[node.id]
            const duration = timings[node.id]
            const displayName =
              (nodeById[node.id]?.data as GraphNodeData | undefined)?.nodeInfo?.display_name ??
              node.id
            const label = (nodeById[node.id]?.data as GraphNodeData | undefined)?.label
            const nodeOutputs = result?.[node.id] as Record<string, unknown> | undefined

            // Build a short output summary
            let outputSummary = ""
            if (nodeOutputs && typeof nodeOutputs === "object") {
              outputSummary = Object.entries(nodeOutputs)
                .map(([slot, val]) => {
                  if (val && typeof val === "object") {
                    const t = (val as Record<string, unknown>).__type__
                    if (t === "dataframe") {
                      const df = val as { shape: number[] }
                      return `${slot}: ${df.shape?.[0]}×${df.shape?.[1]}`
                    }
                    if (t === "model") return `${slot}: model`
                    if (t === "figure") return `${slot}: chart`
                  }
                  return `${slot}: ${String(val).slice(0, 30)}`
                })
                .join(", ")
            }

            const isError = status?.startsWith("error:")
            const errorMsg = isError ? status?.replace(/^error:\s*/, "") : undefined

            return (
              <Tr key={node.id}>
                <Td fontSize="xs" p={2} maxW="160px">
                  <Text fontWeight="semibold" noOfLines={1} title={displayName}>
                    {label ? `${label}` : displayName}
                  </Text>
                  <Text fontSize="2xs" color="gray.400" noOfLines={1}>{node.id}</Text>
                </Td>
                <Td fontSize="xs" p={2}>
                  <RunStatusBadge status={status} />
                  {isError && errorMsg && (
                    <Tooltip label={errorMsg} fontSize="xs">
                      <Text fontSize="2xs" color="red.400" noOfLines={1} maxW="120px" cursor="help">
                        {errorMsg}
                      </Text>
                    </Tooltip>
                  )}
                </Td>
                <Td fontSize="xs" p={2} isNumeric color="gray.600">
                  {duration !== undefined ? duration.toFixed(3) : "—"}
                </Td>
                <Td fontSize="xs" p={2} color="gray.600" maxW="200px">
                  <Text noOfLines={1} title={outputSummary}>{outputSummary || "—"}</Text>
                </Td>
              </Tr>
            )
          })}
        </Tbody>
      </Table>
    </Box>
  )
}

// ── Results pane ───────────────────────────────────────────────────────────

function ResultsPane({
  runId,
  status,
  result,
  nodes,
}: {
  runId: string | null
  status: RunStatus | undefined
  result: RunResult | undefined
  nodes: GraphFlowNode[]
}) {
  if (!runId) return null

  const statusColor: Record<string, string> = {
    pending: "yellow", running: "blue", success: "green", done: "green", error: "red",
  }

  return (
    <Box bg="white" borderTop="1px solid" borderColor="gray.200" p={3} maxH="350px" overflowY="auto">
      <Flex align="center" gap={3} mb={2}>
        <Text fontWeight="bold" fontSize="sm">Run Results</Text>
        {status && (
          <Badge colorScheme={statusColor[status.status] ?? "gray"}>
            {status.status}
            {(status.status === "pending" || status.status === "running") && (
              <Spinner size="xs" ml={1} />
            )}
          </Badge>
        )}
        <Text fontSize="xs" color="gray.400">{runId}</Text>
      </Flex>

      {status?.error && (
        <Text color="red.500" fontSize="xs" mb={2}>{status.error}</Text>
      )}

      <Tabs size="sm" variant="soft-rounded" colorScheme="blue">
        <TabList mb={2}>
          <Tab fontSize="xs" py={1} px={3}>Log</Tab>
          <Tab fontSize="xs" py={1} px={3}>Outputs</Tab>
        </TabList>
        <TabPanels>
          <TabPanel p={0}>
            <ExecutionLogPane
              result={result?.result}
              nodeStatuses={status?.node_statuses}
              nodes={nodes}
            />
          </TabPanel>
          <TabPanel p={0}>
            {result?.result && <RunResultView result={result.result} />}
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  )
}

/** Paginated table for a preview rows array. */
function PreviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  const PAGE_SIZE = 10
  const [page, setPage] = useState(0)
  const total = rows.length
  const pageRows = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const cols = Object.keys(rows[0] ?? {})

  return (
    <Box overflowX="auto">
      <Table size="xs" variant="simple">
        <Thead>
          <Tr>
            {cols.map((col) => (
              <Th key={col} fontSize="xs" p={1}>{col}</Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          {pageRows.map((row, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: preview rows
            <Tr key={i}>
              {cols.map((col, j) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: preview cells
                <Td key={j} fontSize="xs" p={1}>{String(row[col] ?? "")}</Td>
              ))}
            </Tr>
          ))}
        </Tbody>
      </Table>
      {total > PAGE_SIZE && (
        <Flex align="center" gap={2} mt={1}>
          <Button size="xs" isDisabled={page === 0} onClick={() => setPage((p) => p - 1)}>‹</Button>
          <Text fontSize="xs" color="gray.500">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </Text>
          <Button size="xs" isDisabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)}>›</Button>
        </Flex>
      )}
    </Box>
  )
}

function RunResultView({ result, hideNodeId = false }: { result: Record<string, unknown>, hideNodeId?: boolean }) {
  // Track which (nodeId, slot) pairs have their preview expanded
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const toggle = (key: string) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))

  return (
    <Box>
      {Object.entries(result).map(([nodeId, outputs]) => {
        // Skip the internal timings key injected by the backend
        if (nodeId === "_timings_") return null
        const outs = outputs as Record<string, unknown>
        return (
          <Box key={nodeId} mb={3}>
            {!hideNodeId && <Text fontWeight="semibold" fontSize="xs" color="gray.600" mb={1}>{nodeId}</Text>}
            {Object.entries(outs).map(([slot, val]) => {
              const v = val as Record<string, unknown> | unknown
              if (v && typeof v === "object" && (v as Record<string, unknown>).__type__ === "dataframe") {
                const df = v as { shape: number[]; path: string; preview_rows?: Record<string, unknown>[]; columns?: string[] }
                const expandKey = `${nodeId}:${slot}`
                const isExpanded = !!expanded[expandKey]
                const hasPreview = Array.isArray(df.preview_rows) && df.preview_rows.length > 0
                return (
                  <Box key={slot} mb={1}>
                    <Flex align="center" gap={2} flexWrap="wrap">
                      <Text fontSize="xs" color="gray.700">
                        📊 <b>{slot}</b>: {df.shape?.[0]} rows × {df.shape?.[1]} cols
                      </Text>
                      {df.path && (
                        <a href={`/api/v1/graphs/artifacts/${df.path}`} download style={{ fontSize: '11px', color: '#3182ce', textDecoration: 'underline' }}>
                          Download
                        </a>
                      )}
                      {hasPreview && (
                        <Button size="xs" variant="ghost" colorScheme="blue" onClick={() => toggle(expandKey)}>
                          {isExpanded ? "▾ Hide preview" : `▸ Show preview (${df.preview_rows!.length} rows)`}
                        </Button>
                      )}
                    </Flex>
                    {hasPreview && (
                      <Collapse in={isExpanded} animateOpacity>
                        <Box mt={1}>
                          <PreviewTable rows={df.preview_rows!} />
                        </Box>
                      </Collapse>
                    )}
                  </Box>
                )
              }
              if (v && typeof v === "object" && (v as Record<string, unknown>).__type__ === "model") {
                const m = v as { path: string }
                return (
                  <Text key={slot} fontSize="xs" color="gray.700">
                    🤖 <b>{slot}</b>: Model saved at{" "}
                    <a href={`/api/v1/graphs/artifacts/${m.path}`} style={{ color: "#3182ce" }}>
                      {m.path}
                    </a>
                  </Text>
                )
              }
              if (v && typeof v === "object" && (v as Record<string, unknown>).__type__ === "figure") {
                const fig = v as { data: string; format?: string }
                const expandKey = `${nodeId}:${slot}`
                const isExpanded = !!expanded[expandKey]
                return (
                  <Box key={slot} mb={1}>
                    <Button size="xs" variant="ghost" colorScheme="purple" onClick={() => toggle(expandKey)}>
                      {isExpanded ? "▾ Hide chart" : "▸ Show chart"}
                    </Button>
                    <Collapse in={isExpanded} animateOpacity>
                      <Box mt={1} border="1px solid" borderColor="gray.200" borderRadius="md" overflow="hidden" maxW="100%">
                        <img
                          src={`data:image/${fig.format ?? "png"};base64,${fig.data}`}
                          alt={`${slot} chart`}
                          style={{ maxWidth: "100%", display: "block" }}
                        />
                      </Box>
                    </Collapse>
                  </Box>
                )
              }
              return (
                <Text key={slot} fontSize="xs">
                  <b>{slot}:</b> {JSON.stringify(v).slice(0, 120)}
                </Text>
              )
            })}
          </Box>
        )
      })}
    </Box>
  )
}

// ── Canvas with drag-drop ──────────────────────────────────────────────────
// useReactFlow requires a ReactFlowProvider ancestor. We wrap the canvas in
// ReactFlowProvider (in GraphPage) and put the drag-drop logic in this inner
// component so that screenToFlowPosition is available from the correct context.

function FlowWithDrop({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onPaneClick,
  onNodeDrop,
  onNodeDelete,
  onNodeDuplicate,
  onNodeBypass,
  selectedNodeId,
}: {
  nodes: GraphFlowNode[]
  edges: Edge[]
  onNodesChange: Parameters<typeof useNodesState>[0] extends never ? never : (changes: unknown) => void
  onEdgesChange: Parameters<typeof useEdgesState>[0] extends never ? never : (changes: unknown) => void
  onConnect: (c: Connection) => void
  onNodeClick: (id: string) => void
  onPaneClick: () => void
  onNodeDrop: (nodeInfo: NodeInfo, pos: { x: number; y: number }) => void
  onNodeDelete: (id: string) => void
  onNodeDuplicate: (id: string) => void
  onNodeBypass: (id: string) => void
  selectedNodeId: string | null
}) {
  const { screenToFlowPosition } = useReactFlow()
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)

  // Dismiss context menu on outside click
  useEffect(() => {
    if (!contextMenu) return
    const dismiss = () => setContextMenu(null)
    document.addEventListener("click", dismiss)
    return () => document.removeEventListener("click", dismiss)
  }, [contextMenu])

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const raw = e.dataTransfer.getData("application/graphnode")
    if (!raw) return
    const nodeInfo: NodeInfo = JSON.parse(raw)
    const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    onNodeDrop(nodeInfo, position)
  }

  return (
    <Box flex={1} position="relative" onDragOver={handleDragOver} onDrop={handleDrop}>
      {/* Empty-state overlay */}
      {nodes.length === 0 && (
        <Flex
          position="absolute"
          inset={0}
          align="center"
          justify="center"
          zIndex={1}
          pointerEvents="none"
        >
          <Box
            border="2px dashed"
            borderColor="gray.300"
            borderRadius="lg"
            p={8}
            textAlign="center"
            color="gray.400"
          >
            <Text fontSize="2xl" mb={2}>🧩</Text>
            <Text fontWeight="medium">Drag nodes from the palette to get started</Text>
            <Text fontSize="sm" mt={1}>Or load a template from the toolbar</Text>
            <Text fontSize="xs" mt={2} color="gray.300">Select nodes and press Delete or Backspace to remove them</Text>
          </Box>
        </Flex>
      )}

      <ReactFlow
        nodes={nodes.map((n) => ({ ...n, selected: n.id === selectedNodeId }))}
        edges={edges}
        onNodesChange={onNodesChange as never}
        onEdgesChange={onEdgesChange as never}
        onConnect={onConnect}
        onNodeClick={(_, node) => { onNodeClick(node.id); setContextMenu(null) }}
        onPaneClick={() => { onPaneClick(); setContextMenu(null) }}
        onNodeContextMenu={(e, node) => {
          e.preventDefault()
          setContextMenu({ x: e.clientX, y: e.clientY, nodeId: node.id })
        }}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        deleteKeyCode={["Delete", "Backspace"]}
      >
        <Background />
        <Controls />
        <MiniMap nodeColor={(n) => CATEGORY_COLORS[(n.data as GraphNodeData).nodeInfo?.category] ?? "#718096"} />
      </ReactFlow>

      {/* Right-click context menu */}
      {contextMenu && (
        <Box
          position="fixed"
          left={contextMenu.x}
          top={contextMenu.y}
          bg="white"
          border="1px solid"
          borderColor="gray.200"
          borderRadius="md"
          boxShadow="md"
          zIndex={1000}
          p={1}
          minW="150px"
          onClick={(e) => e.stopPropagation()}
        >
          <Box
            px={3}
            py={1.5}
            cursor="pointer"
            borderRadius="sm"
            fontSize="sm"
            _hover={{ bg: "blue.50" }}
            onClick={() => {
              onNodeDuplicate(contextMenu.nodeId)
              setContextMenu(null)
            }}
          >
            📋 Duplicate
          </Box>
          <Box
            px={3}
            py={1.5}
            cursor="pointer"
            borderRadius="sm"
            fontSize="sm"
            _hover={{ bg: "yellow.50" }}
            onClick={() => {
              onNodeBypass(contextMenu.nodeId)
              setContextMenu(null)
            }}
          >
            ⊘ {nodes.find((n) => n.id === contextMenu.nodeId)?.data.bypassed ? "Un-bypass" : "Bypass"}
          </Box>
          <Divider />
          <Box
            px={3}
            py={1.5}
            cursor="pointer"
            borderRadius="sm"
            fontSize="sm"
            color="red.500"
            _hover={{ bg: "red.50" }}
            onClick={() => {
              onNodeDelete(contextMenu.nodeId)
              setContextMenu(null)
            }}
          >
            🗑 Delete
          </Box>
        </Box>
      )}
    </Box>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────

let nodeCounter = 100

/** Dagre-based auto-layout. direction: "LR" = left-to-right, "TB" = top-to-bottom. */
function layoutNodes(
  nodes: GraphFlowNode[],
  edges: Edge[],
  direction: "LR" | "TB",
): GraphFlowNode[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  const isLR = direction === "LR"
  g.setGraph({ rankdir: direction, ranksep: isLR ? 80 : 60, nodesep: isLR ? 30 : 20 })
  for (const n of nodes) {
    g.setNode(n.id, { width: n.width ?? 200, height: n.height ?? 80 })
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target)
  }
  dagre.layout(g)
  return nodes.map((n) => {
    const pos = g.node(n.id)
    return {
      ...n,
      position: {
        x: pos.x - (n.width ?? 200) / 2,
        y: pos.y - (n.height ?? 80) / 2,
      },
    }
  })
}

/** Grid layout: arranges all nodes in a compact grid regardless of connectivity. */
function gridLayout(nodes: GraphFlowNode[]): GraphFlowNode[] {
  const cols = Math.max(1, Math.ceil(Math.sqrt(nodes.length)))
  return nodes.map((n, i) => ({
    ...n,
    position: { x: (i % cols) * 230 + 40, y: Math.floor(i / cols) * 110 + 40 },
  }))
}

function GraphPage() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const importRef = useRef<HTMLInputElement>(null)
  const clipboardRef = useRef<GraphFlowNode | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphFlowNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [currentWorkflowId, setCurrentWorkflowId] = useState<number | null>(null)
  const [saveWorkflowName, setSaveWorkflowName] = useState("")

  // ── Collapsible panel state (persisted to localStorage) ──
  const [leftOpen, setLeftOpen] = useState<boolean>(() => localStorage.getItem("graph:leftOpen") !== "false")
  const [rightOpen, setRightOpen] = useState<boolean>(() => localStorage.getItem("graph:rightOpen") !== "false")
  const [bottomOpen, setBottomOpen] = useState<boolean>(() => localStorage.getItem("graph:bottomOpen") !== "false")
  useEffect(() => { localStorage.setItem("graph:leftOpen", String(leftOpen)) }, [leftOpen])
  useEffect(() => { localStorage.setItem("graph:rightOpen", String(rightOpen)) }, [rightOpen])
  useEffect(() => { localStorage.setItem("graph:bottomOpen", String(bottomOpen)) }, [bottomOpen])

  const { data: nodeList = [], isLoading: nodesLoading } = useQuery<NodeInfo[]>({
    queryKey: ["graph-nodes"],
    queryFn: () => axios.get("/api/v1/graphs/nodes").then((r) => r.data.data ?? r.data),
  })

  // ── Saved workflows list ──

  const { data: savedWorkflows = [], refetch: refetchWorkflows } = useQuery<WorkflowSummary[]>({
    queryKey: ["saved-workflows"],
    queryFn: () => axios.get("/api/v1/graphs/workflows").then((r) => r.data),
  })

  const saveWorkflowMutation = useMutation({
    mutationFn: (body: { id: number | null; name: string; spec: string }) =>
      body.id
        ? axios.put(`/api/v1/graphs/workflows/${body.id}`, { name: body.name, graph_spec: body.spec }).then((r) => r.data)
        : axios.post("/api/v1/graphs/workflows", { name: body.name, graph_spec: body.spec }).then((r) => r.data),
    onSuccess: (data: WorkflowDetail) => {
      setCurrentWorkflowId(data.id)
      setSaveWorkflowName(data.name)
      refetchWorkflows()
      toast({ title: `Workflow "${data.name}" saved`, status: "success", duration: 2000 })
    },
    onError: () => toast({ title: "Save failed", status: "error", duration: 3000 }),
  })

  const deleteWorkflowMutation = useMutation({
    mutationFn: (id: number) => axios.delete(`/api/v1/graphs/workflows/${id}`),
    onSuccess: () => { refetchWorkflows(); toast({ title: "Workflow deleted", status: "info", duration: 2000 }) },
  })

  function handleSaveWorkflow() {
    if (!saveWorkflowName.trim()) {
      toast({ title: "Enter a workflow name", status: "warning", duration: 2000 })
      return
    }
    const spec = JSON.stringify({ nodes, edges })
    saveWorkflowMutation.mutate({ id: currentWorkflowId, name: saveWorkflowName.trim(), spec })
  }

  function handleLoadWorkflow(wf: WorkflowSummary) {
    axios.get(`/api/v1/graphs/workflows/${wf.id}`).then((r) => {
      try {
        const { nodes: n, edges: eg } = JSON.parse(r.data.graph_spec)
        setNodes(n ?? [])
        setEdges(eg ?? [])
        setSelectedNodeId(null)
        setRunId(null)
        setCurrentWorkflowId(wf.id)
        setSaveWorkflowName(wf.name)
        toast({ title: `Loaded "${wf.name}"`, status: "info", duration: 2000 })
      } catch {
        toast({ title: "Failed to load workflow", status: "error", duration: 3000 })
      }
    })
  }

  // ── Poll run status (lifted from ResultsPane so we can update node dots) ──

  const { data: runStatus } = useQuery<RunStatus>({
    queryKey: ["graph-status", runId],
    queryFn: () => axios.get(`/api/v1/graphs/${runId}/status`).then((r) => r.data),
    enabled: !!runId,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === "pending" || s === "running" ? 1500 : false
    },
  })

  const { data: runResult } = useQuery<RunResult>({
    queryKey: ["graph-result", runId],
    queryFn: () => axios.get(`/api/v1/graphs/${runId}/result`).then((r) => r.data),
    // Backend uses status="success"; keep "done" as alias for legacy cache entries.
    enabled: runStatus?.status === "success" || runStatus?.status === ("done" as string),
  })

  // Sync per-node status dots onto canvas nodes
  useEffect(() => {
    if (!runStatus?.node_statuses) return
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, runStatus: runStatus.node_statuses?.[n.id] },
      })),
    )
  }, [runStatus?.node_statuses, setNodes])

  // ── SSE live progress ──
  // Opens an EventSource against /stream when a run starts.  Events feed
  // directly into the TanStack Query cache so all consumers of runStatus get
  // sub-second node-level updates without touching any other code paths.
  // Polling on runStatus stays as a fallback if the SSE connection drops.
  useEffect(() => {
    if (!runId) return
    const es = new EventSource(`/api/v1/graphs/${runId}/stream`)

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as {
          type: string
          status?: string
          node_statuses?: Record<string, string>
          error?: string | null
        }
        if (data.type === "status" && data.status) {
          queryClient.setQueryData<RunStatus>(["graph-status", runId], (old) => ({
            // Preserve everything from the last HTTP poll (timestamps, etc.)
            ...(old ?? { run_id: runId }),
            status: data.status as RunStatus["status"],
            node_statuses: data.node_statuses,
            error: data.error ?? undefined,
          }))
          if (data.status === "success") {
            // Trigger the result query (enabled guard checks status === "done";
            // manually invalidate so it fires immediately on SSE completion).
            queryClient.invalidateQueries({ queryKey: ["graph-result", runId] })
          }
        }
        if (data.type === "done") es.close()
      } catch { /* skip malformed events */ }
    }

    es.onerror = () => es.close()
    return () => es.close()
  }, [runId, queryClient])

  // ── Keyboard copy-paste ──

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "c" && selectedNodeId) {
        const node = nodes.find((n) => n.id === selectedNodeId)
        if (node) clipboardRef.current = node
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "v" && clipboardRef.current) {
        const src = clipboardRef.current
        const newId = `node-${++nodeCounter}`
        setNodes((prev) => [
          ...prev,
          { ...src, id: newId, position: { x: src.position.x + 40, y: src.position.y + 40 }, data: { ...src.data, runStatus: undefined } },
        ])
        setSelectedNodeId(newId)
      }
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [selectedNodeId, nodes, setNodes])

  // ── Node rename from custom event ──

  useEffect(() => {
    function handleRename(e: Event) {
      const { nodeId, label } = (e as CustomEvent<{ nodeId: string; label: string }>).detail
      if (!nodeId) return
      setNodes((prev) => prev.map((n) => n.id === nodeId ? { ...n, data: { ...n.data, label } } : n))
    }
    document.addEventListener("graph:rename-node", handleRename)
    return () => document.removeEventListener("graph:rename-node", handleRename)
  }, [setNodes])

  // ── Validate ──

  const validateMutation = useMutation({
    mutationFn: (spec: object) => axios.post("/api/v1/graphs/validate", spec).then((r) => r.data),
    onSuccess: (data) => toast({ title: data.valid ? "Graph is valid ✓" : "Validation failed", status: data.valid ? "success" : "warning", duration: 3000 }),
    onError: (e: unknown) => toast({ title: "Validation error", description: String(e), status: "error", duration: 4000 }),
  })

  // ── Run ──

  const runMutation = useMutation({
    mutationFn: (spec: object) => axios.post("/api/v1/graphs/run", spec).then((r) => r.data),
    onSuccess: (data) => {
      setRunId(data.run_id)
      // Clear stale status/result for the new run
      queryClient.removeQueries({ queryKey: ["graph-status", data.run_id] })
      queryClient.removeQueries({ queryKey: ["graph-result", data.run_id] })
      toast({ title: "Graph submitted", description: `Run ID: ${data.run_id}`, status: "info", duration: 3000 })
    },
    onError: (e: unknown) => toast({ title: "Run failed", description: String(e), status: "error", duration: 4000 }),
  })

  // ── Build graph spec from canvas state ──
  // Field names must match the Pydantic models on the backend:
  //   NodeInstance: instance_id, node_type, params
  //   Edge: source_instance_id, source_slot, target_instance_id, target_slot

  function buildSpec() {
    return {
      nodes: nodes.map((n) => ({
        instance_id: n.id,
        node_type: n.data.nodeInfo.node_id,
        params: n.data.params,
        bypassed: n.data.bypassed ?? false,
      })),
      edges: edges.map((e) => ({
        source_instance_id: e.source,
        source_slot: e.sourceHandle ?? "df",
        target_instance_id: e.target,
        target_slot: e.targetHandle ?? "df",
      })),
    }
  }

  // ── Node param updates from inspector ──

  function handleParamChange(nodeId: string, newParams: Record<string, unknown>) {
    setNodes((prev) =>
      prev.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, params: newParams } }
          : n,
      ),
    )
  }

  // ── Drag-drop from palette ──

  function handleNodeDrop(nodeInfo: NodeInfo, position: { x: number; y: number }) {
    const id = `node-${++nodeCounter}`
    const defaultParams = Object.fromEntries(
      Object.entries(nodeInfo.params_schema?.properties ?? {}).map(([k, prop]) => [k, prop.default ?? ""]),
    )
    const newNode: GraphFlowNode = {
      id,
      type: "graphNode",
      position,
      data: { nodeInfo, params: defaultParams },
    }
    setNodes((prev) => [...prev, newNode])
    setSelectedNodeId(id)
  }

  // ── Delete a node and its connected edges ──

  function handleNodeDelete(id: string) {
    setNodes((prev) => prev.filter((n) => n.id !== id))
    setEdges((prev) => prev.filter((e) => e.source !== id && e.target !== id))
    if (selectedNodeId === id) setSelectedNodeId(null)
  }

  // ── Duplicate a node ──

  function handleNodeDuplicate(id: string) {
    const src = nodes.find((n) => n.id === id)
    if (!src) return
    const newId = `node-${++nodeCounter}`
    setNodes((prev) => [
      ...prev,
      {
        ...src,
        id: newId,
        position: { x: src.position.x + 30, y: src.position.y + 30 },
        data: { ...src.data, runStatus: undefined },
      },
    ])
    setSelectedNodeId(newId)
  }

  // ── Bypass / un-bypass a node ──

  function handleNodeBypass(id: string) {
    setNodes((prev) =>
      prev.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, bypassed: !n.data.bypassed } } : n,
      ),
    )
  }

  // ── Edge connect ──

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  )

  // ── Load template ──

  function loadTemplate(name: string) {
    const tpl = TEMPLATES[name]
    if (!tpl) return
    setNodes(tpl.nodes)
    setEdges(tpl.edges)
    setSelectedNodeId(null)
    setRunId(null)
    setCurrentWorkflowId(null)
    setSaveWorkflowName("")
  }

  // ── Auto-layout (LR, TB, or compact grid) ──

  function handleAutoLayout(dir: "LR" | "TB" | "grid") {
    setNodes((prev) =>
      dir === "grid" ? gridLayout(prev) : layoutNodes(prev, edges, dir),
    )
  }

  // ── Clear canvas ──

  function handleClearCanvas() {
    if (nodes.length === 0) return
    if (!window.confirm("Clear all nodes and edges?")) return
    setNodes([])
    setEdges([])
    setSelectedNodeId(null)
    setRunId(null)
  }

  // ── Export graph JSON ──

  function handleExport() {
    const payload = { nodes, edges }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "graph.json"
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Import graph JSON ──

  function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const { nodes: n, edges: eg } = JSON.parse(ev.target?.result as string)
        setNodes(n ?? [])
        setEdges(eg ?? [])
        setSelectedNodeId(null)
        setRunId(null)
      } catch {
        toast({ title: "Import failed", description: "Invalid JSON file", status: "error", duration: 3000 })
      }
    }
    reader.readAsText(file)
    // Reset so the same file can be re-imported
    e.target.value = ""
  }

  // ── Keep nodeList in sync with existing nodes (reload info when palette loads) ──

  useEffect(() => {
    if (!nodeList.length) return
    setNodes((prev) =>
      prev.map((n) => {
        const info = nodeList.find((ni) => ni.node_id === n.data.nodeInfo.node_id)
        if (!info) return n
        return { ...n, data: { ...n.data, nodeInfo: info } }
      }),
    )
  }, [nodeList, setNodes])

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null

  return (
    <Box flex={1} display="flex" flexDir="column" overflow="hidden">
      {/* Hidden file input for JSON import */}
      <input ref={importRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleImport} />

      {/* Toolbar */}
      <Flex
        px={4}
        py={2}
        bg="white"
        borderBottom="1px solid"
        borderColor="gray.200"
        align="center"
        gap={2}
        flexWrap="wrap"
      >
        <Heading size="sm" color="green.700">🔗 Graph Editor</Heading>

        <Button
          size="sm"
          variant="outline"
          onClick={() => validateMutation.mutate(buildSpec())}
          isLoading={validateMutation.isPending}
        >
          Validate
        </Button>
        <Button
          size="sm"
          colorScheme="green"
          onClick={() => runMutation.mutate(buildSpec())}
          isLoading={runMutation.isPending}
          isDisabled={nodes.length === 0}
        >
          ▶ Run
        </Button>

        <Divider orientation="vertical" h="24px" />

        <Button
          size="sm"
          colorScheme="red"
          variant="ghost"
          isDisabled={!selectedNodeId}
          onClick={() => selectedNodeId && handleNodeDelete(selectedNodeId)}
        >
          🗑 Delete
        </Button>
        <Button
          size="sm"
          variant="ghost"
          isDisabled={nodes.length === 0}
          onClick={handleClearCanvas}
        >
          Clear
        </Button>
        <Menu>
          <MenuButton
            as={Button}
            size="sm"
            variant="ghost"
            isDisabled={nodes.length === 0}
          >
            ⚙ Layout ▾
          </MenuButton>
          <MenuList minW="140px">
            <MenuItem fontSize="sm" onClick={() => handleAutoLayout("LR")}>→ Left to Right</MenuItem>
            <MenuItem fontSize="sm" onClick={() => handleAutoLayout("TB")}>↓ Top to Bottom</MenuItem>
            <MenuItem fontSize="sm" onClick={() => handleAutoLayout("grid")}>⊞ Compact Grid</MenuItem>
          </MenuList>
        </Menu>

        <Divider orientation="vertical" h="24px" />

        {/* Save Workflow */}
        <Popover placement="bottom-start">
          <PopoverTrigger>
            <Button size="sm" colorScheme="blue" variant="ghost" isDisabled={nodes.length === 0}>
              💾 Save
              {currentWorkflowId && <Badge ml={1} colorScheme="blue" fontSize="2xs">saved</Badge>}
            </Button>
          </PopoverTrigger>
          <PopoverContent w="220px">
            <PopoverArrow />
            <PopoverBody>
              <Text fontSize="xs" fontWeight="semibold" mb={2}>
                {currentWorkflowId ? "Update workflow" : "Save as new workflow"}
              </Text>
              <Input
                size="sm"
                placeholder="Workflow name…"
                value={saveWorkflowName}
                onChange={(e) => setSaveWorkflowName(e.target.value)}
                mb={2}
              />
              <Button
                size="sm"
                colorScheme="blue"
                w="full"
                isLoading={saveWorkflowMutation.isPending}
                onClick={handleSaveWorkflow}
              >
                {currentWorkflowId ? "Update" : "Save"}
              </Button>
              {currentWorkflowId && (
                <Button size="sm" variant="ghost" w="full" mt={1} onClick={() => { setCurrentWorkflowId(null); setSaveWorkflowName("") }}>
                  Save as new
                </Button>
              )}
            </PopoverBody>
          </PopoverContent>
        </Popover>

        {/* Workflows library */}
        <Menu>
          <MenuButton as={Button} size="sm" variant="ghost">
            📂 Workflows {savedWorkflows.length > 0 && <Badge ml={1} colorScheme="gray">{savedWorkflows.length}</Badge>}
          </MenuButton>
          <MenuList maxH="300px" overflowY="auto">
            {savedWorkflows.length === 0 && (
              <MenuItem isDisabled fontSize="sm">No saved workflows</MenuItem>
            )}
            {savedWorkflows.map((wf) => (
              <MenuItem key={wf.id} fontSize="sm" closeOnSelect={false}>
                <Flex align="center" w="full" gap={2}>
                  <Text flex={1} noOfLines={1}>{wf.name}</Text>
                  <Button size="xs" colorScheme="blue" variant="ghost" onClick={() => handleLoadWorkflow(wf)}>Load</Button>
                  <IconButton
                    aria-label="Delete workflow"
                    icon={<Text fontSize="xs">🗑</Text>}
                    size="xs"
                    colorScheme="red"
                    variant="ghost"
                    onClick={(e) => { e.stopPropagation(); deleteWorkflowMutation.mutate(wf.id) }}
                  />
                </Flex>
              </MenuItem>
            ))}
          </MenuList>
        </Menu>

        <Divider orientation="vertical" h="24px" />

        <Menu>
          <MenuButton as={Button} size="sm" variant="ghost">
            Templates ▾
          </MenuButton>
          <MenuList>
            {Object.keys(TEMPLATES).map((name) => (
              <MenuItem key={name} onClick={() => loadTemplate(name)} fontSize="sm">
                {name}
              </MenuItem>
            ))}
          </MenuList>
        </Menu>

        <Button size="sm" variant="ghost" onClick={handleExport} isDisabled={nodes.length === 0}>
          ↓ Export
        </Button>
        <Button size="sm" variant="ghost" onClick={() => importRef.current?.click()}>
          ↑ Import
        </Button>

        <Tooltip
          label={
            <Box fontSize="xs">
              <Text fontWeight="bold" mb={1}>Keyboard shortcuts</Text>
              <Text>Delete / Backspace — remove selected node</Text>
              <Text>Ctrl+C / Ctrl+V — copy / paste selected node</Text>
              <Text>Double-click node title — rename</Text>
              <Text>Drag from palette — add node</Text>
              <Text>Right-click node — context menu</Text>
            </Box>
          }
          placement="bottom-end"
          hasArrow
        >
          <IconButton aria-label="Keyboard shortcuts" icon={<Text>⌨</Text>} size="sm" variant="ghost" />
        </Tooltip>

        <Flex ml="auto" align="center" gap={2}>
          {currentWorkflowId && (
            <Text fontSize="xs" color="blue.500" fontStyle="italic">{saveWorkflowName}</Text>
          )}
          <Text fontSize="xs" color="gray.400">
            {nodes.length} nodes · {edges.length} edges
          </Text>
          {nodesLoading && <Spinner size="sm" />}
        </Flex>
      </Flex>

      {/* Main area */}
      <Flex flex={1} overflow="hidden" minH={0}>
        {nodesLoading ? (
          <Flex align="center" justify="center" flex={1}>
            <Spinner />
          </Flex>
        ) : (
          <>
            {/* Left panel: collapsible node library */}
            {leftOpen ? (
              <Box
                w="200px"
                flexShrink={0}
                bg="white"
                borderRight="1px solid"
                borderColor="gray.200"
                overflow="visible"
                position="relative"
                display="flex"
                flexDir="column"
              >
                <NodePalette nodeList={nodeList} />
                <Box
                  position="absolute"
                  right="-10px"
                  top="50%"
                  transform="translateY(-50%)"
                  bg="white"
                  border="1px solid"
                  borderColor="gray.300"
                  borderRadius="full"
                  w="20px"
                  h="20px"
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                  cursor="pointer"
                  zIndex={10}
                  boxShadow="sm"
                  onClick={() => setLeftOpen(false)}
                  title="Collapse node library"
                  fontSize="sm"
                  color="gray.500"
                  _hover={{ bg: "gray.100" }}
                  userSelect="none"
                >
                  ‹
                </Box>
              </Box>
            ) : (
              <Box
                w="22px"
                flexShrink={0}
                bg="white"
                borderRight="1px solid"
                borderColor="gray.200"
                cursor="pointer"
                display="flex"
                alignItems="center"
                justifyContent="center"
                onClick={() => setLeftOpen(true)}
                title="Expand node library"
                _hover={{ bg: "blue.50" }}
              >
                <Text
                  fontSize="10px"
                  color="gray.400"
                  sx={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
                  userSelect="none"
                >
                  LIBRARY
                </Text>
              </Box>
            )}

            {/* Canvas */}
            <ReactFlowProvider>
              <FlowWithDrop
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange as never}
                onEdgesChange={onEdgesChange as never}
                onConnect={onConnect}
                onNodeClick={setSelectedNodeId}
                onPaneClick={() => setSelectedNodeId(null)}
                onNodeDrop={handleNodeDrop}
                onNodeDelete={handleNodeDelete}
                onNodeDuplicate={handleNodeDuplicate}
                onNodeBypass={handleNodeBypass}
                selectedNodeId={selectedNodeId}
              />
            </ReactFlowProvider>

            {/* Right panel: collapsible node inspector */}
            {rightOpen ? (
              <Box
                flexShrink={0}
                bg="white"
                borderRight="1px solid"
                borderColor="gray.300"
                overflow="visible"
                position="relative"
                display="flex"
                flexDir="column"
              >
              {/* </Box><Box position="relative" flexShrink={0}> */}
                <Box
                  position="absolute"
                  left="-10px"
                  top="50%"
                  transform="translateY(-50%)"
                  bg="white"
                  border="1px solid"
                  borderColor="gray.300"
                  borderRadius="full"
                  w="20px"
                  h="20px"
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                  cursor="pointer"
                  zIndex={10}
                  boxShadow="sm"
                  onClick={() => setRightOpen(false)}
                  title="Collapse inspector"
                  fontSize="sm"
                  color="gray.500"
                  _hover={{ bg: "gray.100" }}
                  userSelect="none"
                >
                  ›
                </Box>
                <NodeInspector node={selectedNode} runResult={runResult} onChange={handleParamChange} allEdges={edges} />
              </Box>
            ) : (
              <Box
                w="22px"
                flexShrink={0}
                bg="white"
                borderLeft="1px solid"
                borderColor="gray.200"
                cursor="pointer"
                display="flex"
                alignItems="center"
                justifyContent="center"
                onClick={() => setRightOpen(true)}
                title="Expand inspector"
                _hover={{ bg: "blue.50" }}
              >
                <Text
                  fontSize="10px"
                  color="gray.400"
                  sx={{ writingMode: "vertical-rl" }}
                  userSelect="none"
                >
                  INSPECTOR
                </Text>
              </Box>
            )}
          </>
        )}
      </Flex>

      {/* Bottom: collapsible results panel */}
      {bottomOpen ? (
        <Box borderTop="1px solid" borderColor="gray.200" flexShrink={0}>
          <Flex
            bg="gray.50"
            px={3}
            py={1}
            align="center"
            borderBottom="1px solid"
            borderColor="gray.200"
            cursor="pointer"
            _hover={{ bg: "gray.100" }}
            onClick={() => setBottomOpen(false)}
            userSelect="none"
          >
            <Text fontSize="xs" fontWeight="semibold" color="gray.600" flex={1}>
              ▾ Run Output
            </Text>
            <Text fontSize="xs" color="gray.400">Click to collapse</Text>
          </Flex>
          <ResultsPane runId={runId} status={runStatus} result={runResult} nodes={nodes} />
        </Box>
      ) : (
        <Box
          borderTop="1px solid"
          borderColor="gray.200"
          bg="gray.50"
          px={3}
          py={1}
          cursor="pointer"
          _hover={{ bg: "gray.100" }}
          onClick={() => setBottomOpen(true)}
          userSelect="none"
          flexShrink={0}
        >
          <Flex align="center" gap={2}>
            <Text fontSize="xs" fontWeight="semibold" color="gray.600">▸ Run Output</Text>
            {runStatus && (
              <Badge
                colorScheme={
                  runStatus.status === "success" ? "green" :
                  runStatus.status === "error" ? "red" :
                  runStatus.status === "running" ? "blue" : "yellow"
                }
                fontSize="2xs"
              >
                {runStatus.status}
              </Badge>
            )}
            {!runId && <Text fontSize="xs" color="gray.400">No run yet</Text>}
          </Flex>
        </Box>
      )}
    </Box>
  )
}
