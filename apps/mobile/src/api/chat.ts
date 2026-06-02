import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type { ChatResponse, Mode } from "./types";

export type ChatArgs = {
  question: string;
  mode: Mode;
  projectId?: string;
};

// POST /chat — non-streaming; returns the full answer + sources at once.
// project_id is forwarded for usage attribution (the backend ignores it for
// retrieval today; answers are not project-scoped yet).
export function useChat() {
  return useMutation({
    mutationFn: ({ question, mode, projectId }: ChatArgs) =>
      apiFetch<ChatResponse>("/chat", {
        method: "POST",
        body: { question, mode, project_id: projectId },
      }),
  });
}
