"use client";

import { useState, useEffect } from "react";
import { 
  FolderKanban, 
  Layers, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Plus, 
  User, 
  Calendar, 
  ChevronRight, 
  ChevronDown, 
  Sparkles,
  ArrowRight,
  ListTodo,
  Check
} from "lucide-react";
import { 
  fetchProjects, 
  fetchProjectEAP, 
  fetchProjectTasks, 
  updateTaskStatus, 
  createProjectTask, 
  Project, 
  EAPItem, 
  TaskItem 
} from "@/lib/api";

const MOCK_EAP: EAPItem[] = [
  { id: "eap-1", project_id: "acacias", code: "1.0", name: "1. Serviços Preliminares e Canteiro", item_type: "etapa", progress_percent: 100, created_at: new Date().toISOString() },
  { id: "eap-2", project_id: "acacias", code: "2.0", name: "2. Infraestrutura e Fundações", item_type: "etapa", progress_percent: 75, created_at: new Date().toISOString() },
  { id: "eap-2-1", project_id: "acacias", code: "2.1", name: "Escavação e Estacas", item_type: "subetapa", progress_percent: 100, parent_id: "eap-2", created_at: new Date().toISOString() },
  { id: "eap-2-2", project_id: "acacias", code: "2.2", name: "Blocos de Coroamento e Baldrame", item_type: "subetapa", progress_percent: 50, parent_id: "eap-2", created_at: new Date().toISOString() },
  { id: "eap-3", project_id: "acacias", code: "3.0", name: "3. Supraestrutura e Alvenaria", item_type: "etapa", progress_percent: 30, created_at: new Date().toISOString() },
  { id: "eap-4", project_id: "acacias", code: "4.0", name: "4. Instalações Hidrossanitárias e Elétricas", item_type: "etapa", progress_percent: 0, created_at: new Date().toISOString() },
  { id: "eap-5", project_id: "acacias", code: "5.0", name: "5. Acabamentos e Revestimentos", item_type: "etapa", progress_percent: 0, created_at: new Date().toISOString() },
];

const MOCK_TASKS: TaskItem[] = [
  {
    id: "task-1",
    project_id: "acacias",
    eap_item_id: "eap-2-2",
    title: "Concretagem das Vigas Baldrame (Eixo A-D)",
    description: "Agendar caminhão betoneira e laudo de resistência Fck 30 MPa.",
    status: "em_andamento",
    priority: "alta",
    assignee: "Eng. Carlos Silva",
    due_date: "12/08/2026",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "task-2",
    project_id: "acacias",
    eap_item_id: "eap-3",
    title: "Conferência de Aprumo de Pilares Térreo",
    description: "Verificar prumo de fôrmas e alinhamento de armaduras antes da concretagem.",
    status: "a_fazer",
    priority: "alta",
    assignee: "Mestre de Obras Roberto",
    due_date: "15/08/2026",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "task-3",
    project_id: "acacias",
    eap_item_id: "eap-1",
    title: "Instalação do Relógio de Água Provisório",
    description: "Solicitação à concessionária aprovada.",
    status: "concluido",
    priority: "media",
    assignee: "Eng. Carlos Silva",
    due_date: "01/08/2026",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: "task-4",
    project_id: "acacias",
    eap_item_id: "eap-4",
    title: "Cotação de Eletrodutos e Caixas de Passagem",
    description: "Fazer 3 orçamentos com fornecedores locais de Lajeado.",
    status: "a_fazer",
    priority: "baixa",
    assignee: "Compradora Ana",
    due_date: "20/08/2026",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

export default function PlanPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"kanban" | "eap">("kanban");
  
  const [eapItems, setEapItems] = useState<EAPItem[]>(MOCK_EAP);
  const [tasks, setTasks] = useState<TaskItem[]>(MOCK_TASKS);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // New task form state
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState<"alta" | "media" | "baixa">("media");
  const [newTaskAssignee, setNewTaskAssignee] = useState("");

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
    async function loadProjectPlan() {
      const [eap, taskList] = await Promise.all([
        fetchProjectEAP(selectedProjectId),
        fetchProjectTasks(selectedProjectId)
      ]);
      if (eap && eap.length > 0) setEapItems(eap);
      if (taskList && taskList.length > 0) setTasks(taskList);
    }
    loadProjectPlan();
  }, [selectedProjectId]);

  const handleTaskStatusChange = async (taskId: string, newStatus: "a_fazer" | "em_andamento" | "concluido") => {
    // Optimistic UI update
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: newStatus } : t));
    await updateTaskStatus(taskId, newStatus);
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle || !selectedProjectId) return;

    const created = await createProjectTask(selectedProjectId, {
      title: newTaskTitle,
      description: newTaskDesc,
      status: "a_fazer",
      priority: newTaskPriority,
      assignee: newTaskAssignee || "Engenheiro Responsável"
    });

    if (created) {
      setTasks(prev => [created, ...prev]);
    } else {
      const fallback: TaskItem = {
        id: `task-${Date.now()}`,
        project_id: selectedProjectId,
        title: newTaskTitle,
        description: newTaskDesc,
        status: "a_fazer",
        priority: newTaskPriority,
        assignee: newTaskAssignee || "Engenheiro Responsável",
        due_date: new Date().toLocaleDateString("pt-BR"),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
      setTasks(prev => [fallback, ...prev]);
    }

    setIsModalOpen(false);
    setNewTaskTitle("");
    setNewTaskDesc("");
  };

  const activeProject = projects.find(p => p.id === selectedProjectId);

  // Group tasks by Kanban column
  const todoTasks = tasks.filter(t => t.status === "a_fazer");
  const inProgressTasks = tasks.filter(t => t.status === "em_andamento");
  const doneTasks = tasks.filter(t => t.status === "concluido");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FolderKanban className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Atlas Plan • Módulo Operacional</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Planejamento, EAP & Tarefas de Obra</h1>
          <p className="text-xs text-slate-400 mt-1">
            Estrutura analítica do empreendimento, controle de avanço e Kanban executivo.
          </p>
        </div>

        {/* Project Switcher & View Tabs */}
        <div className="flex flex-wrap items-center gap-3">
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

          <div className="flex items-center gap-1 p-1.5 rounded-xl bg-slate-900 border border-slate-800">
            <button
              onClick={() => setActiveTab("kanban")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeTab === "kanban"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <ListTodo className="w-3.5 h-3.5" /> Quadro Kanban
            </button>
            <button
              onClick={() => setActiveTab("eap")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeTab === "eap"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Layers className="w-3.5 h-3.5" /> Árvore EAP
            </button>
          </div>
        </div>
      </div>

      {/* Main Tab Content */}
      {activeTab === "kanban" ? (
        <div className="space-y-6">
          {/* Action Header */}
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>Quadro de Controle Executivo</span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                {tasks.length} tarefa(s)
              </span>
            </h2>

            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" /> Nova Tarefa
            </button>
          </div>

          {/* Kanban 3-Column Layout */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Column 1: A Fazer */}
            <div className="glass-panel rounded-2xl p-4 border-slate-800 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-slate-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">A Fazer / Pendente</h3>
                </div>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400 font-bold font-mono">
                  {todoTasks.length}
                </span>
              </div>

              <div className="space-y-3">
                {todoTasks.map(task => (
                  <div key={task.id} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-xs font-bold text-white">{task.title}</h4>
                      <span className={`px-2 py-0.5 rounded text-[9px] font-extrabold uppercase shrink-0 ${
                        task.priority === "alta" ? "bg-amber-500/10 text-amber-400 border border-amber-500/30" : "bg-slate-800 text-slate-400"
                      }`}>
                        {task.priority}
                      </span>
                    </div>

                    {task.description && <p className="text-[11px] text-slate-400 line-clamp-2">{task.description}</p>}

                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400">
                      <span className="flex items-center gap-1"><User className="w-3 h-3 text-cyan-400" /> {task.assignee}</span>
                      <button
                        onClick={() => handleTaskStatusChange(task.id, "em_andamento")}
                        className="px-2 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-400 font-semibold flex items-center gap-1 transition-colors"
                      >
                        Iniciar <ArrowRight className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Column 2: Em Andamento */}
            <div className="glass-panel rounded-2xl p-4 border-cyan-500/30 glow-blue space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-bold text-cyan-400 uppercase tracking-wider">Em Andamento</h3>
                </div>
                <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-[10px] text-cyan-400 font-bold font-mono">
                  {inProgressTasks.length}
                </span>
              </div>

              <div className="space-y-3">
                {inProgressTasks.map(task => (
                  <div key={task.id} className="p-4 rounded-xl bg-slate-900/90 border border-cyan-500/30 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-xs font-bold text-white">{task.title}</h4>
                      <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-[9px] font-extrabold uppercase shrink-0">
                        {task.priority}
                      </span>
                    </div>

                    {task.description && <p className="text-[11px] text-slate-300">{task.description}</p>}

                    <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-400">
                      <span className="flex items-center gap-1"><User className="w-3 h-3 text-cyan-400" /> {task.assignee}</span>
                      <button
                        onClick={() => handleTaskStatusChange(task.id, "concluido")}
                        className="px-2.5 py-1 rounded bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-400 font-semibold flex items-center gap-1 transition-colors"
                      >
                        Concluir <Check className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Column 3: Concluído */}
            <div className="glass-panel rounded-2xl p-4 border-slate-800 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Concluído</h3>
                </div>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-[10px] text-emerald-400 font-bold font-mono">
                  {doneTasks.length}
                </span>
              </div>

              <div className="space-y-3">
                {doneTasks.map(task => (
                  <div key={task.id} className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 opacity-80 space-y-2">
                    <h4 className="text-xs font-bold text-slate-300 line-through">{task.title}</h4>
                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/60">
                      <span>{task.assignee}</span>
                      <span className="text-emerald-400 font-semibold">Finalizado</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* EAP Tree View */
        <div className="glass-panel rounded-2xl p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-bold text-white">Estrutura Analítica do Projeto (EAP)</h2>
              <p className="text-xs text-slate-400">Linha de base oficial dividida por etapas executivas e serviços</p>
            </div>
            <span className="text-xs text-slate-400 font-mono font-semibold">
              EAP Padrão • NBR 12721
            </span>
          </div>

          <div className="space-y-3">
            {eapItems.map(item => (
              <div
                key={item.id}
                className={`p-4 rounded-xl border transition-all ${
                  item.parent_id 
                    ? "ml-6 bg-slate-900/40 border-slate-800" 
                    : "bg-slate-900/80 border-slate-700"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-xs text-cyan-400 px-2 py-1 rounded bg-cyan-500/10 border border-cyan-500/20">
                      {item.code}
                    </span>
                    <h3 className={`text-sm font-bold ${item.parent_id ? 'text-slate-200' : 'text-white'}`}>
                      {item.name}
                    </h3>
                  </div>

                  <div className="flex items-center gap-4">
                    {/* Progress Bar */}
                    <div className="w-36 bg-slate-800 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-cyan-400 h-full rounded-full transition-all"
                        style={{ width: `${item.progress_percent}%` }}
                      />
                    </div>
                    <span className="font-mono text-xs font-bold text-slate-300 w-12 text-right">
                      {item.progress_percent}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Task Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-md rounded-2xl p-6 space-y-4 border border-cyan-500/30">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white">Criar Tarefa de Obra</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">Título da Tarefa:</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Concretagem das estacas eixo B"
                  value={newTaskTitle}
                  onChange={e => setNewTaskTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Descrição / Especificação:</label>
                <textarea
                  rows={3}
                  placeholder="Detalhes operacionais, traço de concreto, laudos..."
                  value={newTaskDesc}
                  onChange={e => setNewTaskDesc(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Prioridade:</label>
                  <select
                    value={newTaskPriority}
                    onChange={e => setNewTaskPriority(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  >
                    <option value="alta">Alta</option>
                    <option value="media">Média</option>
                    <option value="baixa">Baixa</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Responsável:</label>
                  <input
                    type="text"
                    placeholder="Engenheiro / Mestre"
                    value={newTaskAssignee}
                    onChange={e => setNewTaskAssignee(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>
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
                  Criar Tarefa
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
