const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface Organization {
  id: string;
  name: string;
  document_number?: string;
  created_at: string;
}

export interface ValidationRecord {
  id: string;
  rule_id: string;
  rule_title: string;
  status: "conforme" | "nao_conforme" | "atencao" | "nao_verificavel";
  field: string;
  expected_value: string;
  actual_value: string;
  details?: string;
  source_citation?: string;
  validated_at: string;
}

export interface DocumentItem {
  id: string;
  project_id: string;
  title: string;
  category: string;
  version: string;
  file_path: string;
  hash_sha256?: string;
  status: string;
  created_at: string;
}

export interface ExtractedParameters {
  lot_area?: number;
  built_area?: number;
  front_setback?: number;
  rear_setback?: number;
  permeability_rate?: number;
  floors?: number;
  confidence_score: number;
  raw_matches: string[];
}

export interface ExtractionResponse {
  document_id: string;
  document_title: string;
  extracted_parameters: ExtractedParameters;
}

export interface EAPItem {
  id: string;
  project_id: string;
  code: string;
  name: string;
  item_type: string; // etapa, subetapa, servico
  progress_percent: number;
  parent_id?: string;
  created_at: string;
}

export interface TaskItem {
  id: string;
  project_id: string;
  eap_item_id?: string;
  title: string;
  description?: string;
  status: "a_fazer" | "em_andamento" | "concluido";
  priority: "alta" | "media" | "baixa";
  assignee?: string;
  due_date?: string;
  created_at: string;
  updated_at: string;
}

export interface DailyLogItem {
  id: string;
  project_id: string;
  date: string;
  weather_condition: "ensolarado" | "nublado" | "chuvoso" | "impraticavel";
  manpower_own: number;
  manpower_subcontracted: number;
  activities_done: string;
  occurrences?: string;
  status: string;
  created_at: string;
}

export interface AIChatResponse {
  answer: string;
  law_citations: string[];
  suggested_actions: string[];
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  city_ibge: string;
  city_name: string;
  state: string;
  zone: string;
  building_type: string;
  lot_area: number;
  built_area: number;
  floors: number;
  front_setback: number;
  side_setback: number;
  rear_setback: number;
  occupancy_rate: number;
  permeability_rate: number;
  parking_spaces: number;
  status: string;
  is_official_baseline: boolean;
  created_at: string;
  updated_at: string;
  validations: ValidationRecord[];
}

export async function fetchProjects(): Promise<Project[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects`, { cache: 'no-store' });
    if (!res.ok) throw new Error("Failed to fetch projects");
    return await res.json();
  } catch (err) {
    console.warn("FastAPI backend unreachable, fallback to initial state", err);
    return [];
  }
}

export async function updateProjectParameters(id: string, params: Partial<Project>): Promise<Project | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error("Failed to update project");
    return await res.json();
  } catch (err) {
    console.error("Error updating project:", err);
    return null;
  }
}

export async function fetchProjectDocuments(projectId: string): Promise<DocumentItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/documents`, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error("Error fetching documents:", err);
    return [];
  }
}

export async function uploadProjectDocument(
  projectId: string,
  formData: FormData
): Promise<DocumentItem | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error("Upload failed");
    return await res.json();
  } catch (err) {
    console.error("Error uploading document:", err);
    return null;
  }
}

export async function extractDocumentParameters(
  projectId: string,
  documentId: string
): Promise<ExtractionResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/documents/${documentId}/extract`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error("Extraction failed");
    return await res.json();
  } catch (err) {
    console.error("Error extracting document parameters:", err);
    return null;
  }
}

export function getProjectReportPDFUrl(projectId: string): string {
  return `${API_BASE_URL}/projects/${projectId}/report/pdf`;
}

export async function fetchProjectEAP(projectId: string): Promise<EAPItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/eap`, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error("Error fetching EAP:", err);
    return [];
  }
}

export async function fetchProjectTasks(projectId: string): Promise<TaskItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/tasks`, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error("Error fetching tasks:", err);
    return [];
  }
}

export async function fetchProjectDailyLogs(projectId: string): Promise<DailyLogItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/daily-logs`, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error("Error fetching daily logs:", err);
    return [];
  }
}

export async function createDailyLog(projectId: string, log: {
  date: string;
  weather_condition: string;
  manpower_own: number;
  manpower_subcontracted: number;
  activities_done: string;
  occurrences?: string;
  status?: string;
}): Promise<DailyLogItem | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/daily-logs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(log),
    });
    if (!res.ok) throw new Error("Failed to create daily log");
    return await res.json();
  } catch (err) {
    console.error("Error creating daily log:", err);
    return null;
  }
}

export async function updateTaskStatus(taskId: string, status: "a_fazer" | "em_andamento" | "concluido"): Promise<TaskItem | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error("Failed to update task status");
    return await res.json();
  } catch (err) {
    console.error("Error updating task status:", err);
    return null;
  }
}

export async function createProjectTask(projectId: string, task: {
  title: string;
  description?: string;
  status: string;
  priority: string;
  assignee?: string;
  due_date?: string;
  eap_item_id?: string;
}): Promise<TaskItem | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task),
    });
    if (!res.ok) throw new Error("Failed to create task");
    return await res.json();
  } catch (err) {
    console.error("Error creating task:", err);
    return null;
  }
}

export async function sendAIChatPrompt(prompt: string, projectId?: string): Promise<AIChatResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_id: projectId }),
    });
    if (!res.ok) throw new Error("AI chat request failed");
    return await res.json();
  } catch (err) {
    console.error("Error sending AI prompt:", err);
    return null;
  }
}

export async function createProject(project: {
  organization_id: string;
  name: string;
  description?: string;
  city_ibge?: string;
  city_name?: string;
  zone?: string;
  building_type?: string;
  lot_area: number;
  built_area: number;
  floors: number;
  front_setback: number;
  side_setback: number;
  rear_setback: number;
  occupancy_rate: number;
  permeability_rate?: number;
  parking_spaces?: number;
}): Promise<Project | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    });
    if (!res.ok) throw new Error("Failed to create project");
    return await res.json();
  } catch (err) {
    console.error("Error creating project:", err);
    return null;
  }
}
