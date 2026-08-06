"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Calendar,
  ClipboardList,
  Cloud,
  CloudRain,
  Plus,
  Sun,
  Users,
  X,
} from "lucide-react";
import {
  ApiError,
  DailyLogItem,
  createDailyLog,
  fetchProjectDailyLogs,
} from "@/lib/api";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

const WEATHER = {
  ensolarado: { label: "Ensolarado", icon: Sun, color: "text-amber-400" },
  nublado: { label: "Nublado", icon: Cloud, color: "text-slate-400" },
  chuvoso: { label: "Chuvoso", icon: CloudRain, color: "text-blue-400" },
  impraticavel: { label: "Impraticável", icon: AlertTriangle, color: "text-red-400" },
} as const;

export default function DailyLogPage() {
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    isLoading: isLoadingProjects,
    error: projectsError,
    reload: reloadProjects,
  } = useProjects();

  const [logs, setLogs] = useState<DailyLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadLogs = useCallback(async () => {
    if (!selectedProjectId) {
      setLogs([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setLogs(await fetchProjectDailyLogs(selectedProjectId));
    } catch (err) {
      setLogs([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Estágio 2 • Campo
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Diário de Obra</h1>
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

          <button
            onClick={() => setIsModalOpen(true)}
            disabled={!selectedProjectId}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-xs flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Novo registro
          </button>
        </div>
      </div>

      {projectsError && <ErrorBanner error={projectsError} onRetry={reloadProjects} />}
      {error && <ErrorBanner error={error} onRetry={loadLogs} />}
      {(isLoadingProjects || isLoading) && <LoadingState label="Carregando diário..." />}

      {!isLoadingProjects && !projectsError && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para registrar o diário de obra."
        />
      )}

      {!isLoading && !error && selectedProjectId && logs.length === 0 && (
        <EmptyState
          title="Nenhum registro no diário"
          description="Ainda não há registros para este empreendimento. Crie o primeiro registro do dia."
        />
      )}

      <div className="space-y-4">
        {logs.map((log) => {
          const weather = WEATHER[log.weather_condition] ?? WEATHER.nublado;
          const WeatherIcon = weather.icon;
          return (
            <div key={log.id} className="glass-panel rounded-2xl p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
                <div className="flex items-center gap-3">
                  <Calendar className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-bold text-white">{log.date}</span>
                  <span
                    className={`flex items-center gap-1.5 text-xs font-semibold ${weather.color}`}
                  >
                    <WeatherIcon className="w-3.5 h-3.5" /> {weather.label}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <Users className="w-3.5 h-3.5 text-slate-500" />
                    {log.manpower_own} próprios · {log.manpower_subcontracted} terceirizados
                  </span>
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    {log.status}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                  Atividades executadas
                </span>
                <p className="text-xs text-slate-200">{log.activities_done}</p>
              </div>

              {log.occurrences && (
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                    Ocorrências
                  </span>
                  <p className="text-xs text-amber-200/90">{log.occurrences}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {isModalOpen && selectedProjectId && (
        <NewLogModal
          projectId={selectedProjectId}
          onClose={() => setIsModalOpen(false)}
          onCreated={(log) => {
            setLogs((prev) => [log, ...prev]);
            setIsModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

function NewLogModal({
  projectId,
  onClose,
  onCreated,
}: {
  projectId: string;
  onClose: () => void;
  onCreated: (log: DailyLogItem) => void;
}) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [weather, setWeather] = useState<DailyLogItem["weather_condition"]>("ensolarado");
  const [manpowerOwn, setManpowerOwn] = useState("0");
  const [manpowerSub, setManpowerSub] = useState("0");
  const [activities, setActivities] = useState("");
  const [occurrences, setOccurrences] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!activities.trim()) return;

    setIsSaving(true);
    setError(null);
    try {
      const created = await createDailyLog(projectId, {
        date,
        weather_condition: weather,
        manpower_own: Number(manpowerOwn) || 0,
        manpower_subcontracted: Number(manpowerSub) || 0,
        activities_done: activities,
        occurrences: occurrences || undefined,
        status: "assinado",
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto">
      <div className="glass-panel rounded-2xl p-6 w-full max-w-lg space-y-5 my-8">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white">Novo registro de diário</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
            />
            <select
              value={weather}
              onChange={(e) =>
                setWeather(e.target.value as DailyLogItem["weather_condition"])
              }
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
            >
              {Object.entries(WEATHER).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="0"
              value={manpowerOwn}
              onChange={(e) => setManpowerOwn(e.target.value)}
              placeholder="Efetivo próprio"
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
            />
            <input
              type="number"
              min="0"
              value={manpowerSub}
              onChange={(e) => setManpowerSub(e.target.value)}
              placeholder="Efetivo terceirizado"
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
            />
          </div>

          <textarea
            value={activities}
            onChange={(e) => setActivities(e.target.value)}
            placeholder="Atividades executadas no dia"
            rows={4}
            required
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
          />
          <textarea
            value={occurrences}
            onChange={(e) => setOccurrences(e.target.value)}
            placeholder="Ocorrências (opcional)"
            rows={2}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
          />

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
    </div>
  );
}
