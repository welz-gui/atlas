/**
 * Service worker do Atlas (§6.2, §3.7).
 *
 * A política de cache não é uniforme, e a diferença é de propósito. Há dados
 * cuja versão velha é inofensiva — a lista de tarefas de ontem — e há dados
 * cuja versão velha é perigosa: um veredicto de conformidade calculado sobre
 * um catálogo que já mudou, ou um laudo que passou a ser publicável (ou
 * deixou de ser) depois de a página ter sido guardada.
 *
 * Por isso três regras:
 *
 * 1. **App shell em cache-first.** HTML, JS e CSS podem vir do cache: a
 *    aplicação abre em campo sem rede.
 * 2. **Leituras de campo em network-first com cache de emergência.** Diário,
 *    tarefas, EAP e projetos respondem do cache quando a rede falha — e a
 *    resposta sai carimbada com `X-Atlas-From-Cache` e a data em que foi
 *    guardada, para a interface poder dizer ao técnico que aquilo é uma cópia.
 * 3. **Análise, laudo, catálogo e IA nunca vêm do cache.** Sem rede, falham.
 *    A ausência de resposta é honesta; uma resposta desatualizada sobre
 *    conformidade legal não é (§3.4).
 *
 * Escritas (POST/PATCH) nunca passam pelo service worker: quem trata rede
 * ausente na escrita é a fila em `lib/offline.ts`, que deixa o item visível
 * como pendente em vez de fingir que foi salvo.
 */

const VERSION = "atlas-v1";
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;

const SHELL_ASSETS = [
  "/",
  "/daily-log",
  "/plan",
  "/projects",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

/** Caminhos de API que podem responder do cache quando não há rede. */
const CACHEABLE_API = [
  /\/api\/v1\/projects$/,
  /\/api\/v1\/projects\/[^/]+$/,
  /\/api\/v1\/projects\/[^/]+\/daily-logs$/,
  /\/api\/v1\/projects\/[^/]+\/tasks$/,
  /\/api\/v1\/projects\/[^/]+\/eap$/,
  /\/api\/v1\/projects\/[^/]+\/documents$/,
];

/**
 * Caminhos que jamais respondem do cache.
 *
 * Todos dizem respeito a conformidade legal. Uma cópia velha aqui não é uma
 * inconveniência: é um erro com consequência jurídica.
 */
const NEVER_CACHE = [
  /\/api\/v1\/projects\/[^/]+\/evaluate/,
  /\/api\/v1\/projects\/[^/]+\/validations/,
  /\/api\/v1\/projects\/[^/]+\/analysis-runs/,
  /\/api\/v1\/projects\/[^/]+\/report/,
  /\/api\/v1\/analysis-runs\//,
  /\/api\/v1\/catalog\//,
  /\/api\/v1\/ai\//,
  /\/api\/v1\/auth\//,
  /\/api\/v1\/jobs/,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // `addAll` falha inteiro se um recurso falhar; em rota que exige login
      // isso derrubaria a instalação. Cada um por si.
      .then((cache) =>
        Promise.all(SHELL_ASSETS.map((asset) => cache.add(asset).catch(() => undefined)))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !key.startsWith(VERSION))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

function matches(patterns, url) {
  return patterns.some((pattern) => pattern.test(url));
}

/** Anexa a marca de cópia e a data de captura à resposta servida do cache. */
async function stamped(response) {
  const body = await response.blob();
  const headers = new Headers(response.headers);
  headers.set("X-Atlas-From-Cache", "true");
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = request.url;

  // Escrita é assunto da fila da aplicação, não do service worker.
  if (request.method !== "GET") return;
  if (!url.startsWith("http")) return;

  if (matches(NEVER_CACHE, url)) return; // deixa falhar, e falhar visivelmente

  if (url.includes("/api/")) {
    if (!matches(CACHEABLE_API, url)) return;

    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(DATA_CACHE).then((cache) => {
              const headers = new Headers(copy.headers);
              headers.set("X-Atlas-Cached-At", new Date().toISOString());
              copy.blob().then((body) => {
                cache.put(
                  request,
                  new Response(body, { status: copy.status, headers })
                );
              });
            });
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return stamped(cached);
          // Sem cópia: devolve um erro que a interface reconhece, em vez de
          // uma página de erro do navegador dentro de um fetch.
          return new Response(
            JSON.stringify({
              detail:
                "Sem conexão e sem cópia local destes dados. Reconecte para consultar.",
            }),
            { status: 503, headers: { "Content-Type": "application/json" } }
          );
        })
    );
    return;
  }

  // Navegação e estáticos: cache primeiro, rede para atualizar.
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok && response.type === "basic") {
            const copy = response.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

/** Permite que a aplicação force a ativação de uma versão nova. */
self.addEventListener("message", (event) => {
  if (event.data === "atlas:skip-waiting") self.skipWaiting();
});
