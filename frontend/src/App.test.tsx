// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("loads and displays the graph", async () => {
    const graph = {
      version: 1,
      entries: [
        {
          id: "root",
          parent_id: null,
          author: "user",
          kind: "question",
          title: "Prototype question",
          content: "What should Histos do?",
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(graph), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe = vi.fn();
        unobserve = vi.fn();
        disconnect = vi.fn();
      },
    );

    render(<App />);

    expect((await screen.findAllByText("Prototype question")).length).toBeGreaterThan(0);
    expect(screen.getByText("What should Histos do?")).toBeInTheDocument();
  });
});
