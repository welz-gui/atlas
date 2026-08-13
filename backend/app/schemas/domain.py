from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Any, Dict, List, Optional
from datetime import datetime

# =============================================================================
# Autenticação e organização
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str = "engineer"


class UserCreate(UserBase):
    password: str = Field(min_length=10, description="Mínimo de 10 caracteres.")


class UserResponse(UserBase):
    id: str
    organization_id: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrganizationBase(BaseModel):
    name: str
    document_number: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: str
    is_active: bool = True
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SignupRequest(BaseModel):
    """Cria organização e o primeiro usuário (papel `owner`)."""

    organization_name: str
    organization_document: Optional[str] = None
    name: str
    email: EmailStr
    password: str = Field(min_length=10)


# =============================================================================
# Versões de projeto
# =============================================================================

class ProjectParameters(BaseModel):
    """Parâmetros urbanísticos.

    `None` significa "não informado" e produz verificação `nao_verificavel`.
    Nunca use 0 como valor padrão — zero é uma medida, ausência não é.
    """

    zone: Optional[str] = None
    building_type: Optional[str] = None
    lot_area: Optional[float] = None
    built_area: Optional[float] = None
    floors: Optional[int] = None
    front_setback: Optional[float] = None
    side_setback: Optional[float] = None
    rear_setback: Optional[float] = None
    permeability_rate: Optional[float] = None
    parking_spaces: Optional[int] = None


class ProjectVersionCreate(ProjectParameters):
    change_reason: Optional[str] = None
    state: Optional[str] = None


class ProjectVersionResponse(BaseModel):
    id: str
    project_id: str
    version_number: int
    state: str
    zone: str
    building_type: str
    lot_area: Optional[float] = None
    built_area: Optional[float] = None
    floors: Optional[int] = None
    front_setback: Optional[float] = None
    side_setback: Optional[float] = None
    rear_setback: Optional[float] = None
    permeability_rate: Optional[float] = None
    parking_spaces: Optional[int] = None
    occupancy_rate: Optional[float] = None
    is_official_baseline: bool
    baseline_marked_at: Optional[datetime] = None
    change_reason: Optional[str] = None
    change_origin: str
    content_hash: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VersionStateChange(BaseModel):
    state: str
    change_reason: Optional[str] = None


# =============================================================================
# Empreendimento
# =============================================================================

class ProjectIdentity(BaseModel):
    """Campos de identidade e localização do empreendimento (§8.2)."""

    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    district: Optional[str] = None
    postal_code: Optional[str] = None
    city_ibge: str = "BR-RS-4311403"
    city_name: str = "Lajeado"
    state: str = "RS"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    lot: Optional[str] = None
    block: Optional[str] = None
    registry_number: Optional[str] = None
    municipal_registration: Optional[str] = None
    owner_name: Optional[str] = None
    owner_document: Optional[str] = None
    contractor_name: Optional[str] = None
    technical_responsible_name: Optional[str] = None
    technical_responsible_registry: Optional[str] = None
    use_type: Optional[str] = None
    units_count: Optional[int] = None


class ProjectCreate(ProjectIdentity, ProjectParameters):
    """Cria o empreendimento e a versão 1 em uma única chamada."""


class ProjectUpdate(BaseModel):
    """Atualiza somente a identidade.

    Parâmetros urbanísticos não são editáveis por aqui: eles pertencem a uma
    versão e mudam por `POST /projects/{id}/versions`.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    district: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    lot: Optional[str] = None
    block: Optional[str] = None
    registry_number: Optional[str] = None
    municipal_registration: Optional[str] = None
    owner_name: Optional[str] = None
    owner_document: Optional[str] = None
    contractor_name: Optional[str] = None
    technical_responsible_name: Optional[str] = None
    technical_responsible_registry: Optional[str] = None
    use_type: Optional[str] = None
    units_count: Optional[int] = None
    licensing_status: Optional[str] = None


class ValidationRecordResponse(BaseModel):
    id: str
    analysis_run_id: str
    rule_id: str
    rule_title: str
    status: str
    field: str
    expected_value: str
    actual_value: str
    details: Optional[str] = None
    rule_state: str
    severity: str
    method: str
    source_document: Optional[str] = None
    source_article: Optional[str] = None
    source_citation: Optional[str] = None
    source_is_verified: bool = False
    evidence_required: Optional[str] = None
    validated_by: Optional[str] = None
    is_publishable: bool = False
    validated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(ProjectIdentity):
    id: str
    organization_id: str
    licensing_status: str
    created_at: datetime
    updated_at: datetime
    current_version: Optional[ProjectVersionResponse] = None
    official_baseline: Optional[ProjectVersionResponse] = None
    validations: List[ValidationRecordResponse] = []
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Análises
# =============================================================================

class AnalysisRunResponse(BaseModel):
    id: str
    project_id: str
    project_version_id: Optional[str] = None
    project_version_number: Optional[int] = None
    jurisdiction: str
    catalog_version: str
    engine_version: str
    trigger: str
    total_checks: int
    conforme_count: int
    nao_conforme_count: int
    atencao_count: int
    nao_verificavel_count: int
    is_publishable: bool
    content_hash: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnalysisRunDetail(AnalysisRunResponse):
    validations: List[ValidationRecordResponse] = []


class RegulatoryAnalysisReport(BaseModel):
    project_id: str
    analysis_run_id: str
    project_version_number: Optional[int] = None
    catalog_version: str
    engine_version: str
    total_checks: int
    conforme_count: int
    nao_conforme_count: int
    atencao_count: int
    nao_verificavel_count: int
    is_publishable: bool
    content_hash: Optional[str] = None
    results: List[ValidationRecordResponse]


# =============================================================================
# Catálogo regulatório (§7)
# =============================================================================

class RegulatoryDocumentBase(BaseModel):
    jurisdiction: str
    doc_type: str = "lei"
    number: Optional[str] = None
    title: str
    issuing_body: Optional[str] = None
    url: Optional[str] = None
    theme: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None


class RegulatoryDocumentCreate(RegulatoryDocumentBase):
    state: str = "catalogado"


class RegulatoryDocumentResponse(RegulatoryDocumentBase):
    id: str
    state: str
    hash_sha256: Optional[str] = None
    consulted_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RegulatoryRuleResponse(BaseModel):
    id: str
    rule_key: str
    jurisdiction: str
    title: str
    state: str
    severity: str
    applies_to: Dict[str, Any] = {}
    check: Optional[Dict[str, Any]] = None
    requires_manual_review: bool
    manual_review_reason: Optional[str] = None
    evidence_required: List[str] = []
    source_document_id: Optional[str] = None
    source_document_label: Optional[str] = None
    source_article: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    validated_by_id: Optional[str] = None
    validated_by_name: Optional[str] = None
    validated_at: Optional[datetime] = None
    notes: Optional[str] = None
    catalog_version: str
    is_executable: bool = False
    is_publishable: bool = False
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RuleValidationRequest(BaseModel):
    """Ato de validação técnica de uma regra (§7.5, §15.12)."""

    action: str = Field(description="publicar | rejeitar | suspender | revogar | reabrir")
    notes: Optional[str] = None
    #: Obrigatórios ao publicar: sem fonte conferida a regra não pode ser vigente.
    source_document_id: Optional[str] = None
    source_article: Optional[str] = None
    effective_from: Optional[str] = None


class RuleValidationEventResponse(BaseModel):
    id: str
    rule_id: str
    from_state: Optional[str] = None
    to_state: str
    action: str
    notes: Optional[str] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CatalogImportResponse(BaseModel):
    created: int
    updated: int
    skipped_validated: int


# =============================================================================
# Tramitação (§8.5)
# =============================================================================

class ProtocolProcessCreate(BaseModel):
    protocol_number: str
    agency: str = "Prefeitura Municipal"
    process_type: str = "aprovacao_projeto"
    submitted_at: Optional[str] = None
    project_version_id: Optional[str] = None
    notes: Optional[str] = None


class ProtocolStatusChange(BaseModel):
    status: str
    description: Optional[str] = None
    decided_at: Optional[str] = None


class ProtocolRequirementCreate(BaseModel):
    description: str
    origin: str = "notificacao_orgao"
    raised_at: Optional[str] = None
    due_date: Optional[str] = None
    linked_rule_key: Optional[str] = None


class ProtocolRequirementUpdate(BaseModel):
    status: Optional[str] = None
    response_text: Optional[str] = None
    responded_at: Optional[str] = None
    resolved_at: Optional[str] = None
    due_date: Optional[str] = None
    linked_rule_key: Optional[str] = None


class ProtocolRequirementResponse(BaseModel):
    id: str
    process_id: str
    sequence: int
    description: str
    origin: str
    raised_at: Optional[str] = None
    due_date: Optional[str] = None
    status: str
    response_text: Optional[str] = None
    responded_at: Optional[str] = None
    resolved_at: Optional[str] = None
    linked_rule_key: Optional[str] = None
    was_predicted: Optional[bool] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProtocolEventResponse(BaseModel):
    id: str
    process_id: str
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    description: Optional[str] = None
    actor_name: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProtocolProcessResponse(BaseModel):
    id: str
    project_id: str
    project_version_id: Optional[str] = None
    protocol_number: str
    agency: str
    process_type: str
    status: str
    submitted_at: Optional[str] = None
    decided_at: Optional[str] = None
    notes: Optional[str] = None
    open_requirements_count: int = 0
    created_at: datetime
    updated_at: datetime
    requirements: List[ProtocolRequirementResponse] = []
    events: List[ProtocolEventResponse] = []
    model_config = ConfigDict(from_attributes=True)


class PredictionAccuracy(BaseModel):
    """Recall de bloqueios: quanto da exigência real o Atlas antecipou (§11)."""

    total_requirements: int
    linked_to_rules: int
    predicted: int
    not_predicted: int
    recall_percent: Optional[float] = None


# =============================================================================
# Documentos (§8.3)
# =============================================================================

class DocumentResponse(BaseModel):
    id: str
    project_id: str
    project_version_id: Optional[str] = None
    title: str
    category: str
    version: str
    file_path: str
    storage_backend: str = "local"
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    hash_sha256: Optional[str] = None
    status: str
    supersedes_id: Optional[str] = None
    superseded_at: Optional[datetime] = None
    is_current: bool = True

    # Antivírus e retenção (§6.6). `nao_verificado` é resposta legítima, e a
    # interface precisa poder mostrá-la como tal.
    antivirus_status: str = "nao_verificado"
    antivirus_engine: Optional[str] = None
    antivirus_scanned_at: Optional[datetime] = None
    antivirus_signature: Optional[str] = None
    retention_until: Optional[datetime] = None
    purged_at: Optional[datetime] = None
    purge_reason: Optional[str] = None
    is_purged: bool = False

    uploaded_by_id: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JobRecordResponse(BaseModel):
    """Registro de um trabalho assíncrono (§6.7)."""

    id: str
    project_id: Optional[str] = None
    job_type: str
    status: str
    payload: dict = Field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    #: Verdadeiro quando não havia broker e o trabalho rodou dentro do request.
    executed_inline: bool = False
    queue: str = "default"
    worker_id: Optional[str] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    is_terminal: bool = False
    requested_by_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class JobSubmitResponse(BaseModel):
    job: JobRecordResponse
    #: Descrição do backend de fila em uso — a interface precisa poder dizer ao
    #: usuário se existe worker ou se o trabalho rodou ali mesmo.
    queue_backend: str


class PurgeReportResponse(BaseModel):
    """Resultado do expurgo por retenção (§6.6)."""

    dry_run: bool
    retention_enabled: bool
    retention_days: int
    examined: int
    purged: int
    already_missing: int
    failed: int
    document_ids: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    document_id: str
    document_title: str
    status: str
    fields_found: int
    fields_expected: int
    extracted_parameters: dict
    evidence: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# =============================================================================
# EAP, tarefas e diário
# =============================================================================

class EAPItemBase(BaseModel):
    code: str
    name: str
    item_type: str = "etapa"
    progress_percent: float = 0.0
    parent_id: Optional[str] = None


class EAPItemCreate(EAPItemBase):
    pass


class EAPItemResponse(EAPItemBase):
    id: str
    project_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "a_fazer"
    priority: str = "media"
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    eap_item_id: Optional[str] = None


class TaskItemCreate(TaskItemBase):
    #: Chave de idempotência do cliente de campo (§3.7). O aplicativo offline
    #: gera uma por item da fila; reenviar depois de uma resposta perdida
    #: devolve o registro original em vez de criar um segundo.
    client_token: Optional[str] = Field(default=None, max_length=64)


class TaskItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    eap_item_id: Optional[str] = None


class TaskItemResponse(TaskItemBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DailyLogBase(BaseModel):
    date: str
    weather_condition: str = "ensolarado"
    manpower_own: int = 0
    manpower_subcontracted: int = 0
    activities_done: str
    occurrences: Optional[str] = None
    status: str = "assinado"


class DailyLogCreate(DailyLogBase):
    #: Ver `TaskItemCreate.client_token`.
    client_token: Optional[str] = Field(default=None, max_length=64)


class DailyLogResponse(DailyLogBase):
    id: str
    project_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Métricas do §11 (D5) ----------------------------------------------------
# Todo campo opcional aqui é `None` **por ausência de base amostral**, nunca por
# erro. Zero afirma; `None` declara que não há o que afirmar.


class ApprovalMetrics(BaseModel):
    """§11 — Aprovação."""

    projects: int
    protocols: int
    permits_granted: int

    #: Cada volta do órgão. `None` quando não há processo protocolado.
    notification_cycles_total: Optional[int] = None
    notification_cycles_per_protocol: Optional[float] = None

    #: Média entre protocolo e decisão, só para processos aprovados com as
    #: duas datas registradas.
    days_to_permit_avg: Optional[float] = None

    requirements_total: Optional[int] = None
    requirements_linked_to_rules: Optional[int] = None

    #: Das exigências vinculadas a regra, quantas o Atlas apontou antes.
    blocking_recall_percent: Optional[float] = None
    #: A métrica que decide o Portão 0 → 1. `None` significa "não houve
    #: exigência vinculada", que é diferente de "nenhuma escapou".
    critical_false_negatives: Optional[int] = None
    #: Do que o motor apontou, quanto o órgão confirmou.
    precision_percent: Optional[float] = None
    #: Quanto do projeto o sistema não consegue avaliar por falta de dado.
    unverifiable_percent: Optional[float] = None

    catalog_rules: Optional[int] = None
    catalog_publishable_rules: Optional[int] = None
    #: Regra publicável sobre total, nas jurisdições em uso — o progresso do D3.
    catalog_coverage_percent: Optional[float] = None


class AIMetrics(BaseModel):
    """§11 — IA.

    Custo aparece em **tokens**, não em dinheiro: converter exigiria uma tabela
    de preços que não existe no sistema, e preço estimado é suposição com cara
    de medição. Quando a tabela existir, a conversão entra aqui.
    """

    interactions: int
    grounded_percent: Optional[float] = None
    served_from_cache_percent: Optional[float] = None
    failed: Optional[int] = None

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    tokens_per_analysis: Optional[float] = None
    tokens_per_project: Optional[float] = None

    drafts_extracted: Optional[int] = None
    drafts_accepted: Optional[int] = None
    drafts_rejected: Optional[int] = None
    draft_acceptance_percent: Optional[float] = None


class GateCriterion(BaseModel):
    """Um critério do portão, com o medido ao lado do proposto."""

    name: str
    measured: Optional[float] = None
    threshold: float
    comparison: str
    met: Optional[bool] = None


class GateStatus(BaseModel):
    """Portão 0 → 1.

    Os limiares são **proposta** do roadmap, não decisão tomada — §10 do plano
    diz "taxa mínima de previsão" sem número. `met` é `None` quando o critério
    não pôde ser medido, e `overall` é `None` se qualquer critério for `None`:
    portão não se atravessa por falta de dado.
    """

    criteria: List[GateCriterion]
    overall: Optional[bool] = None
    note: str = (
        "Limiares propostos em docs/ROADMAP.md, a confirmar por quem decide. "
        "Critério não medido é `null`, nunca falso — e nunca verdadeiro."
    )


class MetricsResponse(BaseModel):
    organization_id: str
    generated_at: datetime
    approval: ApprovalMetrics
    ai: AIMetrics
    gate_0_to_1: GateStatus


# --- Privacidade e retenção de conteúdo (LGPD) -------------------------------


class ContentPurgeReportResponse(BaseModel):
    """Resultado do expurgo de conteúdo de IA ou de trabalhos.

    O que sai é o conteúdo; a linha e a proveniência permanecem (§3.5).
    """

    dry_run: bool
    retention_enabled: bool
    retention_days: int
    examined: int
    purged: int
    record_ids: List[str] = Field(default_factory=list)


class AnonymizationRequest(BaseModel):
    #: Por que o pedido está sendo atendido. Fica no registro: a própria
    #: anonimização é um ato que precisa de trilha.
    reason: str = Field(min_length=10, max_length=1000)
    dry_run: bool = True


class AnonymizationResponse(BaseModel):
    project_id: str
    dry_run: bool
    already_anonymized: bool
    fields_cleared: List[str] = Field(default_factory=list)
    anonymized_at: Optional[datetime] = None
    note: str = (
        "Análises, versões e tramitação permanecem íntegras e auditáveis. "
        "O que foi removido é o dado pessoal de terceiros, não o registro do "
        "ato técnico."
    )
