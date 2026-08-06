"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, Project, fetchProjects } from "@/lib/api";

/**
 * Carrega a lista de empreendimentos com estados explícitos.
 *
 * Não existe estado "dado de exemplo": ou há dado do backend, ou há erro, ou
 * a lista está genuinamente vazia.
 */
export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchProjects();
      setProjects(data);
      setSelectedProjectId((current) =>
        current && data.some((p) => p.id === current) ? current : data[0]?.id ?? ""
      );
    } catch (err) {
      setProjects([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selectedProject =
    projects.find((p) => p.id === selectedProjectId) ?? null;

  const replaceProject = useCallback((updated: Project) => {
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  }, []);

  return {
    projects,
    selectedProject,
    selectedProjectId,
    setSelectedProjectId,
    replaceProject,
    isLoading,
    error,
    reload: load,
  };
}

/** Seletor de empreendimento reutilizado pelas páginas. */
export function projectShortLabel(project: Project): string {
  const words = project.name.split(" ");
  return words.slice(0, 2).join(" ");
}
