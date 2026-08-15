"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { ApiError, Project, fetchProjects } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";

/**
 * Carrega a lista de empreendimentos com estados explícitos.
 *
 * Não existe estado "dado de exemplo": ou há dado do backend, ou há erro, ou a
 * lista está genuinamente vazia. Por isso não há `initialData` — ela faria a
 * tela dizer "nenhum empreendimento" enquanto o backend está fora do ar, que é
 * o defeito que o I13 existe para impedir.
 *
 * A forma de retorno é a mesma de antes da adoção do TanStack Query (§6.1, D8),
 * de propósito: nove páginas consomem este hook, e a migração não precisava
 * tocar em nenhuma delas.
 */
export function useProjects() {
  const queryClient = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  const query = useQuery({
    queryKey: queryKeys.projects,
    queryFn: fetchProjects,
  });

  // A lista só existe quando a consulta deu certo. Em erro, `data` é
  // `undefined`, e o `?? []` abaixo alimenta apenas a renderização — quem
  // decide o que mostrar é `error`, exposto logo adiante.
  const projects = query.data ?? [];

  // Seleção derivada: mantém a escolha do usuário enquanto ela existir na
  // lista, e cai para o primeiro item quando não existir mais.
  const resolvedId =
    selectedProjectId && projects.some((p) => p.id === selectedProjectId)
      ? selectedProjectId
      : projects[0]?.id ?? "";

  const selectedProject = projects.find((p) => p.id === resolvedId) ?? null;

  /** Atualiza um empreendimento no cache, sem nova ida ao servidor. */
  const replaceProject = useCallback(
    (updated: Project) => {
      queryClient.setQueryData<Project[]>(queryKeys.projects, (atual) =>
        (atual ?? []).map((p) => (p.id === updated.id ? updated : p))
      );
    },
    [queryClient]
  );

  const reload = useCallback(() => {
    return queryClient.invalidateQueries({ queryKey: queryKeys.projects });
  }, [queryClient]);

  return {
    projects,
    selectedProject,
    selectedProjectId: resolvedId,
    setSelectedProjectId,
    replaceProject,
    isLoading: query.isPending,
    error: (query.error as ApiError | Error | null) ?? null,
    reload,
  };
}

/** Seletor de empreendimento reutilizado pelas páginas. */
export function projectShortLabel(project: Project): string {
  const words = project.name.split(" ");
  return words.slice(0, 2).join(" ");
}
