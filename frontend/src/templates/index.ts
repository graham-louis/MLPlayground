/**
 * Template registry for the Graph Editor.
 *
 * Import this module in graph.tsx to get the TEMPLATES constant.
 * Add new templates by creating a file in this directory and exporting
 * them here.
 */
import type { GraphTemplate } from "../graphTypes"
import { csvFilterTemplate } from "./csvFilter"
import { yieldPredictionTemplate } from "./yieldPrediction"
import { noaaWeatherPlotTemplate } from "./noaaWeatherPlot"
import { pythonCodeTransformTemplate } from "./pythonCodeTransform"

export const TEMPLATES: Record<string, GraphTemplate> = {
  "CSV → Filter": csvFilterTemplate,
  "Yield Prediction (Weather + Soil)": yieldPredictionTemplate,
  "NOAA Weather → Plot": noaaWeatherPlotTemplate,
  "Python Code Transform": pythonCodeTransformTemplate,
}

export type { GraphTemplate }
