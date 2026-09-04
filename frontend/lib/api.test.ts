/**
 * O contrato do cliente HTTP (I13).
 *
 * Aproveitado do PR #17, que foi fechado: os testes estavam certos, a
 * implementação que os acompanhava é que não — ela reescrevia `fetchProjects`
 * com `fetch` cru e devolvia `[]` no catch. Contra o `request()` do `master`,
 * que é o correto, estes mesmos testes passam.
 *
 * O que eles travam, e por que importa:
 *
 * - **falha de rede vira `ApiError`, nunca dado.** Backend fora do ar não pode
 *   ser indistinguível de "o usuário não tem empreendimentos";
 * - **o token vai em toda chamada autenticada.** `fetch` cru esquece o
 *   `Authorization`, e a resposta 401 vira lista vazia se alguém a engolir;
 * - **erro de API preserva o status**, para a interface distinguir 404 de 500.
 *
 * Foi exatamente este defeito que os PRs #17 e #27 tentaram introduzir, e é o
 * mesmo que a Fase A removeu do frontend. Sem estes testes, a CI só verifica
 * que o código compila — e `catch { return [] }` compila.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchProjects, login, setToken, setUnauthorizedHandler } from "./api";

const TOKEN = "token-de-teste";

function respostaOk(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

function respostaErro(status: number, detail: string) {
  return { ok: false, status, json: async () => ({ detail }) };
}

describe("request — o contrato do cliente HTTP", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    setToken(TOKEN);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setToken(null);
  });

  it("devolve o corpo quando a chamada dá certo", async () => {
    const projetos = [{ id: "1", name: "Residencial de Teste" }];
    (global.fetch as any).mockResolvedValueOnce(respostaOk(projetos));

    await expect(fetchProjects()).resolves.toEqual(projetos);
  });

  it("envia o token em toda chamada autenticada", async () => {
    (global.fetch as any).mockResolvedValueOnce(respostaOk([]));

    await fetchProjects();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/projects"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      })
    );
  });

  it("não envia Authorization quando não há token", async () => {
    setToken(null);
    (global.fetch as any).mockResolvedValueOnce(respostaOk([]));

    await fetchProjects();

    const [, init] = (global.fetch as any).mock.calls[0];
    expect(init.headers).not.toHaveProperty("Authorization");
  });

  // --- I13: falha de rede não vira dado -----------------------------------

  it("converte falha de rede em ApiError, e não em lista vazia", async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error("ECONNREFUSED"));

    await expect(fetchProjects()).rejects.toBeInstanceOf(ApiError);
  });

  it("converte TypeError (falha de fetch) em ApiError de conexão com status 0", async () => {
    (global.fetch as any).mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const promise = fetchProjects();
    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toHaveProperty("status", 0);
  });

  it("a ApiError de rede carrega status 0", async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error("ECONNREFUSED"));

    // Status 0 distingue "não falei com a API" de "a API respondeu erro".
    await expect(fetchProjects()).rejects.toMatchObject({ status: 0 });
  });

  it("erro de API vira ApiError preservando o status", async () => {
    (global.fetch as any).mockResolvedValueOnce(
      respostaErro(500, "Erro interno")
    );

    await expect(fetchProjects()).rejects.toMatchObject({ status: 500 });
  });

  it("404 chega como 404, para a interface poder distingui-lo", async () => {
    (global.fetch as any).mockResolvedValueOnce(
      respostaErro(404, "Empreendimento não encontrado.")
    );

    await expect(fetchProjects()).rejects.toMatchObject({ status: 404 });
  });

  it("login dispensa o token, porque é quem o obtém", async () => {
    setToken(null);
    // `login` faz duas chamadas: obtém o token e então busca o usuário.
    (global.fetch as any)
      .mockResolvedValueOnce(
        respostaOk({ access_token: "novo", token_type: "bearer" })
      )
      .mockResolvedValueOnce(respostaOk({ id: "u1", email: "e@atlas.demo" }));

    await login("engenharia@atlas.demo", "senha");

    const [, initLogin] = (global.fetch as any).mock.calls[0];
    expect(initLogin.headers).not.toHaveProperty("Authorization");

    // E a chamada seguinte já vai autenticada com o token recém-obtido.
    const [, initMe] = (global.fetch as any).mock.calls[1];
    expect(initMe.headers).toMatchObject({ Authorization: "Bearer novo" });
  });

  it("chama onUnauthorized em erro 401", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);

    (global.fetch as any).mockResolvedValueOnce(
      respostaErro(401, "Token inválido")
    );

    await expect(fetchProjects()).rejects.toMatchObject({ status: 401 });

    expect(handler).toHaveBeenCalled();

    // Limpa o estado
    setUnauthorizedHandler(null);
  });
});
