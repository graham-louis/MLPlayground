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
import { ncCornYieldTemplate } from "./ncCornYield"
import { sarimaxyieldForecastTemplate } from "./sarimaxyieldForecast"
import { quickAnalysisTemplate } from "./quickAnalysis"

export const TEMPLATES: Record<string, GraphTemplate> = {
  "Quick Analysis (Start Here)": quickAnalysisTemplate,
  "CSV → Filter": csvFilterTemplate,
  "Yield Prediction (Weather + Soil)": yieldPredictionTemplate,
  "NC Corn Yield + Forecast (Final Goal)": ncCornYieldTemplate,
  "NC Corn Yield Forecast (SARIMAX + NOAA)": sarimaxyieldForecastTemplate,
  "NOAA Weather → Plot": noaaWeatherPlotTemplate,
  "Python Code Transform": pythonCodeTransformTemplate,
}

export type { GraphTemplate }
