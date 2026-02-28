import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

const plotSchema = {
  properties: {
    plot_type: {
      type: "string",
      title: "Plot Type",
      enum: ["scatter", "line", "histogram", "bar", "box"],
      default: "line",
    },
    x_column: { type: "string", title: "X Column", default: "" },
    y_column: { type: "string", title: "Y Column", default: "" },
    color_column: { type: "string", title: "Colour Column", default: "" },
    title: { type: "string", title: "Title", default: "" },
  },
}

export const noaaWeatherPlotTemplate: GraphTemplate = {
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
    } satisfies GraphFlowNode,
    {
      id: "r2",
      type: "graphNode",
      position: { x: 360, y: 60 },
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
          params_schema: plotSchema,
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
    } satisfies GraphFlowNode,
    {
      id: "r3",
      type: "graphNode",
      position: { x: 360, y: 280 },
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
          params_schema: plotSchema,
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
    } satisfies GraphFlowNode,
  ],
  edges: [
    {
      id: "er1-r2",
      source: "r1",
      sourceHandle: "dataframe",
      target: "r2",
      targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "er1-r3",
      source: "r1",
      sourceHandle: "dataframe",
      target: "r3",
      targetHandle: "dataframe",
    } satisfies Edge,
  ],
}
