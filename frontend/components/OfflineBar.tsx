"use client";

/**
 * Barra de estado da operação de campo (§3.7, §6.2).
 *
 * Faz duas coisas que a interface não pode deixar implícitas:
 *
 * 1. registra o service worker — é o que permite abrir a aplicação em obra
 *    sem rede;
 * 2. mostra, o tempo todo, quantos registros ainda estão no celular. Um item
 *    na fila **não** foi salvo, e o técnico precisa saber disso antes de
 *    fechar o aplicativo achando que o diário do dia já está no sistema.
 */

import { useCallback, useEffect, useState } from "react";
import { CloudOff, Loader2, RefreshCw, Send, WifiOff } from "lucide-react";
import {
  OutboxItem,
  QUEUEABLE,
  flushOutbox,
  isOnline,
  listOutbox,
  startOutboxSync,
  subscribeToOutbox,
} from "@/lib/offline";

export default function OfflineBar() {
  const [online, setOnline] = useState(true);
  const [items, setItems] = useState<OutboxItem[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const reload = useCallback(() => {
    void listOutbox().then(setItems);
  }, []);

  useEffect(() => {
    // O service worker só é registrado em produção: em desenvolvimento ele
    // serviria bundles antigos e faria perder tempo caçando bug que não existe.
    if (
      typeof navigator !== "undefined" &&
      "serviceWorker" in navigator &&
      process.env.NODE_ENV === "production"
    ) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }

    setOnline(isOnline());
    reload();

    const unsubscribe = subscribeToOutbox(reload);
    const stopSync = startOutboxSync();
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);

    return () => {
      unsubscribe();
      stopSync();
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [reload]);

  const send = async () => {
    setIsSending(true);
    try {
      await flushOutbox();
    } finally {
      setIsSending(false);
      reload();
    }
  };

  const pendentes = items.filter((i) => i.status !== "falhou");
  const falhados = items.filter((i) => i.status === "falhou");

  if (online && items.length === 0) return null;

  return (
    <div className="sticky top-0 z-40">
      <div
        className={`px-4 py-2 text-xs font-semibold flex items-center justify-between gap-3 border-b ${
          online
            ? "bg-amber-950/70 border-amber-500/30 text-amber-200"
            : "bg-slate-900 border-slate-700 text-slate-300"
        }`}
      >
        <div className="flex items-center gap-2 min-w-0">
          {online ? (
            <CloudOff className="w-4 h-4 shrink-0" />
          ) : (
            <WifiOff className="w-4 h-4 shrink-0" />
          )}
          <span className="truncate">
            {!online && "Sem conexão. "}
            {items.length > 0
              ? `${items.length} registro(s) ainda no aparelho, não enviados.`
              : "Análise, laudo e assistente exigem conexão."}
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {items.length > 0 && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="underline underline-offset-2 hover:opacity-80"
            >
              {expanded ? "ocultar" : "ver"}
            </button>
          )}
          {online && pendentes.length > 0 && (
            <button
              onClick={send}
              disabled={isSending}
              className="px-2.5 py-1 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center gap-1.5 disabled:opacity-50"
            >
              {isSending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
              Enviar agora
            </button>
          )}
        </div>
      </div>

      {expanded && items.length > 0 && (
        <div className="bg-slate-950 border-b border-slate-800 px-4 py-3 space-y-2 max-h-64 overflow-y-auto">
          {items.map((item) => (
            <div
              key={item.id}
              className="text-[11px] flex items-start justify-between gap-3 p-2 rounded-lg bg-slate-900/60 border border-slate-800"
            >
              <div className="min-w-0">
                <p className="font-bold text-slate-200">
                  {QUEUEABLE[item.kind]}
                  {item.projectName ? ` • ${item.projectName}` : ""}
                </p>
                <p className="text-slate-400">
                  Escrito em {new Date(item.createdAt).toLocaleString("pt-BR")}
                </p>
                {item.lastError && (
                  <p className="text-red-400 mt-0.5 break-words">{item.lastError}</p>
                )}
              </div>
              <span
                className={`shrink-0 px-2 py-0.5 rounded-full font-bold ${
                  item.status === "falhou"
                    ? "bg-red-500/15 text-red-300 border border-red-500/30"
                    : "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                }`}
              >
                {item.status === "falhou" ? "recusado" : "pendente"}
              </span>
            </div>
          ))}

          {falhados.length > 0 && (
            <p className="text-[11px] text-slate-400 flex items-center gap-1.5 pt-1">
              <RefreshCw className="w-3 h-3" />
              Registros recusados pelo servidor não são retentados. Corrija o cadastro
              e lance novamente.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
