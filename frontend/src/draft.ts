export type UserEntryKind = "question" | "message";

export interface EntryDraft {
  content: string;
  kind: UserEntryKind;
  kindOverridden: boolean;
}

export const emptyDraft: EntryDraft = {
  content: "",
  kind: "message",
  kindOverridden: false,
};

export function updateDraftContent(draft: EntryDraft, content: string): EntryDraft {
  if (content === "") return emptyDraft;
  if (draft.kindOverridden) return { ...draft, content };
  return {
    content,
    kind: content.includes("?") ? "question" : "message",
    kindOverridden: false,
  };
}

export function overrideDraftKind(draft: EntryDraft, kind: UserEntryKind): EntryDraft {
  return { ...draft, kind, kindOverridden: true };
}
