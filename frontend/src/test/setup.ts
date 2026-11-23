import "@testing-library/jest-dom/vitest";

// jsdom has no layout engine: give elements a width so width-dependent charts render.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
Element.prototype.getBoundingClientRect = function () {
  return { width: 640, height: 400, top: 0, left: 0, right: 640, bottom: 400, x: 0, y: 0, toJSON() {} };
};

// Vitest runs without globals, so Testing Library can't register its own cleanup.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(() => cleanup());
