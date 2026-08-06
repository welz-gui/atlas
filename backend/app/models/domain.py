from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
import uuid

from app.core.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # CNPJ / CPF
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projects: Mapped[List["Project"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="engineer") # admin, engineer, inspector, client
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="users")

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parâmetros de Localização e Zoneamento
    city_ibge: Mapped[str] = mapped_column(String(20), default="BR-RS-4311403") # Lajeado/RS
    city_name: Mapped[str] = mapped_column(String(100), default="Lajeado")
    state: Mapped[str] = mapped_column(String(2), default="RS")
    zone: Mapped[str] = mapped_column(String(50), default="Z2") # Z1, Z2, Z3, etc.
    building_type: Mapped[str] = mapped_column(String(100), default="residencial_unifamiliar")

    # Métricas Físicas do Empreendimento.
    # NULL significa "não informado" — nunca zero. Um parâmetro ausente produz
    # verificação `nao_verificavel`, jamais um veredicto de não conformidade.
    lot_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Área do Lote m²
    built_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Área Construída m²
    floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # Número de Pavimentos
    front_setback: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Recuo Frontal m
    side_setback: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Recuo Lateral m
    rear_setback: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Recuo dos Fundos m
    permeability_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Taxa de Permeabilidade %
    parking_spaces: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # Vagas de Estacionamento

    # Status de Licenciamento
    status: Mapped[str] = mapped_column(String(50), default="estudo_preliminar")
    is_official_baseline: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    documents: Mapped[List["Document"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    analysis_runs: Mapped[List["AnalysisRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="AnalysisRun.created_at",
    )
    eap_items: Mapped[List["EAPItem"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[List["TaskItem"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    daily_logs: Mapped[List["DailyLog"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    # -- Derivados ---------------------------------------------------------
    @property
    def occupancy_rate(self) -> Optional[float]:
        """Taxa de ocupação — sempre derivada, nunca armazenada.

        O protótipo mantinha uma coluna `occupancy_rate` *e* recalculava o
        valor no motor, com resultados divergentes. A taxa passa a ter uma
        única fonte da verdade.
        """
        if not self.lot_area or self.built_area is None:
            return None
        return round(self.built_area / self.lot_area * 100, 1)

    @property
    def latest_analysis_run(self) -> Optional["AnalysisRun"]:
        if not self.analysis_runs:
            return None
        return max(self.analysis_runs, key=lambda run: (run.created_at, run.id))

    @property
    def validations(self) -> List["ValidationRecord"]:
        """Verificações da análise mais recente.

        O histórico completo continua disponível em `analysis_runs`; nada é
        apagado (§3.5).
        """
        run = self.latest_analysis_run
        return list(run.validations) if run else []

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="projeto_arquitetonico")
    version: Mapped[str] = mapped_column(String(20), default="v1.0")

    # `file_path` guarda um nome opaco (UUID + extensão) gerado pelo servidor.
    # O nome enviado pelo usuário fica em `original_filename` e nunca toca o disco.
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="rascunho")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="documents")

class EAPItem(Base):
    __tablename__ = "eap_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
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

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    eap_item_id: Mapped[Optional[str]] = mapped_column(ForeignKey("eap_items.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="a_fazer")
    priority: Mapped[str] = mapped_column(String(50), default="media")
    assignee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    eap_item: Mapped[Optional["EAPItem"]] = relationship(back_populates="tasks")

class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "2026-08-06"
    weather_condition: Mapped[str] = mapped_column(String(50), default="ensolarado") # ensolarado, nublado, chuvoso, impraticavel
    manpower_own: Mapped[int] = mapped_column(Integer, default=0)
    manpower_subcontracted: Mapped[int] = mapped_column(Integer, default=0)
    activities_done: Mapped[str] = mapped_column(Text, nullable=False)
    occurrences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="assinado") # rascunho, assinado, aprovado

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="daily_logs")

class AnalysisRun(Base):
    """Uma execução do motor regulatório sobre um projeto.

    Análises são *append-only*: cada avaliação cria um novo registro e nada é
    sobrescrito, para que o histórico de conformidade seja auditável (§3.5).
    """

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String, nullable=False)

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

    #: SHA-256 sobre o conteúdo canônico da análise (parâmetros + regras +
    #: resultados). Identifica a análise, não o arquivo PDF.
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")
    validations: Mapped[List["ValidationRecord"]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )

class ValidationRecord(Base):
    __tablename__ = "validation_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)

    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_title: Mapped[str] = mapped_column(String(255), nullable=False)
    field: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False) # conforme, nao_conforme, atencao, nao_aplicavel, nao_verificavel
    expected_value: Mapped[str] = mapped_column(String(100), nullable=False)
    actual_value: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # -- Proveniência e auditabilidade (§3.5) ------------------------------
    rule_state: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(50), default="regra_deterministica")
    source_document: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_article: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_citation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_required: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_publishable: Mapped[bool] = mapped_column(Boolean, default=False)

    validated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="validations")
