import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it, vi } from "vitest"
import { Route } from "../routes/explore"
import { YIELDS_RESPONSE, DAILY_WEATHER_RESPONSE, server } from "./handlers"
import { renderWithProviders } from "./utils"

// Mock recharts to avoid ResizeObserver issues in jsdom
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Line: () => null,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const ExplorePage = Route.options.component as React.ComponentType

describe("Data Explorer – filter UI", () => {
  it("renders heading and filter controls", () => {
    renderWithProviders(<ExplorePage />)
    expect(screen.getByText("Data Explorer")).toBeInTheDocument()
    expect(screen.getByLabelText("State")).toBeInTheDocument()
    expect(screen.getByLabelText("County")).toBeInTheDocument()
    expect(screen.getByLabelText("Start Year")).toBeInTheDocument()
    expect(screen.getByLabelText("End Year")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /load data/i })).toBeInTheDocument()
  })

  it("pre-selects North Carolina", () => {
    renderWithProviders(<ExplorePage />)
    const stateSelect = screen.getByLabelText("State") as HTMLSelectElement
    expect(stateSelect.value).toBe("North Carolina")
  })

  it("shows data-driven tabs from datasources API", async () => {
    renderWithProviders(<ExplorePage />)
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /crop yields/i })).toBeInTheDocument()
    })
    expect(screen.getByRole("tab", { name: /annual weather/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /soil properties/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /daily weather/i })).toBeInTheDocument()
  })

  it("allows changing state", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    const stateSelect = screen.getByLabelText("State")
    await user.selectOptions(stateSelect, "Iowa")
    expect((stateSelect as HTMLSelectElement).value).toBe("Iowa")
  })

  it("allows typing a county filter", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    const countyInput = screen.getByLabelText("County") as HTMLInputElement
    await user.type(countyInput, "Wake")
    expect(countyInput.value).toBe("Wake")
  })

  it("pre-selects North Carolina and shows crop dropdown options", async () => {
    renderWithProviders(<ExplorePage />)
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument()
    })
  })
})

describe("Data Explorer – loading data", () => {
  it("shows results table after clicking Load Data (yields tab)", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)

    // Wait for tabs to load from API
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /crop yields/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByText(/2 records/)).toBeInTheDocument()
    })

    expect(screen.getAllByText("Wake").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("CORN").length).toBeGreaterThanOrEqual(1)
  })

  it("shows a loading spinner while fetching", async () => {
    server.use(
      http.get("/api/v1/data/yields", async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json(YIELDS_RESPONSE)
      })
    )
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await waitFor(() => screen.getByRole("tab", { name: /crop yields/i }))
    await user.click(screen.getByRole("button", { name: /load data/i }))
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText(/loading/i)).not.toBeInTheDocument())
  })

  it("shows empty state alert when API returns no data", async () => {
    server.use(
      http.get("/api/v1/data/yields", () => HttpResponse.json({ data: [], count: 0 }))
    )
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await waitFor(() => screen.getByRole("tab", { name: /crop yields/i }))
    await user.click(screen.getByRole("button", { name: /load data/i }))
    await waitFor(() => {
      expect(screen.getByText(/no yields data found/i)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })
  })

  it("triggers ingestion when button is clicked", async () => {
    server.use(
      http.get("/api/v1/data/yields", () => HttpResponse.json({ data: [], count: 0 }))
    )
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await waitFor(() => screen.getByRole("tab", { name: /crop yields/i }))
    await user.click(screen.getByRole("button", { name: /load data/i }))
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole("button", { name: /run data ingestion/i }))
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })
  })

  it("can switch to Daily Weather tab and load daily weather data", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await waitFor(() => screen.getByRole("tab", { name: /daily weather/i }))
    await user.click(screen.getByRole("tab", { name: /daily weather/i }))
    await user.click(screen.getByRole("button", { name: /load data/i }))
    await waitFor(() => {
      expect(screen.getByText(/1 records/)).toBeInTheDocument()
    })
    expect(screen.getByRole("columnheader", { name: "tmax" })).toBeInTheDocument()
  })

  it("shows Ingest Daily Weather button when daily weather tab is empty", async () => {
    server.use(
      http.get("/api/v1/data/daily_weather", () => HttpResponse.json({ data: [], count: 0 }))
    )
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await waitFor(() => screen.getByRole("tab", { name: /daily weather/i }))
    await user.click(screen.getByRole("tab", { name: /daily weather/i }))
    await user.click(screen.getByRole("button", { name: /load data/i }))
    await waitFor(() => {
      expect(screen.getByText(/no daily weather data found/i)).toBeInTheDocument()
    })
    await waitFor(() => {
      const buttons = screen.getAllByRole("button", { name: /ingest daily weather/i })
      expect(buttons.length).toBeGreaterThanOrEqual(1)
    })
  })
})
