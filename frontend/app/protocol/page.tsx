"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Gavel,
  History,
  Plus,
  Target,
  X,
} from "lucide-react";
import {
  ApiError,
  PredictionAccuracy,
  ProtocolProcess,
  ProtocolStatusValue,
  changeProtocolStatus,
  createProtocol,
  createRequirement,
  fetchPredictionAccuracy,
  fetchProtocols,
  humanize,
  updateRequirement,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

const STATUS_STYLE: Record<string, string> = {
  protocolado: "bg-blue-500/10 text-blue-300 border-blue-500/40",
  em_analise: "bg-cyan-500/10 text-cyan-300 border-cyan-500/40",
  notificado: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  em_correcao: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  reprotocolado: "bg-blue-500/10 text-blue-300 border-blue-500/40",
  aprovado: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  indeferido: "bg-red-500/10 text-red-400 border-red-500/30",
  arquivado: "bg-slate-800 text-slate-400 border-slate-700",
};

const NEXT_STATUSES: ProtocolStatusValue[] = [
  "em_analise",
  "notificado",
  "em_correcao",
  "reprotocolado",
  "aprovado",
  "indeferido",
  "arquivado",
];

const TERMINAL = new Set(["aprovado", "indeferido", "arquivado"]);

export default function ProtocolPage() {
  const { can } = useAuth();
  const canWrite = can("protocol:write");
  const {
    projects,
    selectedProject,
    selectedProjectId,
    setSelectedProjectId,
    isLoading: isLoadingProjects,
    error: projectsError,
    reload: reloadProjects,
  } = useProjects();

  const [processes, setProcesses] = useState<ProtocolProcess[]>([]);
  const [accuracy, setAccuracy] = useState<PredictionAccuracy | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [isProtocolModalOpen, setIsProtocolModalOpen] = useState(false);
  const [requirementFor, setRequirementFor] = useState<ProtocolProcess | null>(null);

  const load = useCallback(async () => {
    if (!selectedProjectId) {
      setProcesses([]);
      setAccuracy(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [list, metrics] = await Promise.all([
        fetchProtocols(selectedProjectId),
        fetchPredictionAccuracy(selectedProjectId),
      ]);
      setProcesses(list);
      setAccuracy(metrics);
    } catch (err) {
      setProcesses([]);
      setAccuracy(null);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStatus = async (process: ProtocolProcess, status: ProtocolStatusValue) => {
    try {
      await changeProtocolStatus(process.id, { status });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  const handleRequirementStatus = async (requirementId: string, status: string) => {
    try {
      await updateRequirement(requirementId, { status: status as "atendida" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Gavel className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Aprovação municipal
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Tramitação</h1>
          <p className="text-xs text-slate-400 mt-1">
            Exigências vinculadas a uma regra do catálogo medem quanto da notificação
            real o Atlas havia antecipado.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {projects.length > 0 && (
            <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800 flex-wrap">
              {projects.map((project) => (
                <button
                  key={project.id}
                  onClick={() => setSelectedProjectId(project.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    selectedProjectId === project.id
                      ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {projectShortLabel(project)}
                </button>
              ))}
            </div>
          )}
          {canWrite && (
            <button
              onClick={() => setIsProtocolModalOpen(true)}
              disabled={!selectedProjectId}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 disabled:opacity-40 text-white font-semibold text-xs flex items-center gap-2"
            >
              <Plus className="w-4 h-4" /> Registrar protocolo
            </button>
          )}
        </div>
      </div>

      {projectsError && <ErrorBanner error={projectsError} onRetry={reloadProjects} />}
      {error && <ErrorBanner error={error} onRetry={load} />}
      {(isLoadingProjects || isLoading) && <LoadingState label="Carregando tramitação..." />}

      {!isLoadingProjects && !projectsError && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para registrar o protocolo junto ao órgão."
        />
      )}

      {!isLoading && !error && selectedProject && accuracy && (
        <div className="glass-panel rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold text-white uppercase tracking-wide">
              Recall de bloqueios
            </h2>
          </div>
          {accuracy.linked_to_rules === 0 ? (
            <p className="text-xs text-slate-400">
              Nenhuma exigência foi vinculada a uma regra do catálogo ainda. Sem vínculo,
              não há como medir a taxa de acerto — e o Atlas não estima o número.
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <Stat label="Exigências" value={accuracy.total_requirements} />
              <Stat label="Vinculadas a regras" value={accuracy.linked_to_rules} />
              <Stat
                label="Antecipadas"
                value={accuracy.predicted}
                className="text-emerald-400"
              />
              <Stat
                label="Recall"
                value={
                  accuracy.recall_percent === null ? "—" : `${accuracy.recall_percent}%`
                }
                className="text-cyan-400"
              />
            </div>
          )}
        </div>
      )}

      {!isLoading && !error && selectedProjectId && processes.length === 0 && (
        <EmptyState
          title="Nenhum protocolo registrado"
          description="Registre o protocolo do empreendimento para acompanhar exigências e prazos."
        />
      )}

      <div className="space-y-5">
        {processes.map((process) => (
          <div key={process.id} className="glass-panel rounded-2xl p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-white">
                  Protocolo {process.protocol_number}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  {process.agency}
                  {process.submitted_at && ` • protocolado em ${process.submitted_at}`}
                </p>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase border shrink-0 ${
                  STATUS_STYLE[process.status] ?? STATUS_STYLE.arquivado
                }`}
              >
                {humanize(process.status)}
              </span>
            </div>

            {canWrite && !TERMINAL.has(process.status) && (
              <div className="flex flex-wrap gap-2">
                {NEXT_STATUSES.filter((s) => s !== process.status).map((status) => (
                  <button
                    key={status}
                    onClick={() => handleStatus(process, status)}
                    className="px-2.5 py-1 rounded-md text-[10px] font-semibold bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300"
                  >
                    → {humanize(status)}
                  </button>
                ))}
              </div>
            )}

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  Exigências ({process.open_requirements_count} em aberto)
                </h4>
                {canWrite && (
                  <button
                    onClick={() => setRequirementFor(process)}
                    className="text-[11px] font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" /> Registrar exigência
                  </button>
                )}
              </div>

              {process.requirements.length === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nenhuma exigência registrada neste processo.
                </p>
              ) : (
                process.requirements.map((requirement) => (
                  <div
                    key={requirement.id}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs text-slate-200">
                        <span className="font-mono text-slate-500 mr-2">
                          {requirement.sequence}.
                        </span>
                        {requirement.description}
                      </p>
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase shrink-0 border ${
                          requirement.status === "atendida"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                        }`}
                      >
                        {humanize(requirement.status)}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-[10px] text-slate-500">
                      {requirement.due_date && (
                        <span className="flex items-center gap-1">
                          <CalendarClock className="w-3 h-3" /> prazo{" "}
                          {requirement.due_date}
                        </span>
                      )}
                      {requirement.linked_rule_key && (
                        <span className="font-mono">{requirement.linked_rule_key}</span>
                      )}
                      {requirement.was_predicted === true && (
                        <span className="flex items-center gap-1 text-emerald-400 font-semibold">
                          <CheckCircle2 className="w-3 h-3" /> antecipada pelo Atlas
                        </span>
                      )}
                      {requirement.was_predicted === false && (
                        <span className="flex items-center gap-1 text-red-400 font-semibold">
                          <AlertTriangle className="w-3 h-3" /> não antecipada
                        </span>
                      )}
                    </div>

                    {canWrite && requirement.status !== "atendida" && (
                      <button
                        onClick={() => handleRequirementStatus(requirement.id, "atendida")}
                        className="px-2.5 py-1 rounded-md text-[10px] font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                      >
                        Marcar como atendida
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>

            {process.events.length > 0 && (
              <div className="pt-3 border-t border-slate-800 space-y-1.5">
                <h4 className="text-[11px] font-bold text-slate-400 uppercase flex items-center gap-1.5">
                  <History className="w-3 h-3" /> Histórico
                </h4>
                {process.events.map((event) => (
                  <p key={event.id} className="text-[11px] text-slate-500">
                    {new Date(event.created_at).toLocaleString("pt-BR")} —{" "}
                    {humanize(event.event_type)}
                    {event.to_status && ` → ${humanize(event.to_status)}`}
                    {event.actor_name && ` (${event.actor_name})`}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {isProtocolModalOpen && selectedProjectId && (
        <ProtocolModal
          projectId={selectedProjectId}
          onClose={() => setIsProtocolModalOpen(false)}
          onCreated={() => {
            setIsProtocolModalOpen(false);
            load();
          }}
        />
      )}

      {requirementFor && (
        <RequirementModal
          process={requirementFor}
          validations={selectedProject?.validations ?? []}
          onClose={() => setRequirementFor(null)}
          onCreated={() => {
            setRequirementFor(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  className = "text-white",
}: {
  label: string;
  value: number | string;
  className?: string;
}) {
  return (
    <div>
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`text-lg font-extrabold ${className}`}>{value}</p>
    </div>
  );
}

function ProtocolModal({
  projectId,
  onClose,
  onCreated,
}: {
  projectId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [protocolNumber, setProtocolNumber] = useState("");
  const [agency, setAgency] = useState("Prefeitura Municipal");
  const [submittedAt, setSubmittedAt] = useState(new Date().toISOString().slice(0, 10));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      await createProtocol(projectId, {
        protocol_number: protocolNumber,
        agency,
        submitted_at: submittedAt,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="glass-panel rounded-2xl p-6 w-full max-w-lg space-y-4"
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white">Registrar protocolo</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <input
          value={protocolNumber}
          onChange={(e) => setProtocolNumber(e.target.value)}
          placeholder="Número do protocolo"
          required
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />
        <input
          value={agency}
          onChange={(e) => setAgency(e.target.value)}
          placeholder="Órgão"
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />
        <input
          type="date"
          value={submittedAt}
          onChange={(e) => setSubmittedAt(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
        />

        <p className="text-[11px] text-slate-500">
          O protocolo é vinculado à versão vigente do projeto, congelando o que foi
          efetivamente submetido.
        </p>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 text-xs font-semibold"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-50"
          >
            {isSaving ? "Salvando..." : "Registrar"}
          </button>
        </div>
      </form>
    </div>
  );
}

function RequirementModal({
  process,
  validations,
  onClose,
  onCreated,
}: {
  process: ProtocolProcess;
  validations: { rule_id: string; rule_title: string }[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [linkedRuleKey, setLinkedRuleKey] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      await createRequirement(process.id, {
        description,
        due_date: dueDate || undefined,
        linked_rule_key: linkedRuleKey || undefined,
        raised_at: new Date().toISOString().slice(0, 10),
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="glass-panel rounded-2xl p-6 w-full max-w-lg space-y-4"
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white">Registrar exigência</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Descrição da exigência do órgão"
          rows={3}
          required
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />

        <label className="block">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
            Regra correspondente do catálogo (opcional)
          </span>
          <select
            value={linkedRuleKey}
            onChange={(e) => setLinkedRuleKey(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
          >
            <option value="">Sem vínculo</option>
            {validations.map((v) => (
              <option key={v.rule_id} value={v.rule_id}>
                {v.rule_title}
              </option>
            ))}
          </select>
          <span className="text-[10px] text-slate-500 block mt-1">
            Vincular permite medir se o Atlas havia antecipado esta exigência.
          </span>
        </label>

        <label className="block">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
            Prazo de resposta
          </span>
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
          />
        </label>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 text-xs font-semibold"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-50"
          >
            {isSaving ? "Salvando..." : "Registrar"}
          </button>
        </div>
      </form>
    </div>
  );
}
