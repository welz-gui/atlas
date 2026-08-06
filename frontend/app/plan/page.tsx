"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Calendar,
  FolderKanban,
  Layers,
  ListTodo,
  Plus,
  User,
  X,
} from "lucide-react";
import {
  ApiError,
  EAPItem,
  TaskItem,
  createProjectTask,
  fetchProjectEAP,
  fetchProjectTasks,
  updateTaskStatus,
} from "@/lib/api";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

const COLUMNS: { key: TaskItem["status"]; title: string; accent: string }[] = [
  { key: "a_fazer", title: "A fazer", accent: "border-t-slate-500" },
  { key: "em_andamento", title: "Em andamento", accent: "border-t-cyan-500" },
  { key: "concluido", title: "Concluído", accent: "border-t-emerald-500" },
];

const PRIORITY_STYLE: Record<TaskItem["priority"], string> = {
  alta: "bg-red-500/10 text-red-400 border-red-500/30",
  media: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  baixa: "bg-slate-800 text-slate-400 border-slate-700",
};

export default function PlanPage() {
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    isLoading: isLoadingProjects,
    error: projectsError,
    reload: reloadProjects,
  } = useProjects();

  const [activeTab, setActiveTab] = useState<"kanban" | "eap">("kanban");
  const [eapItems, setEapItems] = useState<EAPItem[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadPlan = useCallback(async () => {
    if (!selectedProjectId) {
      setEapItems([]);
      setTasks([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [eap, taskList] = await Promise.all([
        fetchProjectEAP(selectedProjectId),
        fetchProjectTasks(selectedProjectId),
      ]);
      setEapItems(eap);
      setTasks(taskList);
    } catch (err) {
      setEapItems([]);
      setTasks([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  const handleMoveTask = async (task: TaskItem, status: TaskItem["status"]) => {
    const previous = tasks;
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status } : t)));
    try {
      const updated = await updateTaskStatus(task.id, status);
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch (err) {
      // Reverte: o quadro não pode exibir um estado que o servidor não aceitou.
      setTasks(previous);
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FolderKanban className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Estágio 2 • Núcleo operacional
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Planejamento e EAP</h1>
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

      {projectsError && <ErrorBanner error={projectsError} onRetry={reloadProjects} />}
      {error && <ErrorBanner error={error} onRetry={loadPlan} />}

      {(isLoadingProjects || isLoading) && <LoadingState label="Carregando planejamento..." />}

      {!isLoadingProjects && !projectsError && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para montar a EAP e o quadro de tarefas."
        />
      )}

      {!isLoading && !error && selectedProjectId && (
        <>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800">
              <TabButton
                active={activeTab === "kanban"}
                onClick={() => setActiveTab("kanban")}
                icon={<ListTodo className="w-3.5 h-3.5" />}
                label="Quadro de tarefas"
              />
              <TabButton
                active={activeTab === "eap"}
                onClick={() => setActiveTab("eap")}
                icon={<Layers className="w-3.5 h-3.5" />}
                label="EAP"
              />
            </div>

            {activeTab === "kanban" && (
              <button
                onClick={() => setIsModalOpen(true)}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-xs flex items-center gap-2"
              >
                <Plus className="w-4 h-4" /> Nova tarefa
              </button>
            )}
          </div>

          {activeTab === "kanban" &&
            (tasks.length === 0 ? (
              <EmptyState
                title="Nenhuma tarefa neste empreendimento"
                description="Crie a primeira tarefa para começar a acompanhar a execução."
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {COLUMNS.map((column) => {
                  const columnTasks = tasks.filter((t) => t.status === column.key);
                  return (
                    <div
                      key={column.key}
                      className={`glass-panel rounded-2xl p-4 border-t-4 ${column.accent} space-y-3`}
                    >
                      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                        <h3 className="text-xs font-bold text-white uppercase tracking-wide">
                          {column.title}
                        </h3>
                        <span className="text-[11px] font-mono text-slate-400">
                          {columnTasks.length}
                        </span>
                      </div>

                      {columnTasks.map((task) => (
                        <div
                          key={task.id}
                          className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-xs font-bold text-white">{task.title}</p>
                            <span
                              className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase border shrink-0 ${
                                PRIORITY_STYLE[task.priority]
                              }`}
                            >
                              {task.priority}
                            </span>
                          </div>
                          {task.description && (
                            <p className="text-[11px] text-slate-400">{task.description}</p>
                          )}
                          <div className="flex items-center gap-3 text-[10px] text-slate-500">
                            {task.assignee && (
                              <span className="flex items-center gap-1">
                                <User className="w-3 h-3" /> {task.assignee}
                              </span>
                            )}
                            {task.due_date && (
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" /> {task.due_date}
                              </span>
                            )}
                          </div>
                          <div className="flex gap-1.5 pt-1">
                            {COLUMNS.filter((c) => c.key !== task.status).map((target) => (
                              <button
                                key={target.key}
                                onClick={() => handleMoveTask(task, target.key)}
                                className="px-2 py-1 rounded-md text-[10px] font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300"
                              >
                                → {target.title}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            ))}

          {activeTab === "eap" &&
            (eapItems.length === 0 ? (
              <EmptyState
                title="EAP não estruturada"
                description="Nenhum item de EAP cadastrado para este empreendimento."
              />
            ) : (
              <div className="glass-panel rounded-2xl p-6 space-y-3">
                {eapItems.map((item) => (
                  <div
                    key={item.id}
                    className={`p-4 rounded-xl bg-slate-900/60 border border-slate-800 ${
                      item.parent_id ? "ml-8" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-cyan-400 font-bold">
                          {item.code}
                        </span>
                        <span className="text-xs font-semibold text-white">{item.name}</span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        {item.progress_percent.toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                        style={{ width: `${Math.min(100, item.progress_percent)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ))}
        </>
      )}

      {isModalOpen && selectedProjectId && (
        <NewTaskModal
          projectId={selectedProjectId}
          eapItems={eapItems}
          onClose={() => setIsModalOpen(false)}
          onCreated={(task) => {
            setTasks((prev) => [task, ...prev]);
            setIsModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
        active
          ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold"
          : "text-slate-400 hover:text-white"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function NewTaskModal({
  projectId,
  eapItems,
  onClose,
  onCreated,
}: {
  projectId: string;
  eapItems: EAPItem[];
  onClose: () => void;
  onCreated: (task: TaskItem) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskItem["priority"]>("media");
  const [assignee, setAssignee] = useState("");
  const [eapItemId, setEapItemId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;

    setIsSaving(true);
    setError(null);
    try {
      const created = await createProjectTask(projectId, {
        title,
        description: description || undefined,
        status: "a_fazer",
        priority,
        assignee: assignee || undefined,
        eap_item_id: eapItemId || undefined,
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="glass-panel rounded-2xl p-6 w-full max-w-lg space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white">Nova tarefa</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título da tarefa"
            required
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Descrição (opcional)"
            rows={3}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
          />
          <div className="grid grid-cols-2 gap-3">
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskItem["priority"])}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
            >
              <option value="alta">Prioridade alta</option>
              <option value="media">Prioridade média</option>
              <option value="baixa">Prioridade baixa</option>
            </select>
            <input
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              placeholder="Responsável"
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
            />
          </div>
          {eapItems.length > 0 && (
            <select
              value={eapItemId}
              onChange={(e) => setEapItemId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
            >
              <option value="">Sem vínculo com a EAP</option>
              {eapItems.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} — {item.name}
                </option>
              ))}
            </select>
          )}

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
              {isSaving ? "Salvando..." : "Criar tarefa"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
