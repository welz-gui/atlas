"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  FileCheck,
  FileText,
  HelpCircle,
  RotateCcw,
  ShieldCheck,
  Sliders,
  XCircle,
} from "lucide-react";
import {
  ApiError,
  Project,
  ValidationRecord,
  formatParam,
  getProjectReportPDFUrl,
  updateProjectParameters,
} from "@/lib/api";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  STATUS_PRESENTATION,
  StatusChip,
  UnvalidatedRulesBanner,
} from "@/components/StateViews";

/** Parâmetros que o simulador ajusta. */
const SLIDERS = [
  { key: "front_setback", label: "Recuo frontal", unit: "m", min: 0, max: 8, step: 0.1, decimals: 2 },
  { key: "rear_setback", label: "Recuo dos fundos", unit: "m", min: 0, max: 8, step: 0.1, decimals: 2 },
  { key: "built_area", label: "Área construída", unit: "m²", min: 0, max: 600, step: 5, decimals: 0 },
  { key: "permeability_rate", label: "Permeabilidade", unit: "%", min: 0, max: 60, step: 0.5, decimals: 1 },
] as const;

type SliderKey = (typeof SLIDERS)[number]["key"];

export default function ApprovalsPage() {
  const {
    projects,
    selectedProject,
    selectedProjectId,
    setSelectedProjectId,
    replaceProject,
    isLoading,
    error,
    reload,
  } = useProjects();

  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<ApiError | Error | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  // Rascunho local dos sliders, sincronizado com o projeto selecionado.
  const [draft, setDraft] = useState<Record<SliderKey, number | null>>({
    front_setback: null,
    rear_setback: null,
    built_area: null,
    permeability_rate: null,
  });

  useEffect(() => {
    if (!selectedProject) return;
    setDraft({
      front_setback: selectedProject.front_setback,
      rear_setback: selectedProject.rear_setback,
      built_area: selectedProject.built_area,
      permeability_rate: selectedProject.permeability_rate,
    });
    setReportError(null);
  }, [selectedProject?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Envia o parâmetro ao backend e adota a resposta.
   *
   * Os veredictos vêm sempre do motor de regras. O protótipo reimplementava os
   * limites em JavaScript quando a API estava fora do ar — uma segunda fonte
   * da verdade para conformidade legal, que foi removida.
   */
  const applyParameter = useCallback(
    async (key: SliderKey, value: number) => {
      if (!selectedProject) return;
      setDraft((prev) => ({ ...prev, [key]: value }));
      setIsUpdating(true);
      setUpdateError(null);
      try {
        const updated = await updateProjectParameters(selectedProject.id, {
          [key]: value,
        } as Partial<Project>);
        replaceProject(updated);
      } catch (err) {
        setUpdateError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsUpdating(false);
      }
    },
    [selectedProject, replaceProject]
  );

  const handleEmitReport = async () => {
    if (!selectedProject) return;
    setReportError(null);
    const url = getProjectReportPDFUrl(selectedProject.id);
    try {
      const response = await fetch(url);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setReportError(
          body?.detail ?? `Não foi possível emitir o laudo (HTTP ${response.status}).`
        );
        return;
      }
      const blob = await response.blob();
      window.open(URL.createObjectURL(blob), "_blank");
    } catch {
      setReportError(
        "Não foi possível falar com a API para emitir o laudo. Verifique se o backend está em execução."
      );
    }
  };

  const validations: ValidationRecord[] = selectedProject?.validations ?? [];
  const countBy = (status: ValidationRecord["status"]) =>
    validations.filter((v) => v.status === status).length;

  const hasUnvalidatedRules = validations.some((v) => !v.is_publishable);
  const catalogVersion = validations[0]?.rule_state ? undefined : undefined;

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Estágio 1 • Pré-análise legal
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Copiloto de Aprovação Municipal</h1>
          <p className="text-xs text-slate-400 mt-1">
            Verificação determinística de parâmetros urbanísticos a partir do catálogo
            regulatório.
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
                    ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold shadow-md shadow-cyan-500/20"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {projectShortLabel(project)}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <ErrorBanner error={error} onRetry={reload} />}
      {isLoading && <LoadingState label="Carregando empreendimentos..." />}

      {!isLoading && !error && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para que o motor regulatório possa executar a pré-análise."
        />
      )}

      {!isLoading && !error && selectedProject && (
        <>
          {hasUnvalidatedRules && <UnvalidatedRulesBanner catalogVersion={catalogVersion} />}
          {updateError && <ErrorBanner error={updateError} />}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <StatCard
              label="Conformes"
              value={countBy("conforme")}
              icon={<CheckCircle2 className="w-8 h-8 text-emerald-400/80" />}
              accent="border-l-emerald-500"
              valueClass="text-white"
            />
            <StatCard
              label="Não conformes (bloqueio)"
              value={countBy("nao_conforme")}
              icon={<XCircle className="w-8 h-8 text-red-400/80" />}
              accent="border-l-red-500"
              valueClass="text-red-400"
            />
            <StatCard
              label="Atenção (alerta)"
              value={countBy("atencao")}
              icon={<HelpCircle className="w-8 h-8 text-amber-400/80" />}
              accent="border-l-amber-500"
              valueClass="text-amber-400"
            />
            <StatCard
              label="Não verificáveis"
              value={countBy("nao_verificavel")}
              icon={<HelpCircle className="w-8 h-8 text-blue-400/80" />}
              accent="border-l-blue-500"
              valueClass="text-blue-300"
            />
          </div>

          {/* Simulador */}
          <div className="glass-panel rounded-2xl p-6 border-cyan-500/30 space-y-4 glow-blue">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-bold text-white">
                  Simulador de parâmetros: {selectedProject.name}
                </h2>
                {isUpdating && (
                  <span className="text-[10px] text-cyan-400 animate-pulse font-semibold">
                    reavaliando no motor de regras...
                  </span>
                )}
              </div>
              <button
                onClick={reload}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold"
              >
                <RotateCcw className="w-3 h-3" /> Recarregar do servidor
              </button>
            </div>

            <p className="text-[11px] text-slate-400">
              Cada ajuste é enviado à API e reavaliado pelo motor de regras. Os veredictos
              abaixo vêm sempre do servidor — a interface não calcula conformidade.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-2">
              {SLIDERS.map((slider) => {
                const value = draft[slider.key];
                return (
                  <div key={slider.key}>
                    <div className="flex justify-between text-[11px] mb-2 gap-2">
                      <span className="text-slate-300 font-semibold">{slider.label}:</span>
                      <span className="font-mono font-bold text-cyan-400">
                        {value === null
                          ? "não informado"
                          : formatParam(value, slider.unit, slider.decimals)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={slider.min}
                      max={slider.max}
                      step={slider.step}
                      value={value ?? slider.min}
                      onChange={(e) =>
                        applyParameter(slider.key, parseFloat(e.target.value))
                      }
                      className="w-full accent-cyan-400 bg-slate-800 rounded-lg cursor-pointer"
                    />
                    {value === null && (
                      <p className="text-[10px] text-blue-300 mt-1">
                        Sem valor cadastrado — mover o controle informa o parâmetro.
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Verificações */}
          <div className="glass-panel rounded-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4 flex-wrap gap-3">
              <div>
                <h2 className="text-base font-bold text-white">
                  Resultado da verificação normativa
                </h2>
                <p className="text-xs text-slate-400">
                  Jurisdição {selectedProject.city_ibge} ({selectedProject.city_name}/
                  {selectedProject.state}) • Zona {selectedProject.zone} • Taxa de ocupação
                  derivada: {formatParam(selectedProject.occupancy_rate, "%", 1)}
                </p>
              </div>

              <button
                onClick={handleEmitReport}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
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
                      className={`p-5 rounded-xl border transition-all ${presentation.card}`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
                        <div className="flex items-center gap-3">
                          <h3 className="text-sm font-bold text-white">{rule.rule_title}</h3>
                        </div>
                        <StatusChip status={rule.status} />
                      </div>

                      <p className="text-xs text-slate-300 mb-3">{rule.details}</p>

                      <div className="pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                        <div>
                          <span className="text-slate-500 text-[11px] block">
                            Exigido pela regra:
                          </span>
                          <span className="font-mono text-slate-200 font-semibold">
                            {rule.expected_value}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 text-[11px] block">
                            Valor apurado:
                          </span>
                          <span className={`font-mono font-bold ${presentation.text}`}>
                            {rule.actual_value}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 text-[11px] block">
                            Fonte da regra:
                          </span>
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
  valueClass,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  accent: string;
  valueClass: string;
}) {
  return (
    <div
      className={`glass-panel p-5 rounded-2xl border-l-4 ${accent} flex items-center justify-between`}
    >
      <div>
        <p className="text-xs font-bold text-slate-400 uppercase">{label}</p>
        <p className={`text-2xl font-extrabold mt-1 ${valueClass}`}>{value}</p>
      </div>
      {icon}
    </div>
  );
}
