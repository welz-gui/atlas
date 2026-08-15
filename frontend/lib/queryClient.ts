import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";

/**
 * Cliente de consultas do Atlas (§6.1 — item D8).
 *
 * As opções abaixo não são preferência de estilo: cada uma existe para que a
 * adoção do TanStack Query **não** reabra o invariante I13 — *falha de rede
 * não vira dado*.
 *
 * O que se recusa explicitamente:
 *
 * - **`initialData` ou `placeholderData` com lista vazia.** Seria a mesma
 *   mentira que a Fase A removeu do frontend: a tela mostraria "nenhum
 *   empreendimento" enquanto o backend está fora do ar. Quem escrever consulta
 *   nova não deve preenchê-los com estruturas vazias;
 * - **`retry` indiscriminado.** Repetir um 404 três vezes só atrasa o erro
 *   para quem olha a tela. Repete-se apenas o que pode ser intermitente.
 */

/** Repete falha de rede uma vez; erro que o servidor respondeu, nenhuma. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  // `status === 0` é o que `request()` usa para "não falei com a API".
  return error instanceof ApiError && error.status === 0;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        // Dado de obra muda com o trabalho, não com o relógio: 30 s evita a
        // rajada de refetch ao alternar entre telas sem servir número velho.
        staleTime: 30_000,
        // Voltar para a aba não é motivo para nova rodada de chamadas; quem
        // precisa de dado fresco pede `refetch`.
        refetchOnWindowFocus: false,
        // Reconectar, sim: o técnico de campo perde e recupera rede o tempo
        // todo, e é justamente aí que a tela está desatualizada (§3.7).
        refetchOnReconnect: true,
      },
      mutations: {
        // Escrita não se repete sozinha. O que garante segurança contra
        // duplicata é o `client_token` do backend, e ele é responsabilidade de
        // quem chama — não do cliente de consultas.
        retry: false,
      },
    },
  });
}

/** Chaves de consulta em um lugar só, para que invalidar não vire adivinhação. */
export const queryKeys = {
  projects: ["projects"] as const,
  projectDailyLogs: (projectId: string) => ["projects", projectId, "daily-logs"] as const,
  projectDocuments: (projectId: string) => ["projects", projectId, "documents"] as const,
} as const;
