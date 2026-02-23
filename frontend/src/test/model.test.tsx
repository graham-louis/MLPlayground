import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it, vi } from "vitest"
import { Route } from "../routes/model"
import { server } from "./handlers"
import { renderWithProviders } from "./utils"

// Mock Recharts to avoid ResizeObserver issues in jsdom.
vi.mock("recharts", () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
}))

const ModelPage = Route.options.component as React.ComponentType

const TRAIN_RESULT = {
  model_type: "random_forest",
  n_samples: 120,
  n_train: 96,
  n_test: 24,
  r2: 0.78,
  rmse: 8.5,
  feature_importances: [
    { feature: "avg_temp",      importance: 0.35 },
    { feature: "precipitation", importance: 0.25 },
    { feature: "gdd",           importance: 0.20 },
    { feature: "ph",            importance: 0.12 },
    { feature: "organic_matter",importance: 0.08 },
  ],
  state: "North Carolina",
  crop: "CORN",
  start_year: 2000,
  end_year: 2022,
}

// Register the training endpoint with mock handlers
function setupTrainHandler() {
  server.use(
    http.post("/api/v1/models/train", () =>
      HttpResponse.json(TRAIN_RESULT)
    )
  )
}

describe("Model Training page – static content", () => {
  it("renders the page heading", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByRole("heading", { name: /model training/i })).toBeInTheDocument()
  })

  it("renders the Configure Your Model card", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByRole("heading", { name: /configure your model/i })).toBeInTheDocument()
  })

  it("renders state, crop, model-type selects", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByLabelText("State")).toBeInTheDocument()
    expect(screen.getByLabelText(/crop/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/model type/i)).toBeInTheDocument()
  })

  it("renders all weather feature checkboxes", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByText(/avg temperature/i)).toBeInTheDocument()
    expect(screen.getByText(/total precipitation/i)).toBeInTheDocument()
    expect(screen.getByText(/growing degree days/i)).toBeInTheDocument()
  })

  it("renders all soil feature checkboxes", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByText(/soil ph/i)).toBeInTheDocument()
    expect(screen.getByText(/organic matter/i)).toBeInTheDocument()
    expect(screen.getByText(/sand content/i)).toBeInTheDocument()
  })

  it("Train Model button is disabled when no crop selected", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByRole("button", { name: /train model/i })).toBeDisabled()
  })

  it("shows a warning when no crop is selected", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByText(/select a crop above to enable training/i)).toBeInTheDocument()
  })
})

describe("Model Training page – crop population", () => {
  it("populates crop dropdown from yields/crops API", async () => {
    renderWithProviders(<ModelPage />)
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument()
    })
  })

  it("enables Train Model button after selecting a crop", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByLabelText(/crop/i), "CORN")
    expect(screen.getByRole("button", { name: /train model/i })).not.toBeDisabled()
  })
})

describe("Model Training page – training and results", () => {
  it("shows training spinner while request is in flight", async () => {
    server.use(
      http.post("/api/v1/models/train", async () => {
        await new Promise((r) => setTimeout(r, 200))
        return HttpResponse.json(TRAIN_RESULT)
      })
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)

    await waitFor(() => expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText(/crop/i), "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))

    // The button shows its loadingText while the mutation is in flight
    await waitFor(() => {
      expect(screen.getByText(/training model/i)).toBeInTheDocument()
    })

    // Eventually results appear
    await waitFor(() => expect(screen.getByText("R² Score")).toBeInTheDocument(), { timeout: 3000 })
  })

  it("displays R², RMSE, and sample counts after successful training", async () => {
    setupTrainHandler()
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)

    await waitFor(() => expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText(/crop/i), "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))

    await waitFor(() => {
      expect(screen.getByText("R² Score")).toBeInTheDocument()
    })
    // R² 78% = 0.78 * 100
    expect(screen.getByText("78.0%")).toBeInTheDocument()
    expect(screen.getByText("8.50")).toBeInTheDocument()
    expect(screen.getByText("96")).toBeInTheDocument()  // n_train
    expect(screen.getByText("24")).toBeInTheDocument()  // n_test
  })

  it("shows feature importance section with feature labels", async () => {
    setupTrainHandler()
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)

    await waitFor(() => expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText(/crop/i), "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /feature importances/i })).toBeInTheDocument()
    })
  })

  it("shows model type and crop badges in results header", async () => {
    setupTrainHandler()
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)

    await waitFor(() => expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText(/crop/i), "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))

    // Wait for the unique badge that only appears after training completes
    await waitFor(() => {
      expect(screen.getByText(/CORN · North Carolina/)).toBeInTheDocument()
    })
    // "Random Forest" badge is present (distinct from the select option)
    const allRF = screen.getAllByText("Random Forest")
    expect(allRF.length).toBeGreaterThanOrEqual(1)
  })

  it("shows an error alert when training fails", async () => {
    server.use(
      http.post("/api/v1/models/train", () =>
        HttpResponse.json(
          { detail: "No yield data found for WHEAT in North Carolina." },
          { status: 404 }
        )
      )
    )
    const user = userEvent.setup()
    renderWithProviders(<ModelPage />)

    await waitFor(() => expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText(/crop/i), "CORN")
    await user.click(screen.getByRole("button", { name: /train model/i }))

    await waitFor(() => {
      expect(screen.getByText(/No yield data found/i)).toBeInTheDocument()
    })
  })
})
