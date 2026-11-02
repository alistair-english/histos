import { describe, expect, it } from "vitest";
import {
  emptyDraft,
  overrideDraftKind,
  updateDraftContent,
} from "./draft.ts";

describe("entry draft kind", () => {
  it("follows question marks until manually overridden", () => {
    const question = updateDraftContent(emptyDraft, "What now?");
    const message = updateDraftContent(question, "A statement");
    const overridden = overrideDraftKind(message, "question");

    expect(question.kind).toBe("question");
    expect(message.kind).toBe("message");
    expect(updateDraftContent(overridden, "Still a statement").kind).toBe("question");
  });

  it("clearing content resets a manual override", () => {
    const overridden = overrideDraftKind(emptyDraft, "question");
    const cleared = updateDraftContent(overridden, "");

    expect(cleared).toEqual(emptyDraft);
    expect(updateDraftContent(cleared, "A message").kind).toBe("message");
  });
});
