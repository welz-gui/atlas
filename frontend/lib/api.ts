/**
 * Cliente HTTP do Atlas.
 *
 * Regra deste módulo: **falha de rede nunca vira dado**. Toda função lança
 * `ApiError` quando a requisição não é bem-sucedida, para que a interface
 * mostre o problema ao usuário. O protótipo devolvia listas vazias e valores
 * de exemplo em caso de erro — num produto de conformidade legal, isso faz o
 * usuário acreditar estar vendo o resultado da análise quando não está.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** Verdadeiro quando o backend não pôde ser alcançado. */
  get isOffline(): boolean {
    return this.status === 0;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      ...init,
    });
  } catch (cause) {
    throw new ApiError(
      "Não foi possível falar com a API do Atlas. Verifique se o backend está em execução.",
      0,
      cause instanceof Error ? cause.message : undefined
    );
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = await response.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      detail = await response.text().catch(() => undefined);
    }
    throw new ApiError(`A API respondeu ${response.status}.`, response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Tipos -----------------------------------------------------------------

export type CheckStatus =
  | "conforme"
  | "nao_conforme"
  | "atencao"
  | "nao_aplicavel"
  | "nao_verificavel";

export type RuleState =
  | "rascunho_extraido_por_ia"
  | "em_validacao"
  | "vigente"
  | "suspensa"
  | "revogada"
  | "substituida";

export interface Organization {
  id: string;
  name: string;
  document_number?: string;
  created_at: string;
}

export interface ValidationRecord {
  id: string;
  analysis_run_id: string;
  rule_id: string;
  rule_title: string;
  status: CheckStatus;
  field: string;
  expected_value: string;
  actual_value: string;
  details?: string;
  rule_state: RuleState;
  severity: "bloqueio" | "alerta";
  method: string;
  source_document?: string;
  source_article?: string;
  source_citation?: string;
  source_is_verified: boolean;
  evidence_required?: string;
  validated_by?: string;
  is_publishable: boolean;
  validated_at: string;
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  jurisdiction: string;
  catalog_version: string;
  engine_version: string;
  trigger: string;
  total_checks: number;
  conforme_count: number;
  nao_conforme_count: number;
  atencao_count: number;
  nao_verificavel_count: number;
  is_publishable: boolean;
  content_hash?: string;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  project_id: string;
  title: string;
  category: string;
  version: string;
  file_path: string;
  original_filename?: string;
  content_type?: string;
  size_bytes?: number;
  hash_sha256?: string;
  status: string;
  created_at: string;
}

/** Um parâmetro ausente vem `null`: não foi extraído, não é zero. */
export interface ExtractedParameters {
  lot_area: number | null;
  built_area: number | null;
  front_setback: number | null;
  rear_setback: number | null;
  permeability_rate: number | null;
  floors: number | null;
}

export interface ExtractionResponse {
  document_id: string;
  document_title: string;
  status: "extraido" | "extraido_parcial" | "nao_verificavel";
  fields_found: number;
  fields_expected: number;
  extracted_parameters: ExtractedParameters;
  evidence: string[];
  warnings: string[];
}

export interface EAPItem {
  id: string;
  project_id: string;
  code: string;
  name: string;
  item_type: string;
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
  disclaimer: string;
  is_ai_generated: boolean;
  method: string;
  matched_rules: string[];
}

/**
 * Parâmetros urbanísticos são `number | null`. `null` significa "não
 * informado" e produz verificação `nao_verificavel` — nunca use 0 no lugar.
 */
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
  lot_area: number | null;
  built_area: number | null;
  floors: number | null;
  front_setback: number | null;
  side_setback: number | null;
  rear_setback: number | null;
  permeability_rate: number | null;
  parking_spaces: number | null;
  /** Derivada no servidor (área construída ÷ área do lote). Somente leitura. */
  occupancy_rate: number | null;
  status: string;
  is_official_baseline: boolean;
  created_at: string;
  updated_at: string;
  validations: ValidationRecord[];
}

export interface RegulatoryAnalysisReport {
  project_id: string;
  analysis_run_id: string;
  catalog_version: string;
  engine_version: string;
  total_checks: number;
  conforme_count: number;
  nao_conforme_count: number;
  atencao_count: number;
  nao_verificavel_count: number;
  is_publishable: boolean;
  content_hash?: string;
  results: ValidationRecord[];
}

// --- Empreendimentos -------------------------------------------------------

export function fetchProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function fetchProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${id}`);
}

export function updateProjectParameters(
  id: string,
  params: Partial<Project>
): Promise<Project> {
  return request<Project>(`/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export function createProject(project: {
  organization_id: string;
  name: string;
  description?: string;
  city_ibge?: string;
  city_name?: string;
  zone?: string;
  building_type?: string;
  lot_area?: number | null;
  built_area?: number | null;
  floors?: number | null;
  front_setback?: number | null;
  side_setback?: number | null;
  rear_setback?: number | null;
  permeability_rate?: number | null;
  parking_spaces?: number | null;
}): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project),
  });
}

export function fetchOrganizations(): Promise<Organization[]> {
  return request<Organization[]>("/organizations");
}

// --- Motor regulatório -----------------------------------------------------

export function evaluateProject(projectId: string): Promise<RegulatoryAnalysisReport> {
  return request<RegulatoryAnalysisReport>(`/projects/${projectId}/evaluate`, {
    method: "POST",
  });
}

export function fetchProjectValidations(projectId: string): Promise<ValidationRecord[]> {
  return request<ValidationRecord[]>(`/projects/${projectId}/validations`);
}

export function fetchAnalysisRuns(projectId: string): Promise<AnalysisRun[]> {
  return request<AnalysisRun[]>(`/projects/${projectId}/analysis-runs`);
}

/**
 * URL do laudo. O endpoint é somente leitura: renderiza a análise mais
 * recente e devolve 409 se ainda não houver nenhuma.
 */
export function getProjectReportPDFUrl(projectId: string, runId?: string): string {
  const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return `${API_BASE_URL}/projects/${projectId}/report/pdf${suffix}`;
}

// --- Documentos ------------------------------------------------------------

export function fetchProjectDocuments(projectId: string): Promise<DocumentItem[]> {
  return request<DocumentItem[]>(`/projects/${projectId}/documents`);
}

export function uploadProjectDocument(
  projectId: string,
  formData: FormData
): Promise<DocumentItem> {
  return request<DocumentItem>(`/projects/${projectId}/documents/upload`, {
    method: "POST",
    body: formData,
  });
}

export function extractDocumentParameters(
  projectId: string,
  documentId: string
): Promise<ExtractionResponse> {
  return request<ExtractionResponse>(
    `/projects/${projectId}/documents/${documentId}/extract`,
    { method: "POST" }
  );
}

// --- Planejamento ----------------------------------------------------------

export function fetchProjectEAP(projectId: string): Promise<EAPItem[]> {
  return request<EAPItem[]>(`/projects/${projectId}/eap`);
}

export function fetchProjectTasks(projectId: string): Promise<TaskItem[]> {
  return request<TaskItem[]>(`/projects/${projectId}/tasks`);
}

export function updateTaskStatus(
  taskId: string,
  status: TaskItem["status"]
): Promise<TaskItem> {
  return request<TaskItem>(`/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export function createProjectTask(
  projectId: string,
  task: {
    title: string;
    description?: string;
    status: string;
    priority: string;
    assignee?: string;
    due_date?: string;
    eap_item_id?: string;
  }
): Promise<TaskItem> {
  return request<TaskItem>(`/projects/${projectId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...task, project_id: projectId }),
  });
}

// --- Diário de obra --------------------------------------------------------

export function fetchProjectDailyLogs(projectId: string): Promise<DailyLogItem[]> {
  return request<DailyLogItem[]>(`/projects/${projectId}/daily-logs`);
}

export function createDailyLog(
  projectId: string,
  log: {
    date: string;
    weather_condition: string;
    manpower_own: number;
    manpower_subcontracted: number;
    activities_done: string;
    occurrences?: string;
    status?: string;
  }
): Promise<DailyLogItem> {
  return request<DailyLogItem>(`/projects/${projectId}/daily-logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...log, project_id: projectId }),
  });
}

// --- Assistente ------------------------------------------------------------

export function sendAIChatPrompt(
  prompt: string,
  projectId?: string
): Promise<AIChatResponse> {
  return request<AIChatResponse>("/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, project_id: projectId }),
  });
}

// --- Formatação ------------------------------------------------------------

/** Formata um parâmetro que pode não ter sido informado. */
export function formatParam(
  value: number | null | undefined,
  unit = "",
  decimals = 2
): string {
  if (value === null || value === undefined) return "não informado";
  const sep = unit === "%" ? "" : " ";
  return `${value.toFixed(decimals)}${sep}${unit}`.trim();
}
