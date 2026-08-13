"""Modelo de domínio do Atlas.

Três invariantes estruturais atravessam este arquivo:

1. **Multiempresa desde a origem (§3.1).** Toda entidade de negócio carrega
   `organization_id`. Nenhuma consulta de aplicação pode dispensar esse filtro.
2. **Linha de base versionada (§3.2).** Os parâmetros urbanísticos pertencem a
   `ProjectVersion`, não ao projeto. Versões são imutáveis: alterar um
   parâmetro cria uma versão nova.
3. **Nada é apagado (§3.5).** Análises, eventos de validação e tramitação são
   append-only.
"""

from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# =============================================================================
# Vocabulários
# =============================================================================

class UserRole:
    """Papéis e o que cada um pode fazer (§8.1)."""

    OWNER = "owner"            # tudo, incluindo gestão da organização
    ADMIN = "admin"            # gestão de usuários e projetos
    VALIDATOR = "validator"    # publica regras no catálogo regulatório (§7.5)
    ENGINEER = "engineer"      # opera projetos, documentos, obra
    INSPECTOR = "inspector"    # campo: diário, tarefas, inspeções
    CLIENT = "client"          # somente leitura do próprio empreendimento

    ALL = {OWNER, ADMIN, VALIDATOR, ENGINEER, INSPECTOR, CLIENT}


class ProjectVersionState:
    """Estados da versão de projeto (§3.2)."""

    ESTUDO_PRELIMINAR = "estudo_preliminar"
    REVISAO_INTERNA = "revisao_interna"
    PROTOCOLADA = "protocolada"
    NOTIFICADA = "notificada"
    CORRIGIDA = "corrigida"
    APROVADA = "aprovada"
    ALTERACAO_EM_OBRA = "alteracao_em_obra"
    AS_BUILT = "as_built"

    ALL = {
        ESTUDO_PRELIMINAR, REVISAO_INTERNA, PROTOCOLADA, NOTIFICADA,
        CORRIGIDA, APROVADA, ALTERACAO_EM_OBRA, AS_BUILT,
    }


class DocumentState:
    """Estados do documento (§8.3)."""

    RASCUNHO = "rascunho"
    EM_REVISAO = "em_revisao"
    VIGENTE = "vigente"
    OBSOLETO = "obsoleto"

    ALL = {RASCUNHO, EM_REVISAO, VIGENTE, OBSOLETO}


class RegulatoryDocumentState:
    """Estados do documento regulatório (§7.3)."""

    DESCOBERTO = "descoberto"
    BAIXADO = "baixado"
    CATALOGADO = "catalogado"
    EM_PROCESSAMENTO = "em_processamento"
    PROCESSADO = "processado"
    VALIDADO = "validado"
    SUBSTITUIDO = "substituido"
    REVOGADO = "revogado"
    INDISPONIVEL = "indisponivel"

    ALL = {
        DESCOBERTO, BAIXADO, CATALOGADO, EM_PROCESSAMENTO, PROCESSADO,
        VALIDADO, SUBSTITUIDO, REVOGADO, INDISPONIVEL,
    }


class ProtocolStatus:
    """Situação do processo junto ao órgão (§8.5)."""

    PROTOCOLADO = "protocolado"
    EM_ANALISE = "em_analise"
    NOTIFICADO = "notificado"
    EM_CORRECAO = "em_correcao"
    REPROTOCOLADO = "reprotocolado"
    APROVADO = "aprovado"
    INDEFERIDO = "indeferido"
    ARQUIVADO = "arquivado"

    ALL = {
        PROTOCOLADO, EM_ANALISE, NOTIFICADO, EM_CORRECAO,
        REPROTOCOLADO, APROVADO, INDEFERIDO, ARQUIVADO,
    }

    #: Situações em que o processo já não avança sozinho.
    TERMINAL = {APROVADO, INDEFERIDO, ARQUIVADO}


class JobStatus:
    """Situação de um trabalho assíncrono (§6.7)."""

    ENFILEIRADO = "enfileirado"
    EXECUTANDO = "executando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"
    CANCELADO = "cancelado"

    ALL = {ENFILEIRADO, EXECUTANDO, CONCLUIDO, FALHOU, CANCELADO}
    TERMINAL = {CONCLUIDO, FALHOU, CANCELADO}


class JobType:
    """Trabalhos que saem do ciclo da requisição (§6.7)."""

    EXTRACAO_DOCUMENTO = "extracao_documento"
    ANALISE_REGULATORIA = "analise_regulatoria"
    GERACAO_LAUDO = "geracao_laudo"
    EXPURGO_RETENCAO = "expurgo_retencao"

    ALL = {EXTRACAO_DOCUMENTO, ANALISE_REGULATORIA, GERACAO_LAUDO, EXPURGO_RETENCAO}


class RequirementStatus:
    """Situação de uma exigência ou notificação."""

    ABERTA = "aberta"
    EM_CORRECAO = "em_correcao"
    RESPONDIDA = "respondida"
    ATENDIDA = "atendida"
    NAO_ATENDIDA = "nao_atendida"

    ALL = {ABERTA, EM_CORRECAO, RESPONDIDA, ATENDIDA, NAO_ATENDIDA}
    OPEN = {ABERTA, EM_CORRECAO, RESPONDIDA}


# =============================================================================
# Organização e usuários
# =============================================================================

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projects: Mapped[List["Project"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    users: Mapped[List["User"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.ENGINEER)

    #: Hash argon2id. A senha em claro nunca é persistida nem registrada em log.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="users")


# =============================================================================
# Empreendimento e versões
# =============================================================================

class Project(Base):
    """Identidade do empreendimento (§8.2).

    Não guarda parâmetros urbanísticos: eles pertencem à versão vigente, para
    que nenhuma medida seja alterada sem deixar rastro.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # -- Localização (§8.2) ------------------------------------------------
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address_complement: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    city_ibge: Mapped[str] = mapped_column(String(20), default="BR-RS-4311403", index=True)
    city_name: Mapped[str] = mapped_column(String(100), default="Lajeado")
    state: Mapped[str] = mapped_column(String(2), default="RS")
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # -- Identificação imobiliária ----------------------------------------
    lot: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    block: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    registry_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)  # matrícula
    municipal_registration: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)  # inscrição

    # -- Partes envolvidas -------------------------------------------------
    #: Quando os dados pessoais de terceiros deste empreendimento foram
    #: redigidos a pedido do titular. A linha permanece — análises, versões e
    #: tramitação são append-only (I5, I6) e continuam auditáveis sem o nome.
    anonymized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    anonymization_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_document: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contractor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    technical_responsible_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    technical_responsible_registry: Mapped[Optional[str]] = mapped_column(
        String(80), nullable=True
    )  # CREA / CAU

    # -- Caracterização ----------------------------------------------------
    use_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    units_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    licensing_status: Mapped[str] = mapped_column(String(50), default="nao_iniciado")

    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    versions: Mapped[List["ProjectVersion"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectVersion.version_number",
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    analysis_runs: Mapped[List["AnalysisRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="AnalysisRun.created_at",
    )
    protocols: Mapped[List["ProtocolProcess"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    eap_items: Mapped[List["EAPItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[List["TaskItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    daily_logs: Mapped[List["DailyLog"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    # -- Derivados ---------------------------------------------------------
    @property
    def current_version(self) -> Optional["ProjectVersion"]:
        """Versão mais recente — a que o cadastro exibe e o motor avalia."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.version_number)

    @property
    def official_baseline(self) -> Optional["ProjectVersion"]:
        """Linha de base oficial: a versão aprovada e marcada como tal (§3.2)."""
        marked = [v for v in self.versions if v.is_official_baseline]
        if not marked:
            return None
        return max(marked, key=lambda v: v.version_number)

    @property
    def latest_analysis_run(self) -> Optional["AnalysisRun"]:
        if not self.analysis_runs:
            return None
        return max(self.analysis_runs, key=lambda run: (run.created_at, run.id))

    @property
    def validations(self) -> List["ValidationRecord"]:
        run = self.latest_analysis_run
        return list(run.validations) if run else []


class ProjectVersion(Base):
    """Fotografia imutável dos parâmetros urbanísticos (§3.2).

    Nenhum campo desta tabela deve ser alterado após a criação: uma mudança de
    parâmetro gera uma versão nova, com motivo e autor. É isso que sustenta a
    exigência de "nenhuma alteração silenciosa" (§14.15).
    """

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(50), default=ProjectVersionState.ESTUDO_PRELIMINAR
    )

    # -- Parâmetros. NULL = não informado; nunca zero. ---------------------
    zone: Mapped[str] = mapped_column(String(50), default="Z2")
    building_type: Mapped[str] = mapped_column(String(100), default="residencial_unifamiliar")
    lot_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    built_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    front_setback: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    side_setback: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rear_setback: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    permeability_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    parking_spaces: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: Verdadeiro apenas na versão aprovada eleita como linha de base oficial.
    is_official_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    baseline_marked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_origin: Mapped[str] = mapped_column(String(50), default="cadastro_manual")
    #: SHA-256 dos parâmetros — permite detectar adulteração da versão.
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="versions")
    created_by: Mapped[Optional["User"]] = relationship()

    @property
    def occupancy_rate(self) -> Optional[float]:
        """Taxa de ocupação — sempre derivada, nunca armazenada."""
        if not self.lot_area or self.built_area is None:
            return None
        return round(self.built_area / self.lot_area * 100, 1)


# =============================================================================
# Gestão documental (§8.3)
# =============================================================================

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    project_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="projeto_arquitetonico")
    version: Mapped[str] = mapped_column(String(20), default="v1.0")

    #: Chave opaca gerada pelo servidor. O nome enviado pelo cliente nunca toca
    #: o armazenamento. Onde a chave é resolvida depende de `storage_backend`.
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    #: Backend que guarda o binário (§6.6): `local`, `s3`.
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # -- Antivírus (§6.6) --------------------------------------------------
    #: `nao_verificado` é o padrão deliberado: sem motor que tenha respondido,
    #: o arquivo não é dado por limpo.
    antivirus_status: Mapped[str] = mapped_column(String(30), default="nao_verificado")
    antivirus_engine: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    antivirus_engine_version: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    antivirus_signature: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    antivirus_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # -- Retenção (§6.6) ---------------------------------------------------
    #: A partir desta data o binário pode ser expurgado. NULL = guardar sempre.
    retention_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    #: Quando preenchido, o binário já não existe — o registro permanece, para
    #: que a trilha de auditoria continue completa (§3.5).
    purged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    purge_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default=DocumentState.VIGENTE)
    #: Cadeia de versões: aponta para o documento que esta versão substitui.
    supersedes_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    uploaded_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="documents")
    uploaded_by: Mapped[Optional["User"]] = relationship()

    @property
    def is_current(self) -> bool:
        return self.status == DocumentState.VIGENTE

    @property
    def is_purged(self) -> bool:
        """Metadados preservados, binário descartado pela política de retenção."""
        return self.purged_at is not None


# =============================================================================
# Catálogo regulatório (§7)
# =============================================================================

class RegulatoryDocument(Base):
    """Norma catalogada (§7.2 — Catálogo regulatório).

    Compartilhada entre organizações: legislação municipal é dado público, e
    duplicá-la por tenant tornaria impossível manter uma vigência única.
    """

    __tablename__ = "regulatory_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    jurisdiction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(80), default="lei")
    number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    consulted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    effective_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    effective_until: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    state: Mapped[str] = mapped_column(
        String(50), default=RegulatoryDocumentState.DESCOBERTO
    )
    supersedes_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulatory_documents.id"), nullable=True
    )
    theme: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    rules: Mapped[List["RegulatoryRule"]] = relationship(back_populates="source_document")


class RegulatoryRule(Base):
    """Regra estruturada (§7.4 e §7.6).

    O motor executa apenas regras em estado executável; somente regras
    `vigente` **com validador registrado** podem ir para laudo entregue ao
    cliente (§7.5).
    """

    __tablename__ = "regulatory_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rule_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    state: Mapped[str] = mapped_column(String(50), default="em_validacao", index=True)
    severity: Mapped[str] = mapped_column(String(20), default="bloqueio")

    applies_to: Mapped[dict] = mapped_column(JSON, default=dict)
    check: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_required: Mapped[list] = mapped_column(JSON, default=list)

    source_document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulatory_documents.id"), nullable=True
    )
    #: Redundante com o documento, mas preservado para regras importadas antes
    #: de o documento ser catalogado.
    source_document_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_article: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    effective_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    effective_until: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    validated_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    validated_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    catalog_version: Mapped[str] = mapped_column(String(50), default="0.1.0")
    superseded_by_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulatory_rules.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    source_document: Mapped[Optional["RegulatoryDocument"]] = relationship(
        back_populates="rules"
    )
    validated_by: Mapped[Optional["User"]] = relationship()
    events: Mapped[List["RuleValidationEvent"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="RuleValidationEvent.created_at",
    )


class RuleValidationEvent(Base):
    """Trilha de transições de estado de uma regra (§3.5, §7.8)."""

    __tablename__ = "rule_validation_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("regulatory_rules.id"), nullable=False, index=True
    )
    from_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule: Mapped["RegulatoryRule"] = relationship(back_populates="events")


# =============================================================================
# Análises
# =============================================================================

class AnalysisRun(Base):
    """Uma execução do motor sobre uma **versão** de projeto.

    Append-only: cada avaliação cria um registro novo e nada é sobrescrito.
    """

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    project_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True, index=True
    )
    project_version_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    jurisdiction: Mapped[str] = mapped_column(String(20), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(50), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), default="manual")

    total_checks: Mapped[int] = mapped_column(Integer, default=0)
    conforme_count: Mapped[int] = mapped_column(Integer, default=0)
    nao_conforme_count: Mapped[int] = mapped_column(Integer, default=0)
    atencao_count: Mapped[int] = mapped_column(Integer, default=0)
    nao_verificavel_count: Mapped[int] = mapped_column(Integer, default=0)

    #: Falso quando qualquer regra aplicada ainda não passou por validação
    #: humana — nesse caso o laudo não pode ser entregue ao cliente (§7.5).
    is_publishable: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    requested_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")
    project_version: Mapped[Optional["ProjectVersion"]] = relationship()
    validations: Mapped[List["ValidationRecord"]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )


class ValidationRecord(Base):
    __tablename__ = "validation_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)

    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_title: Mapped[str] = mapped_column(String(255), nullable=False)
    field: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    expected_value: Mapped[str] = mapped_column(String(100), nullable=False)
    actual_value: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # -- Proveniência (§3.5) -----------------------------------------------
    rule_state: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(50), default="regra_deterministica")
    source_document: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_article: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_citation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_required: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_publishable: Mapped[bool] = mapped_column(Boolean, default=False)

    validated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="validations")


# =============================================================================
# Tramitação (§8.5)
# =============================================================================

class ProtocolProcess(Base):
    """Processo administrativo junto ao órgão licenciador."""

    __tablename__ = "protocol_processes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    project_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )

    protocol_number: Mapped[str] = mapped_column(String(120), nullable=False)
    agency: Mapped[str] = mapped_column(String(255), default="Prefeitura Municipal")
    process_type: Mapped[str] = mapped_column(String(80), default="aprovacao_projeto")
    status: Mapped[str] = mapped_column(String(50), default=ProtocolStatus.PROTOCOLADO)

    submitted_at: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    decided_at: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="protocols")
    requirements: Mapped[List["ProtocolRequirement"]] = relationship(
        back_populates="process",
        cascade="all, delete-orphan",
        order_by="ProtocolRequirement.sequence",
    )
    events: Mapped[List["ProtocolEvent"]] = relationship(
        back_populates="process",
        cascade="all, delete-orphan",
        order_by="ProtocolEvent.created_at",
    )

    @property
    def open_requirements_count(self) -> int:
        return sum(1 for r in self.requirements if r.status in RequirementStatus.OPEN)


class ProtocolRequirement(Base):
    """Exigência ou notificação emitida pelo órgão."""

    __tablename__ = "protocol_requirements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    process_id: Mapped[str] = mapped_column(
        ForeignKey("protocol_processes.id"), nullable=False, index=True
    )

    sequence: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(50), default="notificacao_orgao")
    raised_at: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default=RequirementStatus.ABERTA)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    resolved_at: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    #: Quando a exigência corresponde a uma regra do catálogo, o vínculo
    #: permite medir a taxa de acerto da pré-análise (§11 — recall de bloqueios).
    linked_rule_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    #: Verdadeiro quando o Atlas havia apontado o problema antes do protocolo.
    was_predicted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    process: Mapped["ProtocolProcess"] = relationship(back_populates="requirements")


class ProtocolEvent(Base):
    """Histórico do processo — append-only."""

    __tablename__ = "protocol_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    process_id: Mapped[str] = mapped_column(
        ForeignKey("protocol_processes.id"), nullable=False, index=True
    )

    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    process: Mapped["ProtocolProcess"] = relationship(back_populates="events")


# =============================================================================
# Camada de IA (§3.3, §6.8)
# =============================================================================

class AIInteraction(Base):
    """Proveniência de toda chamada a um modelo de linguagem (§3.3, §3.5).

    Existe para responder, meses depois, a uma pergunta incômoda: *de onde saiu
    esta frase?* Guarda quem perguntou, o que foi perguntado, qual modelo
    respondeu, quais regras do catálogo foram entregues como contexto e o que
    voltou — incluindo recusas e falhas.

    Duas colunas merecem atenção:

    - `grounded` é falso quando o modelo citou regra que não estava no contexto
      recuperado. Nesse caso a resposta é devolvida ao usuário com a citação
      removida e um aviso, porque uma citação legal inventada é exatamente o
      dano que este sistema não pode causar;
    - `answer_is_advisory` é sempre verdadeiro. A coluna existe para que
      nenhuma consulta futura precise supor: nada que saia de um modelo tem
      valor de veredicto — o veredicto vem do motor determinístico (§3.4).
    """

    __tablename__ = "ai_interactions"

    #: O cache procura por (organização, hash da requisição) — ver
    #: `ai/service.py::_lookup_cache`. Sem este índice a busca varreria todo o
    #: histórico de interações a cada consulta.
    __table_args__ = (
        Index("ix_ai_interactions_org_hash", "organization_id", "request_hash"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )

    purpose: Mapped[str] = mapped_column(String(60), default="consulta_normativa")
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    #: SHA-256 de (pergunta + regras recuperadas + modelo). Chave do cache e
    #: prova de que a mesma pergunta, sobre o mesmo catálogo, deu a mesma volta.
    #: Sem `index=True`: a busca do cache é sempre por (organização, hash), e
    #: quem serve é o índice composto em `__table_args__`.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    #: Chaves das regras entregues como contexto — o RAG fica auditável.
    retrieved_rule_keys: Mapped[list] = mapped_column(JSON, default=list)
    #: Chaves efetivamente citadas na resposta, após conferência.
    cited_rule_keys: Mapped[list] = mapped_column(JSON, default=list)

    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: Falso quando o modelo citou regra fora do contexto recuperado.
    grounded: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Invariante, não configuração: resposta de modelo é sempre assistiva.
    answer_is_advisory: Mapped[bool] = mapped_column(Boolean, default=True)
    served_from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: Quando o conteúdo (pergunta, resposta) foi descartado pela retenção.
    #: A linha permanece: proveniência, tokens e vínculo com o catálogo são o
    #: que responde "de onde veio esta resposta", e isso não se apaga (§3.5).
    content_purged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship()


# =============================================================================
# Trabalhos assíncronos (§6.7)
# =============================================================================

class JobRecord(Base):
    """Registro de um trabalho que sai do ciclo da requisição.

    O registro existe **sempre**, tenha o trabalho ido para um worker ou
    rodado no próprio processo por falta de broker. Quem consulta consegue
    distinguir os dois casos por `executed_inline`: uma instalação sem fila
    continua funcionando, mas não finge ter uma.

    Um trabalho que nunca foi retirado da fila permanece `enfileirado` — visível
    e cobrável. Nada some em silêncio.
    """

    __tablename__ = "job_records"

    #: O worker varre por (status, fila) à procura de órfãos — ver
    #: `workers/worker.py::recover_orphans`. Sem este índice a varredura
    #: passaria a tabela inteira a cada partida.
    __table_args__ = (Index("ix_job_records_status_queue", "status", "queue"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )

    job_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    #: Sem `index=True`: a varredura do worker é sempre por (status, fila), e
    #: quem serve é o índice composto em `__table_args__`.
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.ENFILEIRADO)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    #: Mensagem de erro da última tentativa. Preservada mesmo após novo sucesso,
    #: para que a falha não desapareça do histórico.
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    #: Verdadeiro quando não havia broker e o trabalho rodou no request.
    executed_inline: Mapped[bool] = mapped_column(Boolean, default=False)
    queue: Mapped[str] = mapped_column(String(60), default="default")
    worker_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    #: Ver `AIInteraction.content_purged_at` — mesmo contrato.
    content_purged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    requested_by_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    project: Mapped[Optional["Project"]] = relationship()

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.started_at or not self.finished_at:
            return None
        return round((self.finished_at - self.started_at).total_seconds(), 3)

    @property
    def is_terminal(self) -> bool:
        return self.status in JobStatus.TERMINAL


# =============================================================================
# Operação de obra
# =============================================================================

class EAPItem(Base):
    __tablename__ = "eap_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), default="etapa")
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    parent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("eap_items.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="eap_items")
    tasks: Mapped[List["TaskItem"]] = relationship(back_populates="eap_item")


class TaskItem(Base):
    __tablename__ = "task_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    eap_item_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("eap_items.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="a_fazer")
    priority: Mapped[str] = mapped_column(String(50), default="media")
    assignee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    #: Chave de idempotência do cliente de campo (§3.7) — ver `DailyLog`.
    client_token: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )

    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    eap_item: Mapped[Optional["EAPItem"]] = relationship(back_populates="tasks")


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    date: Mapped[str] = mapped_column(String(50), nullable=False)
    weather_condition: Mapped[str] = mapped_column(String(50), default="ensolarado")
    manpower_own: Mapped[int] = mapped_column(Integer, default=0)
    manpower_subcontracted: Mapped[int] = mapped_column(Integer, default=0)
    activities_done: Mapped[str] = mapped_column(Text, nullable=False)
    occurrences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="assinado")

    #: Chave de idempotência gerada pelo cliente de campo (§3.7). Um envio
    #: repetido depois de resposta perdida devolve o registro original em vez
    #: de criar um segundo diário para o mesmo dia.
    client_token: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )

    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="daily_logs")
