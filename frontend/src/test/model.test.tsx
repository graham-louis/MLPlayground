import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it, vi } from "vitest"
import { Route } from "../routes/model"
import { server, MODEL_TYPES_RESPONSE, MODEL_RUNS_RESPONSE } from "./handlers"
import { renderWithProviders } from "./utils"

// Mock recharts to avoid ResizeObserver issues in jsdom
vi.mock("recharts", () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const ModelPage = Route.options.component as React.ComponentType

const TRAIN_SUCCESS = {
  run_id: "uuid-abc-123",
  model_type: "random_forest",
  n_samples: 200,
  n_train: 160,
  n_test: 40,
  r2: 0.82,
  rmse: 11.5,
  feature_importances: [
    { feature: "avg_temp", importance: 0.45 },
    { feature: "precipitation", importance: 0.35 },
    { feature: "ph", importance: 0.20 },
  ],
  state: "North Carolina",
  crop: "CORN",
  start_year: 2000,
  end_year: 2022,
}

const PREDICT_SUCCESS = {
  predicted_yield: 135.7,
  model_type: "random_forest",
  training_r2: 0.82,
  training_rmse: 11.5,
  units: "bu/acre",
}

describe("Model page – structure", () => {
  it("renders heading and three tabs", async () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByText("Model Training")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /train & evaluate/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /predict yield/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /saved models/i })).toBeInTheDocument()
  })

  it("fetches model types from API (not hardcoded)", async () => {
    renderWithProviders(<ModelPage />)
    await waitFor(() => {
      expect(screen.getByRole("option", { name: /random forest/i })).toBeInTheDocument()
    })
    expect(screen.getByRole("option", { name: /gradient boosting/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /lstm/i })).toBeInTheDocument()
  })

  it("populates crop dropdown from yields/crops API", async () => {
    renderWithProviders(<ModelPage />)
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument()
    })
    expect(screen.getByRole("option", { name: "SOYBEANS" })).toBeInTheDocument()
  })

  it("enables Train Model button after selecting a crop", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelect = screen.getAllByRole("combobox").find(
      (s) => (s as HTMLSelectElement).value === "" && s.closest("[class*='card']")
    ) ?? screen.getAllByRole("combobox")[1]
    await user.selectOptions(cropSelect, "CORN")
    expect(screen.getByRole("button", { name: /train model/i })).not.toBeDisabled()
  })

  it("shows training spinner while request is in flight", async () => {
    server.use(
      http.post("/api/v1/models/train", async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json(TRAIN_SUCCESS)
      })
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelect = screen.getAllByRole("combobox").find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? screen.getAllByRole("combobox")[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))
    expect(screen.getByRole("button", { name: /training/i })).toBeInTheDocument()
  })

  it("displays R², RMSE, and sample counts after successful training", async () => {
    server.use(
      http.post("/api/v1/models/train", () => HttpResponse.json(TRAIN_SUCCESS))
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelects = screen.getAllByRole("combobox")
    const cropSelect = cropSelects.find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? cropSelects[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))
    await waitFor(() => {
      expect(screen.getByText("82.0%")).toBeInTheDocument()
    })
    expect(screen.getByText("11.50")).toBeInTheDocument()
    expect(screen.getByText("160")).toBeInTheDocument()
    expect(screen.getByText("40")).toBeInTheDocument()
  })

  it("shows feature importance section with feature labels", async () => {
    server.use(
      http.post("/api/v1/models/train", () => HttpResponse.json(TRAIN_SUCCESS))
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelects = screen.getAllByRole("combobox")
    const cropSelect = cropSelects.find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? cropSelects[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))
    await waitFor(() => {
      expect(screen.getByText(/feature importances/i)).toBeInTheDocument()
    })
  })

  it("shows run_id success alert when model is saved", async () => {
    server.use(
      http.post("/api/v1/models/train", () => HttpResponse.json(TRAIN_SUCCESS))
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelects = screen.getAllByRole("combobox")
    const cropSelect = cropSelects.find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? cropSelects[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))
    await waitFor(() => {
      expect(screen.getByText(/model saved/i)).toBeInTheDocument()
    })
  })

  it("shows model type and crop badges in results header", async () => {
    server.use(
      http.post("/api/v1/models/train", () => HttpResponse.json(TRAIN_SUCCESS))
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelects = screen.getAllByRole("combobox")
    const cropSelect = cropSelects.find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? cropSelects[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))
    await waitFor(() => {
      // Badge appears in results section after training
      const badges = screen.getAllByText("Random Forest")
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getByText(/CORN.*North Carolina/i)).toBeInTheDocument()
  })

  it("shows an error alert when training fails", async () => {
    server.use(
      http.post("/api/v1/models/train", () =>
        HttpResponse.json({ detail: "No yield data found." }, { status: 404 })
      )
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelects = screen.getAllByRole("combobox")
    const cropSelect = cropSelects.find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? cropSelects[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))
    await waitFor(() => {
      expect(screen.getByText(/no yield data found/i)).toBeInTheDocument()
    })
  })
})

describe("Model page – Predict tab", () => {
  it("shows predicted yield after submitting Predict tab", async () => {
    server.use(
      http.post("/api/v1/models/predict", () => HttpResponse.json(PREDICT_SUCCESS))
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await user.click(screen.getByRole("tab", { name: /predict yield/i }))
    await waitFor(() => screen.getByRole("option", { name: "CORN" }))
    const cropSelects = screen.getAllByRole("combobox")
    const cropSelect = cropSelects.find(
      (s) => (s as HTMLSelectElement).value === ""
    ) ?? cropSelects[1]
    await user.selectOptions(cropSelect, "CORN")
    await user.click(screen.getByRole("button", { name: /predict yield/i }))
    await waitFor(() => {
      expect(screen.getByText("135.7")).toBeInTheDocument()
    })
    expect(screen.getAllByText("bu/acre").length).toBeGreaterThanOrEqual(1)
  })
})

describe("Model page – Saved Models tab", () => {
  it("shows saved model runs table", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await user.click(screen.getByRole("tab", { name: /saved models/i }))
    await waitFor(() => {
      expect(screen.getByText("random_forest")).toBeInTheDocument()
    })
    expect(screen.getByText(/72.0%/)).toBeInTheDocument()
  })

  it("shows empty state when no saved models", async () => {
    server.use(
      http.get("/api/v1/models/", () => HttpResponse.json({ data: [], count: 0 }))
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)
    await user.click(screen.getByRole("tab", { name: /saved models/i }))
    await waitFor(() => {
      expect(screen.getByText(/no saved models yet/i)).toBeInTheDocument()
    })
  })
})
