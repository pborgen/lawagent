import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "./client";
import type { Project, ProjectList } from "./types";

const KEY = ["projects"];

export function useProjects() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => (await apiFetch<ProjectList>("/projects")).items,
  });
}

export type CreateProjectArgs = {
  name: string;
  description?: string;
  matter_type?: string;
};

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: CreateProjectArgs) =>
      apiFetch<Project>("/projects", { method: "POST", body: args }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/projects/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
