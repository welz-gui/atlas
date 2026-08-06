"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, HelpCircle, Inbox, Loader2, PlugZap, RefreshCw } from "lucide-react";
import { ApiError, CheckStatus, RuleState } from "@/lib/api";

/**
 * Estados de carregamento, erro e vazio.
 *
 * A distinção importa: "não consegui carregar" e "não há nada aqui" são
 * situações diferentes e nunca devem parecer a mesma coisa numa ferramenta de
 * conformidade.
 */

export function LoadingState({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-slate-400">
      <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
      <p className="text-xs font-semibold">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center">
        <Inbox className="w-5 h-5 text-slate-500" />
      </div>
      <div>
        <p className="text-sm font-bold text-slate-200">{title}</p>
        <p className="text-xs text-slate-400 mt-1 max-w-md">{description}</p>
      </div>
      {action}
    </div>
  );
}

export function ErrorBanner({
  error,
  onRetry,
}: {
  error: ApiError | Error;
  onRetry?: () => void;
}) {
  const apiError = error instanceof ApiError ? error : null;
  const offline = apiError?.isOffline ?? false;

  return (
    <div className="p-5 rounded-2xl border border-red-500/40 bg-red-950/30 flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex items-start gap-3 flex-1">
        <div className="w-9 h-9 rounded-lg bg-red-500/15 border border-red-500/30 flex items-center justify-center shrink-0">
          {offline ? (
            <PlugZap className="w-4 h-4 text-red-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-red-400" />
          )}
        </div>
        <div className="space-y-1">
          <p className="text-sm font-bold text-red-300">
            {offline ? "Backend do Atlas indisponível" : "Falha ao carregar os dados"}
          </p>
          <p className="text-xs text-red-200/80">{error.message}</p>
          {apiError?.detail && (
            <p className="text-[11px] text-red-200/60 font-mono break-all">
              {apiError.detail}
            </p>
          )}
          <p className="text-[11px] text-red-200/70 pt-1">
            Nenhum dado é exibido nesta condição — o Atlas não substitui resultado de
            análise por valor de exemplo.
          </p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 rounded-xl bg-red-500/15 hover:bg-red-500/25 border border-red-500/40 text-red-200 font-semibold text-xs transition-all flex items-center gap-2 shrink-0 self-start"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Tentar novamente
        </button>
      )}
    </div>
  );
}

// --- Apresentação dos estados de verificação (§7.7) ------------------------

export const STATUS_PRESENTATION: Record<
  CheckStatus,
  { label: string; chip: string; card: string; text: string }
> = {
  conforme: {
    label: "Conforme",
    chip: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    card: "bg-slate-900/60 border-emerald-500/30",
    text: "text-emerald-400",
  },
  nao_conforme: {
    label: "Não conforme (bloqueio)",
    chip: "bg-red-500/10 text-red-400 border-red-500/30",
    card: "bg-red-950/20 border-red-500/40",
    text: "text-red-400",
  },
  atencao: {
    label: "Atenção (alerta)",
    chip: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    card: "bg-amber-950/20 border-amber-500/40",
    text: "text-amber-400",
  },
  nao_aplicavel: {
    label: "Não aplicável",
    chip: "bg-slate-800 text-slate-400 border-slate-700",
    card: "bg-slate-900/40 border-slate-800",
    text: "text-slate-400",
  },
  nao_verificavel: {
    label: "Não verificável",
    chip: "bg-blue-500/10 text-blue-300 border-blue-500/40",
    card: "bg-blue-950/20 border-blue-500/40",
    text: "text-blue-300",
  },
};

export function StatusChip({ status }: { status: CheckStatus }) {
  const presentation = STATUS_PRESENTATION[status] ?? STATUS_PRESENTATION.nao_aplicavel;
  return (
    <span
      className={`px-3 py-1 rounded-full text-[11px] font-extrabold tracking-wide uppercase border ${presentation.chip}`}
    >
      {presentation.label}
    </span>
  );
}

/**
 * Tarja exibida enquanto o catálogo regulatório não passou por validação
 * técnica humana (§7.5). Sem isso, o usuário não tem como saber que os
 * parâmetros exibidos não foram conferidos contra o texto legal.
 */
export function UnvalidatedRulesBanner({
  catalogVersion,
}: {
  catalogVersion?: string;
}) {
  return (
    <div className="p-4 rounded-2xl border border-amber-500/40 bg-amber-950/20 flex items-start gap-3">
      <HelpCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
      <div className="text-xs text-amber-200/90 space-y-1">
        <p className="font-bold text-amber-300">
          Catálogo regulatório em validação — resultado de uso interno
        </p>
        <p>
          As regras aplicadas ainda não foram conferidas contra o texto legal publicado
          pelo município, e por isso não exibem número de artigo. Este resultado não
          deve ser entregue ao cliente nem usado como base para protocolo sem
          conferência do responsável técnico.
        </p>
        {catalogVersion && (
          <p className="font-mono text-[10px] text-amber-200/60">
            Versão do catálogo: {catalogVersion}
          </p>
        )}
      </div>
    </div>
  );
}

export function RuleStateTag({ state }: { state: RuleState }) {
  if (state === "vigente") return null;
  return (
    <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide bg-amber-500/10 text-amber-400 border border-amber-500/30">
      {state.replace(/_/g, " ")}
    </span>
  );
}

/**
 * Aviso de recurso que exige conexão (§3.7).
 *
 * Análise regulatória, laudo, catálogo e assistente não têm modo offline — e
 * isso é decisão de projeto, não limitação técnica. Um veredicto de
 * conformidade calculado sobre catálogo desatualizado é pior que a ausência de
 * veredicto: o técnico protocolaria com base em um limite que já mudou.
 */
export function OnlineOnlyNotice({ feature }: { feature: string }) {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;

  return (
    <div className="p-4 rounded-2xl border border-slate-700 bg-slate-900/70 flex items-start gap-3">
      <PlugZap className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
      <div className="space-y-1">
        <p className="text-sm font-bold text-slate-200">
          {feature} exige conexão
        </p>
        <p className="text-xs text-slate-400">
          Este recurso não opera offline por decisão de projeto: um resultado
          calculado sobre um catálogo regulatório desatualizado seria pior que a
          ausência de resultado. O registro de campo — diário e tarefas — continua
          funcionando sem rede.
        </p>
      </div>
    </div>
  );
}
