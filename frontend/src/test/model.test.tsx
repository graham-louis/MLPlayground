import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Route } from "../routes/model"
import { renderWithProviders } from "./utils"

const ModelPage = Route.options.component as React.ComponentType

describe("Model Training page", () => {
  it("renders the page heading", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByRole("heading", { name: /model training/i })).toBeInTheDocument()
  })

  it("renders the AutoML Pipeline card heading", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByRole("heading", { name: /automl pipeline/i })).toBeInTheDocument()
  })

  it("shows supported model list description", () => {
    renderWithProviders(<ModelPage />)
    expect(
      screen.getByText(/linear regression, random forest, gradient boosting/i)
    ).toBeInTheDocument()
  })

  it("shows a warning that data must be loaded first", () => {
    renderWithProviders(<ModelPage />)
    expect(
      screen.getByText(/model training requires data to be loaded first/i)
    ).toBeInTheDocument()
  })

  it("prompts user to navigate to Data Explorer", () => {
    renderWithProviders(<ModelPage />)
    expect(screen.getByText(/navigate to data explorer to load data/i)).toBeInTheDocument()
  })
})
