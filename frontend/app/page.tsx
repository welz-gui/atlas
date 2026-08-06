"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  Building2,
  CheckCircle2,
  HelpCircle,
  Landmark,
  ScrollText,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";
import { formatParam, humanize } from "@/lib/api";
import { useProjects } from "@/lib/useProjects";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  StatusChip,
  UnvalidatedRulesBanner,
} from "@/components/StateViews";

/**
 * Painel geral.
 *
 * Todos os números vêm da API. O protótipo trazia indicadores fixos no JSX,
 * que pareciam medições reais do portfólio.
 */
export default function DashboardPage() {
  const { projects, isLoading, error, reload } = useProjects();

  const allValidations = projects.flatMap((p) => p.validations ?? []);
  const totals = {
    conforme: allValidations.filter((v) => v.status === "conforme").length,
    naoConforme: allValidations.filter((v) => v.status === "nao_conforme").length,
    atencao: allValidations.filter((v) => v.status === "atencao").length,
    naoVerificavel: allValidations.filter((v) => v.status === "nao_verificavel").length,
  };
  const hasUnvalidatedRules = allValidations.some((v) => !v.is_publishable);
  const withBaseline = projects.filter((p) => p.official_baseline).length;

  return (
    <div className="space-y-8">
      <div className="p-6 rounded-2xl bg-gradient-to-r from-blue-900/40 via-slate-900 to-cyan-950/40 border border-blue-500/20 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Atlas • Copiloto de Aprovação
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Painel geral dos empreendimentos</h1>
          <p className="text-xs text-slate-400 mt-1">
            Conformidade consolidada a partir da análise mais recente de cada
            empreendimento.
          </p>
        </div>

        <Link
          href="/approvals"
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
        >
          <ShieldCheck className="w-4 h-4" />
          Abrir pré-análise legal
        </Link>
      </div>

      {error && <ErrorBanner error={error} onRetry={reload} />}
      {isLoading && <LoadingState label="Carregando painel..." />}

      {!isLoading && !error && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para que o painel exiba indicadores de conformidade."
          action={
            <Link
              href="/projects"
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold"
            >
              Cadastrar empreendimento
            </Link>
          }
        />
      )}

      {!isLoading && !error && projects.length > 0 && (
        <>
          {hasUnvalidatedRules && <UnvalidatedRulesBanner />}

          <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
            <MetricCard
              label="Empreendimentos"
              value={projects.length}
              icon={<Building2 className="w-6 h-6 text-cyan-400/80" />}
              accent="border-l-cyan-500"
            />
            <MetricCard
              label="Com linha de base"
              value={withBaseline}
              icon={<Landmark className="w-6 h-6 text-cyan-400/80" />}
              accent="border-l-cyan-500"
            />
            <MetricCard
              label="Conformes"
              value={totals.conforme}
              icon={<CheckCircle2 className="w-6 h-6 text-emerald-400/80" />}
              accent="border-l-emerald-500"
              valueClass="text-emerald-400"
            />
            <MetricCard
              label="Não conformes"
              value={totals.naoConforme}
              icon={<XCircle className="w-6 h-6 text-red-400/80" />}
              accent="border-l-red-500"
              valueClass="text-red-400"
            />
            <MetricCard
              label="Atenção"
              value={totals.atencao}
              icon={<HelpCircle className="w-6 h-6 text-amber-400/80" />}
              accent="border-l-amber-500"
              valueClass="text-amber-400"
            />
            <MetricCard
              label="Não verificáveis"
              value={totals.naoVerificavel}
              icon={<HelpCircle className="w-6 h-6 text-blue-400/80" />}
              accent="border-l-blue-500"
              valueClass="text-blue-300"
            />
          </div>

          {hasUnvalidatedRules && (
            <Link
              href="/catalog"
              className="glass-panel rounded-2xl p-5 flex items-center justify-between gap-4 hover:border-cyan-500/30 transition-all"
            >
              <div className="flex items-center gap-3">
                <ScrollText className="w-5 h-5 text-amber-400 shrink-0" />
                <div>
                  <p className="text-sm font-bold text-white">
                    Há regras aguardando validação técnica
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Enquanto elas não forem conferidas, os laudos saem marcados como uso
                    interno.
                  </p>
                </div>
              </div>
              <ArrowUpRight className="w-4 h-4 text-cyan-400 shrink-0" />
            </Link>
          )}

          <div className="glass-panel rounded-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h2 className="text-base font-bold text-white">Situação por empreendimento</h2>
              <Link
                href="/projects"
                className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
              >
                Ver todos <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="space-y-3">
              {projects.map((project) => {
                const validations = project.validations ?? [];
                const blockers = validations.filter((v) => v.status === "nao_conforme");
                const pending = validations.filter((v) => v.status === "nao_verificavel");
                const worst = blockers[0] ?? pending[0] ?? validations[0];
                const version = project.current_version;

                return (
                  <div
                    key={project.id}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-white truncate">{project.name}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {project.city_name}/{project.state}
                        {version && ` • v${version.version_number} (${humanize(version.state)})`}
                        {version && ` • ocupação ${formatParam(version.occupancy_rate, "%", 1)}`}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        Licenciamento: {humanize(project.licensing_status)}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {validations.length === 0 ? (
                        <span className="text-[11px] text-slate-500 italic">
                          sem análise registrada
                        </span>
                      ) : (
                        <>
                          <span className="text-[11px] text-slate-400">
                            {blockers.length} bloqueio(s) · {pending.length} pendente(s)
                          </span>
                          {worst && <StatusChip status={worst.status} />}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({
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
      className={`glass-panel p-4 rounded-2xl border-l-4 ${accent} flex items-center justify-between gap-2`}
    >
      <div className="min-w-0">
        <p className="text-[10px] font-bold text-slate-400 uppercase truncate">{label}</p>
        <p className={`text-xl font-extrabold mt-1 ${valueClass}`}>{value}</p>
      </div>
      <div className="shrink-0">{icon}</div>
    </div>
  );
}
