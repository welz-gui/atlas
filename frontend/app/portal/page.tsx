"use client";

/**
 * Portal do cliente (§8.22).
 *
 * Visão de acompanhamento para quem contratou a obra. O que entra aqui é
 * decidido no servidor (`app/api/v1/endpoints/portal.py`) — esta tela não
 * filtra nada, apenas apresenta.
 *
 * O ponto delicado é o resumo de conformidade. Quando a pré-análise aplica
 * regras ainda em conferência, o portal **não** mostra números — e essa
 * ausência precisa ser explicada, não disfarçada de "sem dados". Um cliente
 * que vê um painel vazio conclui que nada foi feito; a tela diz o que de fato
 * aconteceu e o que falta.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Building2,
  CalendarClock,
  CheckCircle2,
  FileText,
  Gavel,
  HardHat,
  Info,
  ShieldQuestion,
  XCircle,
} from "lucide-react";
import { ApiError, PortalProject, fetchPortalProjects, humanize } from "@/lib/api";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

export default function PortalPage() {
  const [projects, setProjects] = useState<PortalProject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setProjects(await fetchPortalProjects());
    } catch (err) {
      setProjects([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-8">
      <div className="border-b border-slate-800 pb-6">
        <div className="flex items-center gap-2 mb-1">
          <HardHat className="w-5 h-5 text-cyan-400" />
          <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
            Acompanhamento
          </span>
        </div>
        <h1 className="text-2xl font-bold text-white">Portal do empreendimento</h1>
        <p className="text-xs text-slate-400 mt-1">
          Situação do licenciamento, documentos vigentes e andamento da obra.
        </p>
      </div>

      {error && <ErrorBanner error={error} onRetry={load} />}
      {isLoading && <LoadingState label="Carregando acompanhamento..." />}

      {!isLoading && !error && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento disponível"
          description="Não há empreendimento vinculado a este acesso."
        />
      )}

      <div className="space-y-8">
        {projects.map((project) => (
          <ProjectPanel key={project.id} project={project} />
        ))}
      </div>
    </div>
  );
}

function ProjectPanel({ project }: { project: PortalProject }) {
  return (
    <div className="glass-panel rounded-2xl p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 border-b border-slate-800 pb-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-cyan-400 shrink-0" />
            <h2 className="text-lg font-bold text-white truncate">{project.name}</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {[project.address, project.district].filter(Boolean).join(", ") || "Endereço não informado"} •{" "}
            {project.city_name}/{project.state}
          </p>
          {project.technical_responsible_name && (
            <p className="text-[11px] text-slate-500 mt-0.5">
              Responsável técnico: {project.technical_responsible_name}
            </p>
          )}
        </div>

        <div className="text-right shrink-0">
          <p className="text-[10px] font-bold text-slate-500 uppercase">Licenciamento</p>
          <p className="text-sm font-bold text-cyan-300">
            {humanize(project.licensing_status)}
          </p>
          {project.version_number && (
            <p className="text-[11px] text-slate-500 mt-0.5">
              Projeto v{project.version_number} ({humanize(project.version_state ?? "")})
              {project.has_official_baseline && " • linha de base aprovada"}
            </p>
          )}
        </div>
      </div>

      <Compliance project={project} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Progress project={project} />
        <Protocols project={project} />
      </div>

      <Documents project={project} />

      <p className="text-[11px] text-slate-500 flex items-start gap-2 border-t border-slate-800 pt-4">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        {project.notice}
      </p>
    </div>
  );
}

function Compliance({ project }: { project: PortalProject }) {
  const { compliance } = project;

  if (!compliance.available) {
    return (
      <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-700 flex items-start gap-3">
        <ShieldQuestion className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-bold text-slate-200">
            Pré-análise ainda não liberada
          </p>
          <p className="text-xs text-slate-400">{compliance.reason}</p>
          {compliance.analysed_at && (
            <p className="text-[11px] text-slate-500">
              Última execução em{" "}
              {new Date(compliance.analysed_at).toLocaleString("pt-BR")}
              {compliance.project_version_number
                ? ` sobre a versão ${compliance.project_version_number} do projeto`
                : ""}
              .
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-white">Pré-análise urbanística</p>
        {compliance.analysed_at && (
          <p className="text-[11px] text-slate-500">
            {new Date(compliance.analysed_at).toLocaleDateString("pt-BR")}
            {compliance.project_version_number
              ? ` • versão ${compliance.project_version_number}`
              : ""}
          </p>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tally
          label="Conformes"
          value={compliance.conforme_count ?? 0}
          tone="text-emerald-400"
          icon={<CheckCircle2 className="w-4 h-4 text-emerald-400/80" />}
        />
        <Tally
          label="Impedimentos"
          value={compliance.blocking_count ?? 0}
          tone="text-red-400"
          icon={<XCircle className="w-4 h-4 text-red-400/80" />}
        />
        <Tally
          label="Pendentes"
          value={compliance.pending_count ?? 0}
          tone="text-amber-400"
          icon={<ShieldQuestion className="w-4 h-4 text-amber-400/80" />}
        />
      </div>

      <p className="text-[11px] text-slate-500">
        &ldquo;Pendentes&rdquo; são verificações sem informação suficiente no projeto —
        não são reprovações.
      </p>
    </div>
  );
}

function Tally({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number;
  tone: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold text-slate-400 uppercase">{label}</p>
        {icon}
      </div>
      <p className={`text-xl font-extrabold mt-1 ${tone}`}>{value}</p>
    </div>
  );
}

function Progress({ project }: { project: PortalProject }) {
  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-white flex items-center gap-2">
          <CalendarClock className="w-4 h-4 text-cyan-400" /> Andamento físico
        </p>
        <span className="text-sm font-extrabold text-cyan-300">
          {project.physical_progress_percent.toFixed(1)}%
        </span>
      </div>

      {project.milestones.length === 0 ? (
        // Zero sem etapas cadastradas não significa obra parada — significa
        // que ninguém mediu. Dizer isso evita uma conclusão errada.
        <p className="text-xs text-slate-400">
          Ainda não há etapas de obra cadastradas, portanto não há medição de
          andamento a apresentar.
        </p>
      ) : (
        <div className="space-y-2.5">
          {project.milestones.map((milestone) => (
            <div key={milestone.name} className="space-y-1">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-300 truncate">{milestone.name}</span>
                <span className="text-slate-400 font-mono shrink-0">
                  {milestone.progress_percent.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                  style={{ width: `${Math.min(100, milestone.progress_percent)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-[11px] text-slate-500">
        {project.open_tasks} tarefa(s) em aberto no planejamento.
      </p>
    </div>
  );
}

function Protocols({ project }: { project: PortalProject }) {
  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
      <p className="text-sm font-bold text-white flex items-center gap-2">
        <Gavel className="w-4 h-4 text-cyan-400" /> Tramitação
      </p>

      {project.protocols.length === 0 ? (
        <p className="text-xs text-slate-400">
          Nenhum processo protocolado até o momento.
        </p>
      ) : (
        <div className="space-y-3">
          {project.protocols.map((protocol) => (
            <div
              key={protocol.protocol_number}
              className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-white font-mono truncate">
                  {protocol.protocol_number}
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shrink-0">
                  {humanize(protocol.status)}
                </span>
              </div>
              <p className="text-[11px] text-slate-500">{protocol.agency}</p>

              {protocol.open_requirements.length > 0 && (
                <div className="space-y-1.5 pt-1 border-t border-slate-800">
                  <p className="text-[10px] font-bold text-amber-400 uppercase">
                    Exigências em aberto
                  </p>
                  {protocol.open_requirements.map((req, index) => (
                    <p key={index} className="text-[11px] text-amber-200/90">
                      • {req.description}
                      {req.due_date && (
                        <span className="text-slate-500"> (prazo: {req.due_date})</span>
                      )}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Documents({ project }: { project: PortalProject }) {
  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-white flex items-center gap-2">
          <FileText className="w-4 h-4 text-cyan-400" /> Documentos vigentes
        </p>
        <span className="text-[11px] text-slate-500">
          {project.current_documents.length} documento(s)
        </span>
      </div>

      {project.current_documents.length === 0 ? (
        <p className="text-xs text-slate-400">
          Nenhum documento vigente publicado até o momento.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {project.current_documents.map((doc) => (
            <div
              key={doc.id}
              className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-200 truncate">
                  {doc.title}
                </p>
                <p className="text-[11px] text-slate-500">
                  {humanize(doc.category)} • {new Date(doc.created_at).toLocaleDateString("pt-BR")}
                </p>
              </div>
              <span className="text-[10px] font-mono text-cyan-400 shrink-0">
                {doc.version}
              </span>
            </div>
          ))}
        </div>
      )}

      <p className="text-[11px] text-slate-500">
        Apenas versões vigentes são listadas. Versões substituídas saem de circulação
        para evitar uso de prancha desatualizada em obra.
      </p>
    </div>
  );
}
