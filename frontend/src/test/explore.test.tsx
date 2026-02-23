import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { Route } from "../routes/explore"
import { YIELDS_RESPONSE, server } from "./handlers"
import { renderWithProviders } from "./utils"

// Extract the page component registered with the TanStack Router route
const ExplorePage = Route.options.component as React.ComponentType

describe("Data Explorer – filter UI", () => {
  it("renders filter controls", () => {
    renderWithProviders(<ExplorePage />)
    expect(screen.getByText("Data Explorer")).toBeInTheDocument()
    expect(screen.getByLabelText("State")).toBeInTheDocument()
    expect(screen.getByLabelText("Crop")).toBeInTheDocument()
    expect(screen.getByLabelText("Start Year")).toBeInTheDocument()
    expect(screen.getByLabelText("End Year")).toBeInTheDocument()
    expect(screen.getByLabelText("Data Type")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /load data/i })).toBeInTheDocument()
  })

  it("pre-selects North Carolina and shows crop dropdown options", async () => {
    renderWithProviders(<ExplorePage />)
    const stateSelect = screen.getByLabelText("State") as HTMLSelectElement
    expect(stateSelect.value).toBe("North Carolina")

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "CORN" })).toBeInTheDocument()
    })
  })

  it("allows changing state and year range", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)

    const stateSelect = screen.getByLabelText("State")
    await user.selectOptions(stateSelect, "Iowa")
    expect((stateSelect as HTMLSelectElement).value).toBe("Iowa")

    const startInput = screen.getByLabelText("Start Year") as HTMLInputElement
    await user.clear(startInput)
    await user.type(startInput, "2015")
    expect(startInput.value).toBe("2015")
  })
})

describe("Data Explorer – loading data", () => {
  it("shows results table after clicking Load Data", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)

    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByText(`(${YIELDS_RESPONSE.count} records)`)).toBeInTheDocument()
    })

    // Column headers from first row keys
    const expectedColumns = Object.keys(YIELDS_RESPONSE.data[0])
    for (const col of expectedColumns) {
      expect(screen.getAllByRole("columnheader").some((th) => th.textContent === col)).toBe(true)
    }

    // Data rows are rendered (two rows both have county "Wake")
    expect(screen.getAllByText("Wake").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("CORN").length).toBeGreaterThanOrEqual(1)
  })

  it("shows a loading spinner while fetching", async () => {
    // Delay the response so we can catch the spinner
    server.use(
      http.get("/api/v1/yields/", async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json(YIELDS_RESPONSE)
      })
    )

    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await user.click(screen.getByRole("button", { name: /load data/i }))

    // Chakra Spinner renders a visually-hidden span with text "Loading..."
    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    // Eventually resolves and spinner disappears
    await waitFor(() =>
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    )
  })

  it("shows empty state alert when API returns no data", async () => {
    server.use(
      http.get("/api/v1/yields/", () =>
        HttpResponse.json({ data: [], count: 0 })
      )
    )

    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByText("No data found")).toBeInTheDocument()
    })

    // Ingest button is present when status is idle
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })
  })

  it("shows an ingestion-running banner when ingest status is running", async () => {
    server.use(
      http.get("/api/v1/yields/", () => HttpResponse.json({ data: [], count: 0 })),
      http.get("/api/v1/ingest/status", () => HttpResponse.json({ status: "running" }))
    )

    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByText(/ingestion is running/i)).toBeInTheDocument()
    })
    // The Run button should NOT be visible when ingestion is running
    expect(screen.queryByRole("button", { name: /run data ingestion/i })).not.toBeInTheDocument()
  })

  it("triggers ingestion and shows loading state", async () => {
    server.use(
      http.get("/api/v1/yields/", () => HttpResponse.json({ data: [], count: 0 }))
    )

    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /run data ingestion/i }))

    // Mutation was called; after success the button re-appears (idle)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })
  })

  it("shows error alert when ingestion trigger fails (409 conflict)", async () => {
    server.use(
      http.get("/api/v1/yields/", () => HttpResponse.json({ data: [], count: 0 })),
      http.post("/api/v1/ingest/trigger", () =>
        HttpResponse.json({ detail: "Ingestion is already running." }, { status: 409 })
      )
    )

    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)
    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run data ingestion/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /run data ingestion/i }))

    await waitFor(() => {
      expect(screen.getByText(/ingestion is already running/i)).toBeInTheDocument()
    })
  })

  it("can switch to Weather data type and show weather results", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)

    const dataTypeSelect = screen.getByLabelText("Data Type")
    await user.selectOptions(dataTypeSelect, "weather")
    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByText("(1 records)")).toBeInTheDocument()
    })
    expect(screen.getByText("avg_temp")).toBeInTheDocument()
  })

  it("can switch to Soil data type and show soil results", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ExplorePage />)

    const dataTypeSelect = screen.getByLabelText("Data Type")
    await user.selectOptions(dataTypeSelect, "soil")
    await user.click(screen.getByRole("button", { name: /load data/i }))

    await waitFor(() => {
      expect(screen.getByText("(1 records)")).toBeInTheDocument()
    })
    expect(screen.getByText("ph")).toBeInTheDocument()
  })
})
