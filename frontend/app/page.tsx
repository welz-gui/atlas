"use client";

import Link from "next/link";
import { 
  Building2, 
  CheckCircle2, 
  AlertTriangle, 
  HelpCircle, 
  ArrowUpRight, 
  ShieldCheck, 
  FileSpreadsheet,
  Clock,
  Sparkles
} from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-blue-900/40 via-slate-900 to-cyan-950/40 border border-blue-500/20 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Atlas AI Copilot</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Painel Geral dos Empreendimentos</h1>
          <p className="text-xs text-slate-400 mt-1">
            Conformidade legal, aprovação municipal e linha de base operacional em tempo real.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/approvals"
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
          >
            <ShieldCheck className="w-4 h-4" />
            Nova Pré-Análise Legal
          </Link>
        </div>
      </div>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="glass-panel p-5 rounded-2xl space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Empreendimentos</span>
            <Building2 className="w-5 h-5 text-blue-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-white">2</span>
            <span className="text-xs text-emerald-400 font-semibold flex items-center gap-0.5">
              <ArrowUpRight className="w-3 h-3" /> Ativos
            </span>
          </div>
          <p className="text-[11px] text-slate-500">Jurisdição: Lajeado / RS</p>
        </div>

        <div className="glass-panel p-5 rounded-2xl space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Regras Conformes</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-emerald-400">7</span>
            <span className="text-xs text-slate-400">de 9 checadas</span>
          </div>
          <p className="text-[11px] text-slate-500">Taxa de Ocupação & Gabarito OK</p>
        </div>

        <div className="glass-panel p-5 rounded-2xl space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Incompatibilidades</span>
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-amber-400">2</span>
            <span className="text-xs text-amber-400/80 font-medium">Requer atenção</span>
          </div>
          <p className="text-[11px] text-slate-500">Recuo frontal em Sol Nascente</p>
        </div>

        <div className="glass-panel p-5 rounded-2xl space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Não Verificáveis</span>
            <HelpCircle className="w-5 h-5 text-slate-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-slate-300">2</span>
            <span className="text-xs text-slate-400">NBR 9050</span>
          </div>
          <p className="text-[11px] text-slate-500">Aguardando arquivo de projeto</p>
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Active Projects Table */}
        <div className="lg:col-span-2 glass-panel rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-bold text-white">Empreendimentos em Licenciamento</h2>
              <p className="text-xs text-slate-400">Projetos sob análise prévia e aprovação municipal</p>
            </div>
            <Link href="/projects" className="text-xs text-cyan-400 hover:text-cyan-300 font-semibold">
              Ver todos →
            </Link>
          </div>

          <div className="space-y-3">
            {/* Project 1 */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-colors flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-sm">
                  RA
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Residencial das Acácias</h3>
                  <p className="text-xs text-slate-400">Zona Z2 • Lajeado-RS • 240 m²</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[11px] font-semibold">
                  100% Conforme
                </span>
                <Link href="/approvals" className="text-xs text-slate-400 hover:text-white">
                  Detalhes
                </Link>
              </div>
            </div>

            {/* Project 2 */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-colors flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold text-sm">
                  SN
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Residencial Sol Nascente</h3>
                  <p className="text-xs text-slate-400">Zona Z2 • Lajeado-RS • 220 m²</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] font-semibold">
                  Incompatibilidade (Recuo)
                </span>
                <Link href="/approvals" className="text-xs text-slate-400 hover:text-white">
                  Detalhes
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Regulatory Updates & Recent Actions */}
        <div className="glass-panel rounded-2xl p-6 space-y-4">
          <div className="border-b border-slate-800 pb-4">
            <h2 className="text-base font-bold text-white">Monitor Regulatório</h2>
            <p className="text-xs text-slate-400">Legislação e normas de Lajeado/RS</p>
          </div>

          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs space-y-1">
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-semibold text-cyan-400">Plano Diretor Lajeado</span>
                <span>Vigente</span>
              </div>
              <p className="text-slate-300">Lei Complementar nº 01/2026</p>
              <p className="text-[11px] text-slate-500">Última checagem autônoma: Hoje, 20:45</p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs space-y-1">
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-semibold text-blue-400">Código de Edificações</span>
                <span>Vigente</span>
              </div>
              <p className="text-slate-300">Recuos mínimos e taxa de ocupação Z2</p>
              <p className="text-[11px] text-slate-500">Validado por Responsável Técnico</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
