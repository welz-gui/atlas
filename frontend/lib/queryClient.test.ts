/**
 * O cliente de consultas não pode reabrir o I13 (§6.1 — item D8).
 *
 * Adotar uma camada de cache é o momento clássico de reintroduzir *"falha de
 * rede vira dado"*: basta um `initialData: []` bem-intencionado para a tela
 * dizer "nenhum empreendimento" enquanto o backend está fora do ar. Foi
 * exatamente o defeito que a Fase A removeu do frontend e que os PRs #17 e #27
 * tentaram trazer de volta.
 *
 * Estes testes travam as decisões do cliente, não a biblioteca.
 */

import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { createQueryClient, queryKeys } from "./queryClient";

function retryDecision(failureCount: number, error: unknown): boolean {
  const cliente = createQueryClient();
  const retry = cliente.getDefaultOptions().queries?.retry;
  if (typeof retry !== "function") throw new Error("retry deveria ser função");
  return retry(failureCount, error) as boolean;
}

describe("cliente de consultas", () => {
  it("não define dado inicial nem de espera", () => {
    // Qualquer um dos dois com estrutura vazia faria a ausência de resposta
    // parecer resposta vazia.
    const queries = createQueryClient().getDefaultOptions().queries ?? {};

    expect(queries).not.toHaveProperty("initialData");
    expect(queries.placeholderData).toBeUndefined();
  });

  it("repete falha de rede uma vez", () => {
    const semRede = new ApiError("API inacessível", 0);

    expect(retryDecision(0, semRede)).toBe(true);
    expect(retryDecision(1, semRede)).toBe(false);
  });

  it("não repete erro que o servidor respondeu", () => {
    // Repetir um 404 três vezes só atrasa o erro para quem olha a tela.
    for (const status of [400, 401, 403, 404, 422, 500]) {
      expect(retryDecision(0, new ApiError("erro", status))).toBe(false);
    }
  });

  it("não repete erro que não é da API", () => {
    expect(retryDecision(0, new Error("qualquer outra coisa"))).toBe(false);
  });

  it("não repete escrita", () => {
    // Segurança contra duplicata vem do `client_token` no backend, não daqui.
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false);
  });

  it("revalida ao reconectar, e não ao focar a aba", () => {
    const queries = createQueryClient().getDefaultOptions().queries ?? {};

    // O técnico de campo perde e recupera rede o tempo todo, e é aí que a tela
    // está desatualizada (§3.7). Voltar para a aba não é motivo.
    expect(queries.refetchOnReconnect).toBe(true);
    expect(queries.refetchOnWindowFocus).toBe(false);
  });
});

describe("chaves de consulta", () => {
  it("são estáveis, para que invalidar não vire adivinhação", () => {
    expect(queryKeys.projects).toEqual(["projects"]);
    expect(queryKeys.projectDailyLogs("p1")).toEqual([
      "projects",
      "p1",
      "daily-logs",
    ]);
  });
});
