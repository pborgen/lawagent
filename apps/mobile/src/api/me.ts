import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type { Me } from "./types";

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/me"),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}
