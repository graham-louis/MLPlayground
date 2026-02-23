import { screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { Route } from "../routes/index"
import { server } from "./handlers"
import { renderWithProviders } from "./utils"

const HomePage = Route.options.component as React.ComponentType

describe("Home page", () => {
  it("renders the MLPlayground heading", () => {
    renderWithProviders(<HomePage />)
    // Chakra Heading renders as h2 by default; use getByText
    expect(screen.getByText("MLPlayground")).toBeInTheDocument()
  })

  it("shows a Connected API badge when health check succeeds", async () => {
    renderWithProviders(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText(/connected/i)).toBeInTheDocument()
    })
  })

  it("shows a Disconnected badge when health check fails", async () => {
    server.use(
      http.get("/api/v1/utils/health-check/", () =>
        HttpResponse.json({ detail: "Service Unavailable" }, { status: 503 })
      )
    )
    renderWithProviders(<HomePage />)
    // Initially shows disconnected before response
    await waitFor(() => {
      expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
    })
  })

  it("renders all three feature cards", () => {
    renderWithProviders(<HomePage />)
    expect(screen.getByText(/crop yields/i)).toBeInTheDocument()
    expect(screen.getByText(/climate data/i)).toBeInTheDocument()
    expect(screen.getByText(/soil properties/i)).toBeInTheDocument()
  })

  it("renders the About section with three principles", () => {
    renderWithProviders(<HomePage />)
    expect(screen.getByText(/researcher-centric/i)).toBeInTheDocument()
    expect(screen.getByText(/plug-and-play/i)).toBeInTheDocument()
    expect(screen.getByText(/transparent/i)).toBeInTheDocument()
  })
})
