import "@testing-library/jest-dom"
import { configure } from "@testing-library/react"
import { server } from "./handlers"

// Extend waitFor timeout to 3 s for slower CI environments.
configure({ asyncUtilTimeout: 3000 })

// @zag-js/focus-visible (used by Chakra UI Checkbox) tries to overwrite
// HTMLElement.prototype.focus at mount time. jsdom defines it as getter-only,
// causing "Cannot set property focus … has only a getter". Make it writable.
const _origFocus = HTMLElement.prototype.focus
Object.defineProperty(HTMLElement.prototype, "focus", {
  configurable: true,
  writable: true,
  value: _origFocus,
})

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
