import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

export const csvFilterTemplate: GraphTemplate = {
  nodes: [
    {
      id: "n1",
      type: "graphNode",
      position: { x: 50, y: 150 },
      data: {
        nodeInfo: {
          node_id: "csv_source",
          display_name: "CSV Source",
          category: "Sources",
          endpoint: "",
          description: "Load CSV",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: {
            properties: {
              file_path: {
                type: "string",
                title: "File Path",
                default: "/app/data/sample.csv",
              },
              separator: { type: "string", title: "Separator", default: "," },
              encoding: { type: "string", title: "Encoding", default: "utf-8" },
            },
            required: ["file_path"],
          },
        },
        params: { file_path: "/app/data/sample.csv", separator: ",", encoding: "utf-8" },
      },
    } satisfies GraphFlowNode,
    {
      id: "n2",
      type: "graphNode",
      position: { x: 320, y: 150 },
      data: {
        nodeInfo: {
          node_id: "filter",
          display_name: "Filter",
          category: "Transforms",
          endpoint: "",
          description: "Filter rows where a column satisfies a condition.",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: {
            properties: {
              column: { type: "string", title: "Column" },
              operator: {
                type: "string",
                title: "Operator",
                enum: ["==", "!=", ">", "<", ">=", "<="],
              },
              value: { type: "string", title: "Value" },
            },
            required: ["column", "operator", "value"],
          },
        },
        params: { column: "year", operator: ">", value: "2010" },
      },
    } satisfies GraphFlowNode,
  ],
  edges: [
    {
      id: "e-n1-n2",
      source: "n1",
      sourceHandle: "dataframe",
      target: "n2",
      targetHandle: "dataframe",
    } satisfies Edge,
  ],
}
