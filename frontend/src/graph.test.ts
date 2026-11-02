import { describe, expect, it } from "vitest";
import { layoutGraph, nodeText, type GraphSnapshot } from "./graph.ts";

const graph: GraphSnapshot = {
  entries: [
    {
      id: "root",
      author: "user",
      kind: "question",
      content: "How should this work?",
      label: null,
    },
    {
      id: "child",
      author: "agent",
      kind: "message",
      content: "A detailed answer",
      label: "Answer",
    },
  ],
  edges: [{ parent_id: "root", child_id: "child" }],
};

describe("browser graph projection", () => {
  it("lays children below their parents and preserves their edge", () => {
    const result = layoutGraph(graph);
    const root = result.nodes.find((node) => node.id === "root");
    const child = result.nodes.find((node) => node.id === "child");

    expect(root).toBeDefined();
    expect(child).toBeDefined();
    expect(child!.position.y).toBeGreaterThan(root!.position.y);
    expect(result.edges).toEqual([
      expect.objectContaining({ source: "root", target: "child" }),
    ]);
  });

  it("prefers a label and bounds unlabeled content", () => {
    expect(nodeText(graph.entries[1]!)).toBe("Answer");
    expect(
      nodeText({ ...graph.entries[0]!, content: "x".repeat(121) }),
    ).toBe(`${"x".repeat(119)}…`);
  });
});
