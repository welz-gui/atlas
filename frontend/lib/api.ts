/**
 * Cliente HTTP do Atlas.
 *
 * Duas regras deste módulo:
 *
 * 1. **Falha de rede nunca vira dado.** Toda função lança `ApiError` quando a
 *    requisição não é bem-sucedida, para que a interface mostre o problema. Um
 *    cliente que devolve lista vazia em caso de erro faz o usuário acreditar
 *    estar vendo o resultado da análise quando não está.
 * 2. **Toda chamada de negócio vai autenticada.** O token é anexado aqui, e um
 *    401 dispara o encerramento da sessão em vez de silenciar.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const TOKEN_STORAGE_KEY = "atlas.token";

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

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }
}

// --- Token -------------------------------------------------------------------

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request<T>(
  path: string,
  init?: RequestInit & { skipAuth?: boolean }
): Promise<T> {
  const { skipAuth, headers, ...rest } = init ?? {};
  const token = skipAuth ? null : getToken();

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      ...rest,
      headers: {
        ...(headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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

    // Sessão expirada ou token inválido: encerra em vez de deixar a interface
    // num limbo de telas vazias.
    if (response.status === 401 && !skipAuth) {
      setToken(null);
      onUnauthorized?.();
    }

    throw new ApiError(`A API respondeu ${response.status}.`, response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Tipos -------------------------------------------------------------------

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

export type UserRole =
  | "owner"
  | "admin"
  | "validator"
  | "engineer"
  | "inspector"
  | "client";

export type ProjectVersionState =
  | "estudo_preliminar"
  | "revisao_interna"
  | "protocolada"
  | "notificada"
  | "corrigida"
  | "aprovada"
  | "alteracao_em_obra"
  | "as_built";

export type ProtocolStatusValue =
  | "protocolado"
  | "em_analise"
  | "notificado"
  | "em_correcao"
  | "reprotocolado"
  | "aprovado"
  | "indeferido"
  | "arquivado";

export interface CurrentUser {
  id: string;
  organization_id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  document_number?: string;
  is_active: boolean;
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
  project_version_id?: string;
  project_version_number?: number;
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

/** Parâmetros urbanísticos. `null` = não informado; nunca zero. */
export interface ProjectVersion {
  id: string;
  project_id: string;
  version_number: number;
  state: ProjectVersionState;
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
  occupancy_rate: number | null;
  is_official_baseline: boolean;
  baseline_marked_at?: string | null;
  change_reason?: string | null;
  change_origin: string;
  content_hash?: string;
  created_by_id?: string | null;
  created_at: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  address?: string;
  address_number?: string;
  address_complement?: string;
  district?: string;
  postal_code?: string;
  city_ibge: string;
  city_name: string;
  state: string;
  latitude?: number | null;
  longitude?: number | null;
  lot?: string;
  block?: string;
  registry_number?: string;
  municipal_registration?: string;
  owner_name?: string;
  owner_document?: string;
  contractor_name?: string;
  technical_responsible_name?: string;
  technical_responsible_registry?: string;
  use_type?: string;
  units_count?: number | null;
  licensing_status: string;
  created_at: string;
  updated_at: string;
  current_version: ProjectVersion | null;
  official_baseline: ProjectVersion | null;
  validations: ValidationRecord[];
}

export interface RegulatoryRule {
  id: string;
  rule_key: string;
  jurisdiction: string;
  title: string;
  state: RuleState;
  severity: "bloqueio" | "alerta";
  applies_to: Record<string, unknown>;
  check: Record<string, unknown> | null;
  requires_manual_review: boolean;
  manual_review_reason?: string;
  evidence_required: string[];
  source_document_id?: string | null;
  source_document_label?: string | null;
  source_article?: string | null;
  effective_from?: string | null;
  effective_until?: string | null;
  validated_by_id?: string | null;
  validated_by_name?: string | null;
  validated_at?: string | null;
  notes?: string | null;
  catalog_version: string;
  is_executable: boolean;
  is_publishable: boolean;
  created_at: string;
  updated_at: string;
}

export interface RegulatoryDocument {
  id: string;
  jurisdiction: string;
  doc_type: string;
  number?: string;
  title: string;
  issuing_body?: string;
  url?: string;
  theme?: string;
  state: string;
  effective_from?: string;
  effective_until?: string;
  created_at: string;
}

export interface RegulatoryDiscoveryResult {
  jurisdiction: string;
  sources_checked: string[];
  candidates_found: number;
  created: number;
  updated: number;
  unchanged: number;
  document_ids: string[];
  requires_human_validation: boolean;
}

export interface RegulatoryDiscoveryJob {
  job: {
    id: string;
    job_type: "descoberta_regulatoria";
    status: "enfileirado" | "executando" | "concluido" | "falhou" | "cancelado";
    result?: RegulatoryDiscoveryResult;
    error?: string;
    executed_inline: boolean;
  };
  queue_backend: string;
}

export interface RuleValidationEvent {
  id: string;
  rule_id: string;
  from_state?: string;
  to_state: string;
  action: string;
  notes?: string;
  actor_name?: string;
  created_at: string;
}

export interface ProtocolRequirement {
  id: string;
  process_id: string;
  sequence: number;
  description: string;
  origin: string;
  raised_at?: string;
  due_date?: string;
  status: "aberta" | "em_correcao" | "respondida" | "atendida" | "nao_atendida";
  response_text?: string;
  responded_at?: string;
  resolved_at?: string;
  linked_rule_key?: string;
  was_predicted?: boolean | null;
  created_at: string;
}

export interface ProtocolEvent {
  id: string;
  process_id: string;
  event_type: string;
  from_status?: string;
  to_status?: string;
  description?: string;
  actor_name?: string;
  created_at: string;
}

export interface ProtocolProcess {
  id: string;
  project_id: string;
  project_version_id?: string;
  protocol_number: string;
  agency: string;
  process_type: string;
  status: ProtocolStatusValue;
  submitted_at?: string;
  decided_at?: string;
  notes?: string;
  open_requirements_count: number;
  created_at: string;
  updated_at: string;
  requirements: ProtocolRequirement[];
  events: ProtocolEvent[];
}

export interface PredictionAccuracy {
  total_requirements: number;
  linked_to_rules: number;
  predicted: number;
  not_predicted: number;
  recall_percent: number | null;
}

export interface DocumentItem {
  id: string;
  project_id: string;
  project_version_id?: string;
  title: string;
  category: string;
  version: string;
  file_path: string;
  original_filename?: string;
  content_type?: string;
  size_bytes?: number;
  hash_sha256?: string;
  status: string;
  supersedes_id?: string;
  superseded_at?: string;
  is_current: boolean;
  created_at: string;
}

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
  created_at: string;

  /** `rascunho` até alguém assinar (§8.12). */
  status: "rascunho" | "assinado";
  signed_by_name?: string | null;
  signed_at?: string | null;
  content_hash?: string | null;
  /**
   * `true` íntegra, `false` alterada depois de assinada, `null` **não
   * assinada** — ausência de assinatura não é adulteração.
   */
  signature_valid?: boolean | null;
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

export interface RegulatoryAnalysisReport {
  project_id: string;
  analysis_run_id: string;
  project_version_number?: number;
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

// --- Autenticação ------------------------------------------------------------

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const token = await request<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
  setToken(token.access_token);
  return fetchCurrentUser();
}

export async function signup(payload: {
  organization_name: string;
  organization_document?: string;
  name: string;
  email: string;
  password: string;
}): Promise<CurrentUser> {
  const token = await request<TokenResponse>("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    skipAuth: true,
  });
  setToken(token.access_token);
  return fetchCurrentUser();
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me");
}

export function fetchOrganization(): Promise<Organization> {
  return request<Organization>("/auth/organization");
}

export function logout(): void {
  setToken(null);
}

// --- Empreendimentos ---------------------------------------------------------

export function fetchProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function fetchProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${id}`);
}

export function createProject(payload: Record<string, unknown>): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateProjectIdentity(
  id: string,
  payload: Record<string, unknown>
): Promise<Project> {
  return request<Project>(`/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// --- Versões -----------------------------------------------------------------

export function fetchProjectVersions(projectId: string): Promise<ProjectVersion[]> {
  return request<ProjectVersion[]>(`/projects/${projectId}/versions`);
}

/**
 * Cria uma versão nova a partir da vigente. Não existe "editar parâmetro": a
 * versão anterior permanece intacta (§3.2).
 */
export function createProjectVersion(
  projectId: string,
  payload: Partial<ProjectVersion> & { change_reason?: string; state?: string }
): Promise<ProjectVersion> {
  return request<ProjectVersion>(`/projects/${projectId}/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function changeVersionState(
  projectId: string,
  versionId: string,
  state: ProjectVersionState,
  changeReason?: string
): Promise<ProjectVersion> {
  return request<ProjectVersion>(
    `/projects/${projectId}/versions/${versionId}/state`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state, change_reason: changeReason }),
    }
  );
}

export function markOfficialBaseline(
  projectId: string,
  versionId: string
): Promise<ProjectVersion> {
  return request<ProjectVersion>(
    `/projects/${projectId}/versions/${versionId}/baseline`,
    { method: "POST" }
  );
}

// --- Motor regulatório -------------------------------------------------------

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
 * Baixa o laudo como blob. O endpoint é somente leitura: devolve 409 se ainda
 * não houver análise registrada.
 */
export async function fetchReportPdf(
  projectId: string,
  runId?: string
): Promise<{ blob: Blob; isPublishable: boolean }> {
  const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const token = getToken();

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/projects/${projectId}/report/pdf${suffix}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new ApiError("Não foi possível falar com a API para emitir o laudo.", 0);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      `A API respondeu ${response.status}.`,
      response.status,
      body?.detail
    );
  }

  return {
    blob: await response.blob(),
    isPublishable: response.headers.get("X-Atlas-Publishable") === "true",
  };
}

// --- Catálogo regulatório ----------------------------------------------------

export function fetchCatalogRules(params?: {
  jurisdiction?: string;
  state?: RuleState;
}): Promise<RegulatoryRule[]> {
  const query = new URLSearchParams();
  if (params?.jurisdiction) query.set("jurisdiction", params.jurisdiction);
  if (params?.state) query.set("state", params.state);
  const suffix = query.toString() ? `?${query}` : "";
  return request<RegulatoryRule[]>(`/catalog/rules${suffix}`);
}

export function fetchValidationQueue(): Promise<RegulatoryRule[]> {
  return request<RegulatoryRule[]>("/catalog/validation-queue");
}

export function fetchRuleEvents(ruleId: string): Promise<RuleValidationEvent[]> {
  return request<RuleValidationEvent[]>(`/catalog/rules/${ruleId}/events`);
}

export function fetchRegulatoryDocuments(jurisdiction?: string): Promise<RegulatoryDocument[]> {
  const query = jurisdiction ? `?${new URLSearchParams({ jurisdiction })}` : "";
  return request<RegulatoryDocument[]>(`/catalog/documents${query}`);
}

export function createRegulatoryDocument(payload: {
  jurisdiction: string;
  title: string;
  doc_type?: string;
  number?: string;
  issuing_body?: string;
  url?: string;
}): Promise<RegulatoryDocument> {
  return request<RegulatoryDocument>("/catalog/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function discoverRegulatoryDocuments(
  jurisdiction: string,
  projectId?: string
): Promise<RegulatoryDiscoveryJob> {
  const query = new URLSearchParams({ jurisdiction });
  if (projectId) query.set("project_id", projectId);
  return request<RegulatoryDiscoveryJob>(`/catalog/jobs/discovery?${query}`, {
    method: "POST",
  });
}

export function validateRule(
  ruleId: string,
  payload: {
    action: "publicar" | "rejeitar" | "suspender" | "revogar" | "reabrir";
    notes?: string;
    source_document_id?: string;
    source_article?: string;
    effective_from?: string;
  }
): Promise<RegulatoryRule> {
  return request<RegulatoryRule>(`/catalog/rules/${ruleId}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// --- Tramitação --------------------------------------------------------------

export function fetchProtocols(projectId: string): Promise<ProtocolProcess[]> {
  return request<ProtocolProcess[]>(`/projects/${projectId}/protocols`);
}

export function createProtocol(
  projectId: string,
  payload: {
    protocol_number: string;
    agency?: string;
    process_type?: string;
    submitted_at?: string;
    notes?: string;
  }
): Promise<ProtocolProcess> {
  return request<ProtocolProcess>(`/projects/${projectId}/protocols`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function changeProtocolStatus(
  processId: string,
  payload: { status: ProtocolStatusValue; description?: string; decided_at?: string }
): Promise<ProtocolProcess> {
  return request<ProtocolProcess>(`/protocols/${processId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createRequirement(
  processId: string,
  payload: {
    description: string;
    origin?: string;
    raised_at?: string;
    due_date?: string;
    linked_rule_key?: string;
  }
): Promise<ProtocolRequirement> {
  return request<ProtocolRequirement>(`/protocols/${processId}/requirements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateRequirement(
  requirementId: string,
  payload: Partial<ProtocolRequirement>
): Promise<ProtocolRequirement> {
  return request<ProtocolRequirement>(`/requirements/${requirementId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchPredictionAccuracy(projectId: string): Promise<PredictionAccuracy> {
  return request<PredictionAccuracy>(`/projects/${projectId}/prediction-accuracy`);
}

// --- Documentos --------------------------------------------------------------

export function fetchProjectDocuments(
  projectId: string,
  includeObsolete = true
): Promise<DocumentItem[]> {
  return request<DocumentItem[]>(
    `/projects/${projectId}/documents?include_obsolete=${includeObsolete}`
  );
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

export function markDocumentObsolete(documentId: string): Promise<DocumentItem> {
  return request<DocumentItem>(`/documents/${documentId}/obsolete`, { method: "POST" });
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

// --- Planejamento ------------------------------------------------------------

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
    body: JSON.stringify(task),
  });
}

// --- Diário de obra ----------------------------------------------------------

export function signDailyLog(logId: string): Promise<DailyLogItem> {
  return request<DailyLogItem>(`/daily-logs/${logId}/sign`, { method: "POST" });
}

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
    // `status` não entra: assinatura é ato do servidor, em `signDailyLog`.
  }
): Promise<DailyLogItem> {
  return request<DailyLogItem>(`/projects/${projectId}/daily-logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(log),
  });
}

// --- Assistente --------------------------------------------------------------

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

// --- Formatação --------------------------------------------------------------

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

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/_/g, " ");
}

// --- Portal do cliente (§8.22) ----------------------------------------------

export interface PortalDocument {
  id: string;
  title: string;
  category: string;
  version: string;
  created_at: string;
}

export interface PortalRequirement {
  description: string;
  status: string;
  raised_at?: string | null;
  due_date?: string | null;
}

export interface PortalProtocol {
  protocol_number: string;
  agency: string;
  status: string;
  submitted_at?: string | null;
  decided_at?: string | null;
  open_requirements: PortalRequirement[];
}

export interface PortalMilestone {
  name: string;
  progress_percent: number;
}

/**
 * Resumo de conformidade.
 *
 * `available: false` **não** significa "sem análise": significa que a análise
 * depende de regras ainda em conferência técnica e por isso não pode ser
 * entregue ao cliente (§7.5). O `reason` diz qual dos dois casos é.
 */
export interface PortalCompliance {
  available: boolean;
  reason?: string | null;
  analysed_at?: string | null;
  project_version_number?: number | null;
  total_checks?: number | null;
  conforme_count?: number | null;
  pending_count?: number | null;
  blocking_count?: number | null;
}

export interface PortalProject {
  id: string;
  name: string;
  address?: string | null;
  district?: string | null;
  city_name: string;
  state: string;
  licensing_status: string;
  use_type?: string | null;
  units_count?: number | null;
  technical_responsible_name?: string | null;
  version_number?: number | null;
  version_state?: string | null;
  has_official_baseline: boolean;
  physical_progress_percent: number;
  milestones: PortalMilestone[];
  open_tasks: number;
  current_documents: PortalDocument[];
  protocols: PortalProtocol[];
  compliance: PortalCompliance;
  notice: string;
}

export function fetchPortalProjects(): Promise<PortalProject[]> {
  return request<PortalProject[]>("/portal/projects");
}

export function fetchPortalProject(projectId: string): Promise<PortalProject> {
  return request<PortalProject>(`/portal/projects/${projectId}`);
}
