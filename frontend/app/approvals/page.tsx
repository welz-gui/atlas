"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  FileCheck,
  FileText,
  GitBranch,
  HelpCircle,
  Landmark,
  RotateCcw,
  ShieldCheck,
  Sliders,
  XCircle,
} from "lucide-react";
import {
  ApiError,
  ProjectVersion,
  ProjectVersionState,
  ValidationRecord,
  changeVersionState,
  createProjectVersion,
  evaluateProject,
  fetchProjectVersions,
  fetchReportPdf,
  formatParam,
  humanize,
  markOfficialBaseline,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  OnlineOnlyNotice,
  STATUS_PRESENTATION,
  StatusChip,
  UnvalidatedRulesBanner,
} from "@/components/StateViews";

const PARAMETERS = [
  { key: "front_setback", label: "Recuo frontal", unit: "m", min: 0, max: 10, step: 0.1, decimals: 2 },
  { key: "rear_setback", label: "Recuo dos fundos", unit: "m", min: 0, max: 10, step: 0.1, decimals: 2 },
  { key: "side_setback", label: "Recuo lateral", unit: "m", min: 0, max: 10, step: 0.1, decimals: 2 },
  { key: "built_area", label: "Área construída", unit: "m²", min: 0, max: 1000, step: 5, decimals: 0 },
  { key: "lot_area", label: "Área do lote", unit: "m²", min: 0, max: 2000, step: 5, decimals: 0 },
  { key: "permeability_rate", label: "Permeabilidade", unit: "%", min: 0, max: 100, step: 0.5, decimals: 1 },
] as const;

type ParameterKey = (typeof PARAMETERS)[number]["key"];

const VERSION_STATES: ProjectVersionState[] = [
  "estudo_preliminar",
  "revisao_interna",
  "protocolada",
  "notificada",
  "corrigida",
  "aprovada",
  "alteracao_em_obra",
  "as_built",
];

export default function ApprovalsPage() {
  const { can } = useAuth();
  const canWrite = can("project:write");
  const canBaseline = can("project:baseline");

  const {
    projects,
    selectedProject,
    selectedProjectId,
    setSelectedProjectId,
    isLoading,
    error,
    reload,
  } = useProjects();

  const [versions, setVersions] = useState<ProjectVersion[]>([]);
  const [draft, setDraft] = useState<Record<ParameterKey, number | null>>(
    {} as Record<ParameterKey, number | null>
  );
  const [changeReason, setChangeReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [actionError, setActionError] = useState<ApiError | Error | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const currentVersion = selectedProject?.current_version ?? null;

  const loadVersions = useCallback(async () => {
    if (!selectedProjectId) {
      setVersions([]);
      return;
    }
    try {
      setVersions(await fetchProjectVersions(selectedProjectId));
    } catch (err) {
      setActionError(err instanceof Error ? err : new Error(String(err)));
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  // O rascunho parte sempre da versão vigente.
  useEffect(() => {
    if (!currentVersion) return;
    setDraft(
      Object.fromEntries(
        PARAMETERS.map(({ key }) => [key, currentVersion[key]])
      ) as Record<ParameterKey, number | null>
    );
    setChangeReason("");
    setReportError(null);
  }, [currentVersion?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirtyKeys = useMemo(() => {
    if (!currentVersion) return [];
    return PARAMETERS.filter(({ key }) => draft[key] !== currentVersion[key]).map(
      ({ key }) => key
    );
  }, [draft, currentVersion]);

  /**
   * Publica as alterações como uma versão nova.
   *
   * Não existe "salvar por cima": a versão vigente é imutável, e é isso que
   * permite a orçamento e cronograma referenciarem uma linha de base estável.
   */
  const handleCreateVersion = async () => {
    if (!selectedProjectId || dirtyKeys.length === 0) return;
    setIsSaving(true);
    setActionError(null);
    try {
      const payload = Object.fromEntries(dirtyKeys.map((key) => [key, draft[key]]));
      await createProjectVersion(selectedProjectId, {
        ...payload,
        change_reason: changeReason || undefined,
      });
      await Promise.all([reload(), loadVersions()]);
      setChangeReason("");
    } catch (err) {
      setActionError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReevaluate = async () => {
    if (!selectedProjectId) return;
    setIsSaving(true);
    setActionError(null);
    try {
      await evaluateProject(selectedProjectId);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  const handleVersionState = async (version: ProjectVersion, state: ProjectVersionState) => {
    if (!selectedProjectId) return;
    try {
      await changeVersionState(selectedProjectId, version.id, state);
      await Promise.all([reload(), loadVersions()]);
    } catch (err) {
      setActionError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  const handleBaseline = async (version: ProjectVersion) => {
    if (!selectedProjectId) return;
    setActionError(null);
    try {
      await markOfficialBaseline(selectedProjectId, version.id);
      await Promise.all([reload(), loadVersions()]);
    } catch (err) {
      setActionError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  const handleEmitReport = async () => {
    if (!selectedProjectId) return;
    setReportError(null);
    try {
      const { blob } = await fetchReportPdf(selectedProjectId);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      setReportError(apiError?.detail ?? "Não foi possível emitir o laudo.");
    }
  };

  const validations: ValidationRecord[] = selectedProject?.validations ?? [];
  const countBy = (status: ValidationRecord["status"]) =>
    validations.filter((v) => v.status === status).length;
  const hasUnvalidatedRules = validations.some((v) => !v.is_publishable);

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Pré-análise legal
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Copiloto de Aprovação</h1>
          <p className="text-xs text-slate-400 mt-1">
            Verificação determinística sobre a versão vigente do projeto.
          </p>
        </div>

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
      </div>

      <OnlineOnlyNotice feature="A pré-análise regulatória" />
      {error && <ErrorBanner error={error} onRetry={reload} />}
      {actionError && <ErrorBanner error={actionError} />}
      {isLoading && <LoadingState label="Carregando empreendimentos..." />}

      {!isLoading && !error && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para que o motor regulatório execute a pré-análise."
        />
      )}

      {!isLoading && !error && selectedProject && currentVersion && (
        <>
          {hasUnvalidatedRules && <UnvalidatedRulesBanner />}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            <StatCard
              label="Conformes"
              value={countBy("conforme")}
              icon={<CheckCircle2 className="w-7 h-7 text-emerald-400/80" />}
              accent="border-l-emerald-500"
            />
            <StatCard
              label="Não conformes"
              value={countBy("nao_conforme")}
              icon={<XCircle className="w-7 h-7 text-red-400/80" />}
              accent="border-l-red-500"
              valueClass="text-red-400"
            />
            <StatCard
              label="Atenção"
              value={countBy("atencao")}
              icon={<HelpCircle className="w-7 h-7 text-amber-400/80" />}
              accent="border-l-amber-500"
              valueClass="text-amber-400"
            />
            <StatCard
              label="Não verificáveis"
              value={countBy("nao_verificavel")}
              icon={<HelpCircle className="w-7 h-7 text-blue-400/80" />}
              accent="border-l-blue-500"
              valueClass="text-blue-300"
            />
          </div>

          {/* Editor de parâmetros */}
          <div className="glass-panel rounded-2xl p-6 border-cyan-500/30 space-y-4 glow-blue">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-bold text-white">
                  Parâmetros — versão {currentVersion.version_number} (
                  {humanize(currentVersion.state)})
                </h2>
              </div>
              <button
                onClick={handleReevaluate}
                disabled={isSaving}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold disabled:opacity-50"
              >
                <RotateCcw className="w-3 h-3" /> Reavaliar
              </button>
            </div>

            <p className="text-[11px] text-slate-400">
              Alterar um parâmetro não sobrescreve a versão atual: gera uma versão nova,
              com autor e motivo. Os veredictos vêm sempre do motor de regras.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-2">
              {PARAMETERS.map((parameter) => {
                const value = draft[parameter.key];
                const isDirty = dirtyKeys.includes(parameter.key);
                return (
                  <div key={parameter.key}>
                    <div className="flex justify-between text-[11px] mb-2 gap-2">
                      <span className="text-slate-300 font-semibold">
                        {parameter.label}:
                      </span>
                      <span
                        className={`font-mono font-bold ${
                          isDirty ? "text-amber-400" : "text-cyan-400"
                        }`}
                      >
                        {value === null
                          ? "não informado"
                          : formatParam(value, parameter.unit, parameter.decimals)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={parameter.min}
                      max={parameter.max}
                      step={parameter.step}
                      value={value ?? parameter.min}
                      disabled={!canWrite}
                      onChange={(e) =>
                        setDraft((prev) => ({
                          ...prev,
                          [parameter.key]: parseFloat(e.target.value),
                        }))
                      }
                      className="w-full accent-cyan-400 bg-slate-800 rounded-lg cursor-pointer disabled:opacity-40"
                    />
                  </div>
                );
              })}
            </div>

            {canWrite && dirtyKeys.length > 0 && (
              <div className="pt-4 border-t border-slate-800 space-y-3">
                <p className="text-[11px] text-amber-300 font-semibold">
                  {dirtyKeys.length} parâmetro(s) alterado(s) — ainda não gravados.
                </p>
                <input
                  value={changeReason}
                  onChange={(e) => setChangeReason(e.target.value)}
                  placeholder="Motivo da alteração (recomendado)"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:border-cyan-500 outline-none"
                />
                <div className="flex gap-3">
                  <button
                    onClick={handleCreateVersion}
                    disabled={isSaving}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-50 flex items-center gap-2"
                  >
                    <GitBranch className="w-3.5 h-3.5" />
                    {isSaving
                      ? "Gravando..."
                      : `Criar versão ${currentVersion.version_number + 1}`}
                  </button>
                  <button
                    onClick={() =>
                      setDraft(
                        Object.fromEntries(
                          PARAMETERS.map(({ key }) => [key, currentVersion[key]])
                        ) as Record<ParameterKey, number | null>
                      )
                    }
                    className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 text-xs font-semibold"
                  >
                    Descartar
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Verificações */}
          <div className="glass-panel rounded-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4 flex-wrap gap-3">
              <div>
                <h2 className="text-base font-bold text-white">
                  Resultado da verificação normativa
                </h2>
                <p className="text-xs text-slate-400">
                  {selectedProject.city_ibge} ({selectedProject.city_name}/
                  {selectedProject.state}) • Zona {currentVersion.zone} • ocupação{" "}
                  {formatParam(currentVersion.occupancy_rate, "%", 1)}
                </p>
              </div>
              <button
                onClick={handleEmitReport}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-xs flex items-center gap-2"
              >
                <FileCheck className="w-4 h-4" /> Emitir laudo PDF
              </button>
            </div>

            {reportError && (
              <div className="p-3 rounded-xl border border-red-500/40 bg-red-950/30 text-xs text-red-200">
                {reportError}
              </div>
            )}

            {validations.length === 0 ? (
              <EmptyState
                title="Nenhuma verificação registrada"
                description="O motor não encontrou regras aplicáveis a este empreendimento na jurisdição cadastrada."
              />
            ) : (
              <div className="space-y-4">
                {validations.map((rule) => {
                  const presentation =
                    STATUS_PRESENTATION[rule.status] ?? STATUS_PRESENTATION.nao_aplicavel;
                  return (
                    <div
                      key={rule.id}
                      className={`p-5 rounded-xl border ${presentation.card}`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
                        <h3 className="text-sm font-bold text-white">{rule.rule_title}</h3>
                        <StatusChip status={rule.status} />
                      </div>

                      <p className="text-xs text-slate-300 mb-3">{rule.details}</p>

                      <div className="pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                        <div>
                          <span className="text-slate-500 text-[11px] block">Exigido:</span>
                          <span className="font-mono text-slate-200 font-semibold">
                            {rule.expected_value}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 text-[11px] block">Apurado:</span>
                          <span className={`font-mono font-bold ${presentation.text}`}>
                            {rule.actual_value}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 text-[11px] block">Fonte:</span>
                          <span className="text-slate-400 italic text-[11px] flex items-start gap-1">
                            <FileText className="w-3 h-3 text-cyan-400 shrink-0 mt-0.5" />
                            <span>
                              {rule.source_citation}
                              {!rule.source_is_verified && (
                                <span className="text-amber-400 font-semibold not-italic">
                                  {" "}
                                  [não conferida]
                                </span>
                              )}
                            </span>
                          </span>
                        </div>
                      </div>

                      {rule.status === "nao_verificavel" && rule.evidence_required && (
                        <p className="mt-3 text-[11px] text-blue-300">
                          Evidência necessária: {rule.evidence_required}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Histórico de versões */}
          <div className="glass-panel rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-4">
              <GitBranch className="w-4 h-4 text-cyan-400" />
              <h2 className="text-base font-bold text-white">Versões do projeto</h2>
            </div>

            <div className="space-y-3">
              {versions.map((version) => (
                <div
                  key={version.id}
                  className={`p-4 rounded-xl border space-y-3 ${
                    version.is_official_baseline
                      ? "bg-cyan-950/20 border-cyan-500/40"
                      : "bg-slate-900/60 border-slate-800"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-white flex items-center gap-2">
                        Versão {version.version_number}
                        {version.is_official_baseline && (
                          <span className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                            <Landmark className="w-3 h-3" /> linha de base
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {humanize(version.state)} •{" "}
                        {new Date(version.created_at).toLocaleString("pt-BR")}
                        {version.change_reason && ` • ${version.change_reason}`}
                      </p>
                    </div>

                    {canBaseline &&
                      version.state === "aprovada" &&
                      !version.is_official_baseline && (
                        <button
                          onClick={() => handleBaseline(version)}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-semibold bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 shrink-0"
                        >
                          Eleger linha de base
                        </button>
                      )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                    <Param label="Recuo frontal" value={formatParam(version.front_setback, "m")} />
                    <Param label="Área construída" value={formatParam(version.built_area, "m²", 0)} />
                    <Param label="Ocupação" value={formatParam(version.occupancy_rate, "%", 1)} />
                    <Param label="Permeabilidade" value={formatParam(version.permeability_rate, "%", 1)} />
                  </div>

                  {canWrite && (
                    <div className="flex flex-wrap gap-1.5">
                      {VERSION_STATES.filter((s) => s !== version.state).map((state) => (
                        <button
                          key={state}
                          onClick={() => handleVersionState(version, state)}
                          className="px-2 py-1 rounded-md text-[10px] font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300"
                        >
                          → {humanize(state)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  accent,
  valueClass = "text-white",
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  accent: string;
  valueClass?: string;
}) {
  return (
    <div
      className={`glass-panel p-5 rounded-2xl border-l-4 ${accent} flex items-center justify-between gap-2`}
    >
      <div className="min-w-0">
        <p className="text-[11px] font-bold text-slate-400 uppercase truncate">{label}</p>
        <p className={`text-2xl font-extrabold mt-1 ${valueClass}`}>{value}</p>
      </div>
      <div className="shrink-0">{icon}</div>
    </div>
  );
}

function Param({ label, value }: { label: string; value: string }) {
  const notInformed = value === "não informado";
  return (
    <div>
      <span className="text-slate-500 block">{label}:</span>
      <span
        className={`font-mono ${notInformed ? "text-blue-300/70 italic" : "text-slate-200"}`}
      >
        {value}
      </span>
    </div>
  );
}
