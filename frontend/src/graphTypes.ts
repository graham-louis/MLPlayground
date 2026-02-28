/**
 * Shared type definitions for the Graph Editor.
 * Imported by graph.tsx and all template files.
 */
import type { Node, Edge } from "@xyflow/react"

export interface JsonSchemaProperty {
  type?: string
  title?: string
  description?: string
  default?: unknown
  enum?: string[]
  items?: { type: string }
  // Monaco widget fields (from json_schema_extra in Pydantic)
  ui_widget?: string
  language?: string
  [key: string]: unknown
}

export interface JsonSchema {
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
  title?: string
  type?: string
}

export interface NodeInfo {
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
export interface GraphNodeData {
  nodeInfo: NodeInfo
  params: Record<string, unknown>
  runStatus?: string
  label?: string        // user-provided custom name
  bypassed?: boolean
  [key: string]: unknown
}

export interface DatasourceColumn {
  name: string
  type_str: string
}

export interface ScopeParam {
  name: string
  type: string
  label?: string
  description?: string
  placeholder?: string
  default?: unknown
}

export interface DatasourceInfo {
  key: string
  columns: DatasourceColumn[]
  query_params: string[]
  scope_params: ScopeParam[]
}

export interface WorkflowSummary {
  id: number
  name: string
  description?: string
  created_at: string
  updated_at: string
}

export interface WorkflowDetail extends WorkflowSummary {
  graph_spec: string
}

export type GraphFlowNode = Node<GraphNodeData>

export interface RunStatus {
  run_id: string
  status: "pending" | "running" | "success" | "error"
  node_statuses?: Record<string, string>
  error?: string
  created_at?: string
  updated_at?: string
}

export interface ContextMenuState {
  x: number
  y: number
  nodeId: string
}

export interface RunResult {
  run_id: string
  status: string
  result?: Record<string, unknown>
}

export type GraphTemplate = { nodes: GraphFlowNode[]; edges: Edge[] }
