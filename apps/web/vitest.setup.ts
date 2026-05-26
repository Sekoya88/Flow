import '@testing-library/jest-dom'

// jsdom lacks ResizeObserver — minimal noop polyfill so components that
// observe element sizes can mount in tests.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class NoopResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  globalThis.ResizeObserver = NoopResizeObserver
}
