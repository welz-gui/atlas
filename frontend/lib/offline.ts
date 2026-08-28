/**
 * Operação de campo sem rede (§3.7, §6.2).
 *
 * Em obra a conexão cai. O que este módulo resolve é o registro do que
 * aconteceu no canteiro — diário, tarefas, ocorrências — sem que o técnico
 * perca o trabalho por estar num subsolo.
 *
 * Três decisões que não são detalhe:
 *
 * 1. **A fila é explícita, nunca invisível.** Um item enfileirado aparece na
 *    interface como *pendente de envio*, com a hora em que foi escrito. Nunca
 *    como salvo. Diário de obra é documento com valor probatório: dar por
 *    assinado o que ainda está no celular seria criar um registro falso.
 *
 * 2. **Só escrita de campo entra na fila.** Análise regulatória, laudo e
 *    assistente **não** funcionam offline, e é deliberado: um veredicto de
 *    conformidade calculado sobre catálogo desatualizado é pior que a ausência
 *    de veredicto (§3.4). Essas telas recusam e explicam.
 *
 * 3. **O reenvio é idempotente pela chave do cliente.** Cada item carrega um
 *    `client_token`; um reenvio depois de resposta perdida não cria diário
 *    duplicado.
 */

import { ApiError, createDailyLog, createProjectTask } from "@/lib/api";

const DB_NAME = "atlas-offline";
const DB_VERSION = 1;
const STORE = "outbox";

export type OutboxKind = "daily_log" | "task";

export type OutboxStatus = "pendente" | "enviando" | "falhou";

export interface OutboxItem {
  id: string;
  kind: OutboxKind;
  projectId: string;
  projectName?: string;
  payload: Record<string, unknown>;
  /** Momento em que o técnico escreveu — não o momento do envio. */
  createdAt: string;
  status: OutboxStatus;
  attempts: number;
  lastError?: string;
}

/** Ações que a fila aceita. O que não estiver aqui exige rede. */
export const QUEUEABLE: Record<OutboxKind, string> = {
  daily_log: "Diário de obra",
  task: "Tarefa",
};

// --- IndexedDB ---------------------------------------------------------------

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Este navegador não suporta armazenamento local."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB indisponível."));
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T>
): Promise<T> {
  const db = await openDb();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const request = run(tx.objectStore(STORE));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Falha no armazenamento local."));
    tx.oncomplete = () => db.close();
  });
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// --- Fila --------------------------------------------------------------------

const listeners = new Set<() => void>();

/** Avisa a interface de que a fila mudou — o contador precisa ser exato. */
function notify(): void {
  listeners.forEach((listener) => listener());
}

export function subscribeToOutbox(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function listOutbox(): Promise<OutboxItem[]> {
  try {
    const items = await withStore<OutboxItem[]>("readonly", (store) => store.getAll());
    return items.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  } catch {
    // Sem IndexedDB não há fila: melhor a interface saber que não há fila do
    // que exibir um contador que não corresponde a nada.
    return [];
  }
}

export async function enqueue(
  kind: OutboxKind,
  projectId: string,
  payload: Record<string, unknown>,
  projectName?: string
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: newId(),
    kind,
    projectId,
    projectName,
    // O token de idempotência acompanha o item: reenviar depois de uma
    // resposta perdida não pode criar dois diários.
    payload: { ...payload, client_token: newId() },
    createdAt: new Date().toISOString(),
    status: "pendente",
    attempts: 0,
  };
  await withStore("readwrite", (store) => store.put(item));
  notify();
  return item;
}

export async function removeFromOutbox(id: string): Promise<void> {
  await withStore("readwrite", (store) => store.delete(id));
  notify();
}

async function update(item: OutboxItem): Promise<void> {
  await withStore("readwrite", (store) => store.put(item));
  notify();
}

export interface FlushReport {
  sent: number;
  failed: number;
  remaining: number;
}

/**
 * Tenta enviar tudo o que está pendente.
 *
 * Um item que falha por rede continua na fila. Um item recusado pelo servidor
 * — 4xx que não seja 401 — para de ser retentado e fica marcado com o motivo:
 * insistir num payload que o servidor rejeita só produziria uma fila que
 * nunca esvazia e um técnico que nunca entende por quê.
 */
export async function flushOutbox(): Promise<FlushReport> {
  const items = await listOutbox();
  let sent = 0;
  let failed = 0;
  let isOffline = false;

  // A concurrent worker pool with a concurrency limit.
  // It handles the items sequentially per worker, ensuring we don't start
  // any operations (like DB updates or network requests) once isOffline is true.

  let currentIndex = 0;

  async function worker() {
    while (currentIndex < items.length) {
      if (isOffline) break;

      const item = items[currentIndex++];

      if (item.status === "falhou") {
        failed += 1;
        continue;
      }

      await update({ ...item, status: "enviando" });

      if (isOffline) {
        // Se a rede caiu durante o update local (raro mas possível em concorrência alta)
        // Restauramos para pendente
        await update({ ...item, status: "pendente" });
        break;
      }

      try {
        if (item.kind === "daily_log") {
          await createDailyLog(item.projectId, item.payload as never);
        } else {
          await createProjectTask(item.projectId, item.payload as never);
        }
        await removeFromOutbox(item.id);
        sent += 1;
      } catch (error) {
        const apiError = error instanceof ApiError ? error : null;
        const permanente =
          apiError !== null &&
          apiError.status >= 400 &&
          apiError.status < 500 &&
          apiError.status !== 401;

        await update({
          ...item,
          status: permanente ? "falhou" : "pendente",
          attempts: item.attempts + 1,
          lastError: apiError?.detail ?? (error as Error).message,
        });
        failed += 1;

        if (apiError?.isOffline) {
          isOffline = true;
          break;
        }
      }
    }
  }

  // Limit concurrency to avoid network/DB starvation but still get a speedup
  const concurrency = Math.min(5, items.length);
  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);

  const remaining = (await listOutbox()).length;
  return { sent, failed, remaining };
}

// --- Conectividade -----------------------------------------------------------

export function isOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine;
}

/**
 * Envia a fila quando a conexão volta.
 *
 * `navigator.onLine` mente com frequência — diz "online" em rede de canteiro
 * sem saída para a internet. Por isso o resultado do envio é o que vale: se
 * falhar, os itens permanecem na fila e o aviso continua visível.
 */
export function startOutboxSync(): () => void {
  if (typeof window === "undefined") return () => undefined;

  const handler = () => {
    void flushOutbox();
  };
  window.addEventListener("online", handler);
  return () => window.removeEventListener("online", handler);
}
