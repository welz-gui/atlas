"use client";

import { useState, useEffect } from "react";
import { 
  ClipboardList, 
  Sun, 
  Cloud, 
  CloudRain, 
  AlertTriangle, 
  Users, 
  Plus, 
  CheckCircle2, 
  Calendar, 
  Building2, 
  FileCheck,
  ShieldCheck
} from "lucide-react";
import { 
  fetchProjects, 
  fetchProjectDailyLogs, 
  createDailyLog, 
  Project, 
  DailyLogItem 
} from "@/lib/api";

const MOCK_DAILY_LOGS: DailyLogItem[] = [
  {
    id: "log-1",
    project_id: "acacias",
    date: "05/08/2026",
    weather_condition: "ensolarado",
    manpower_own: 6,
    manpower_subcontracted: 8,
    activities_done: "Finalizada escavação das estacas do eixo B-C. Montagem das fôrmas do baldrame.",
    occurrences: "Atraso de 30 minutos na entrega das barras de aço de 12mm.",
    status: "assinado",
    created_at: new Date().toISOString()
  },
  {
    id: "log-2",
    project_id: "acacias",
    date: "04/08/2026",
    weather_condition: "nublado",
    manpower_own: 6,
    manpower_subcontracted: 5,
    activities_done: "Marcação gabarito de obra e nivelamento topográfico do lote.",
    occurrences: "Nenhuma ocorrência registrada no dia.",
    status: "assinado",
    created_at: new Date().toISOString()
  }
];

export default function DailyLogPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [dailyLogs, setDailyLogs] = useState<DailyLogItem[]>(MOCK_DAILY_LOGS);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form State
  const [dateStr, setDateStr] = useState(new Date().toLocaleDateString("pt-BR"));
  const [weather, setWeather] = useState<"ensolarado" | "nublado" | "chuvoso" | "impraticavel">("ensolarado");
  const [manpowerOwn, setManpowerOwn] = useState(6);
  const [manpowerSub, setManpowerSub] = useState(8);
  const [activitiesDone, setActivitiesDone] = useState("");
  const [occurrences, setOccurrences] = useState("");

  useEffect(() => {
    async function loadData() {
      const data = await fetchProjects();
      if (data && data.length > 0) {
        setProjects(data);
        setSelectedProjectId(data[0].id);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    async function loadLogs() {
      const logs = await fetchProjectDailyLogs(selectedProjectId);
      if (logs && logs.length > 0) {
        setDailyLogs(logs);
      }
    }
    loadLogs();
  }, [selectedProjectId]);

  const handleCreateLog = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activitiesDone || !selectedProjectId) return;

    const created = await createDailyLog(selectedProjectId, {
      date: dateStr,
      weather_condition: weather,
      manpower_own: manpowerOwn,
      manpower_subcontracted: manpowerSub,
      activities_done: activitiesDone,
      occurrences: occurrences || "Sem ocorrências registradas."
    });

    if (created) {
      setDailyLogs(prev => [created, ...prev]);
    } else {
      const fallback: DailyLogItem = {
        id: `log-${Date.now()}`,
        project_id: selectedProjectId,
        date: dateStr,
        weather_condition: weather,
        manpower_own: manpowerOwn,
        manpower_subcontracted: manpowerSub,
        activities_done: activitiesDone,
        occurrences: occurrences || "Sem ocorrências registradas.",
        status: "assinado",
        created_at: new Date().toISOString()
      };
      setDailyLogs(prev => [fallback, ...prev]);
    }

    setIsModalOpen(false);
    setActivitiesDone("");
    setOccurrences("");
  };

  const activeProject = projects.find(p => p.id === selectedProjectId);

  const getWeatherBadge = (cond: string) => {
    switch (cond) {
      case "ensolarado":
        return <span className="px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[10px] font-extrabold flex items-center gap-1"><Sun className="w-3 h-3 text-amber-400" /> Sol / Bom</span>;
      case "nublado":
        return <span className="px-2.5 py-1 rounded-full bg-slate-500/10 border border-slate-500/30 text-slate-300 text-[10px] font-extrabold flex items-center gap-1"><Cloud className="w-3 h-3 text-slate-400" /> Nublado</span>;
      case "chuvoso":
        return <span className="px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-[10px] font-extrabold flex items-center gap-1"><CloudRain className="w-3 h-3 text-cyan-400" /> Chuva</span>;
      default:
        return <span className="px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-[10px] font-extrabold flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Impraticável</span>;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Módulo Executivo • Campo & Diário de Obra</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Diário de Obra Digital</h1>
          <p className="text-xs text-slate-400 mt-1">
            Registro diário de efetivo, condições climáticas, atividades executadas e ocorrências do canteiro.
          </p>
        </div>

        {/* Project Switcher */}
        {projects.length > 0 && (
          <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800">
            {projects.map(p => (
              <button
                key={p.id}
                onClick={() => setSelectedProjectId(p.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  selectedProjectId === p.id
                    ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold shadow-md shadow-cyan-500/20"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {p.name.split(" ")[0]} {p.name.split(" ")[1] || ""}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Overview Action Banner */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <span>Histórico de Registros de Campo</span>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
            {dailyLogs.length} registro(s)
          </span>
        </h2>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> Novo Registro de Diário
        </button>
      </div>

      {/* Daily Logs Timeline */}
      <div className="space-y-4">
        {dailyLogs.map(log => (
          <div key={log.id} className="glass-panel rounded-2xl p-6 space-y-4 border-slate-800 hover:border-cyan-500/30 transition-all">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono font-extrabold text-xs flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5" />
                  {log.date}
                </div>
                {getWeatherBadge(log.weather_condition)}
              </div>

              <div className="flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1 text-slate-300">
                  <Users className="w-3.5 h-3.5 text-cyan-400" />
                  <b>{log.manpower_own + log.manpower_subcontracted}</b> trabalhadores ({log.manpower_own} próprios / {log.manpower_subcontracted} ter)
                </span>

                <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-extrabold uppercase flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  Assinado
                </span>
              </div>
            </div>

            {/* Activities & Occurrences */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 font-bold uppercase text-[10px] flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Atividades Executadas no Dia:
                </span>
                <p className="text-slate-200 leading-relaxed">{log.activities_done}</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 font-bold uppercase text-[10px] flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Ocorrências & Observações:
                </span>
                <p className="text-slate-300 leading-relaxed">{log.occurrences || "Nenhuma ocorrência."}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Modal Novo Diário */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-lg rounded-2xl p-6 space-y-4 border border-cyan-500/30">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white">Novo Registro no Diário de Obra</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateLog} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Data do Registro:</label>
                  <input
                    type="text"
                    required
                    value={dateStr}
                    onChange={e => setDateStr(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Condição do Tempo / Clima:</label>
                  <select
                    value={weather}
                    onChange={e => setWeather(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  >
                    <option value="ensolarado">Ensolarado / Bom</option>
                    <option value="nublado">Nublado</option>
                    <option value="chuvoso">Chuvoso</option>
                    <option value="impraticavel">Impraticável (Paralisação)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Efetivo Próprio (Pessoas):</label>
                  <input
                    type="number"
                    min="0"
                    value={manpowerOwn}
                    onChange={e => setManpowerOwn(parseInt(e.target.value) || 0)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Efetivo Terceirizado (Pessoas):</label>
                  <input
                    type="number"
                    min="0"
                    value={manpowerSub}
                    onChange={e => setManpowerSub(parseInt(e.target.value) || 0)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Atividades Executadas:</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Descrição dos serviços realizados no canteiro hoje..."
                  value={activitiesDone}
                  onChange={e => setActivitiesDone(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Ocorrências / Atrasos / Problemas:</label>
                <textarea
                  rows={2}
                  placeholder="Atraso de insumos, chuva pesada, acidentes ou interrupções..."
                  value={occurrences}
                  onChange={e => setOccurrences(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                />
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold shadow-md shadow-cyan-500/20"
                >
                  Assinar e Salvar Registro
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
