"""Portal do cliente (§8.22).

Uma visão de leitura, montada para quem contratou a obra — não para quem a
executa. A diferença não é de layout: é de conteúdo, e a linha é traçada aqui,
no servidor, porque esconder no frontend não esconde nada.

O que o portal **não** entrega, e por quê:

- **Pré-análise não publicável.** Enquanto qualquer regra aplicada estiver em
  validação, o resultado da análise não sai daqui. É a mesma regra do laudo
  (§7.5): número não conferido contra a lei publicada não vira informação
  entregue ao cliente. O portal diz que a análise existe e está em conferência
  técnica — o que é verdade e é diferente de omitir.
- **Documentos obsoletos.** O cliente vê o que está vigente. Uma prancha
  substituída na mão de quem não acompanha o versionamento é fonte de erro.
- **Notas internas, proveniência de IA, trabalhos, catálogo.** Não são assunto
  do contratante.

O que ele entrega: onde o processo está, o que está pendente do lado dele, o
que já foi aprovado e o andamento físico.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_current_user, get_project_or_404, tenant_query
from app.core.database import get_db
from app.models.domain import (
    Document,
    DocumentState,
    EAPItem,
    Project,
    ProtocolProcess,
    RequirementStatus,
    TaskItem,
    User,
)
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()


# =============================================================================
# Contratos
# =============================================================================

class PortalDocument(BaseModel):
    id: str
    title: str
    category: str
    version: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PortalRequirement(BaseModel):
    """Exigência do órgão. O cliente precisa saber o que trava o processo."""

    description: str
    status: str
    raised_at: Optional[str] = None
    due_date: Optional[str] = None


class PortalProtocol(BaseModel):
    protocol_number: str
    agency: str
    status: str
    submitted_at: Optional[str] = None
    decided_at: Optional[str] = None
    open_requirements: List[PortalRequirement] = Field(default_factory=list)


class PortalMilestone(BaseModel):
    name: str
    progress_percent: float


class PortalComplianceSummary(BaseModel):
    """Resumo da conformidade — só quando pode ser entregue.

    `available` falso não significa "sem análise": significa que a análise
    existe mas depende de regras ainda em conferência técnica (§7.5). Dizer
    isso é mais honesto do que exibir número não conferido ou fingir que nada
    foi feito.
    """

    available: bool
    reason: Optional[str] = None
    analysed_at: Optional[datetime] = None
    project_version_number: Optional[int] = None
    total_checks: Optional[int] = None
    conforme_count: Optional[int] = None
    pending_count: Optional[int] = None
    blocking_count: Optional[int] = None


class PortalProject(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    district: Optional[str] = None
    city_name: str
    state: str
    licensing_status: str
    use_type: Optional[str] = None
    units_count: Optional[int] = None
    technical_responsible_name: Optional[str] = None

    version_number: Optional[int] = None
    version_state: Optional[str] = None
    has_official_baseline: bool = False

    physical_progress_percent: float = 0.0
    milestones: List[PortalMilestone] = Field(default_factory=list)
    open_tasks: int = 0

    current_documents: List[PortalDocument] = Field(default_factory=list)
    protocols: List[PortalProtocol] = Field(default_factory=list)
    compliance: PortalComplianceSummary

    notice: str = (
        "Esta é uma visão de acompanhamento. Ela não substitui o projeto aprovado, "
        "o alvará nem a manifestação do órgão licenciador."
    )


# =============================================================================
# Montagem
# =============================================================================

def _compliance(db: Session, project: Project) -> PortalComplianceSummary:
    run = RegulatoryEngine.latest_run(db, project.id)
    if run is None:
        return PortalComplianceSummary(
            available=False,
            reason="Ainda não há pré-análise regulatória registrada para este empreendimento.",
        )

    if not run.is_publishable:
        # §7.5 — a mesma regra do laudo. O portal reconhece a existência da
        # análise sem entregar número que ainda não foi conferido contra a lei.
        return PortalComplianceSummary(
            available=False,
            reason=(
                "A pré-análise foi executada, mas aplica parâmetros ainda em "
                "conferência técnica contra a legislação publicada. O resultado será "
                "liberado após a validação do responsável."
            ),
            analysed_at=run.created_at,
            project_version_number=run.project_version_number,
        )

    return PortalComplianceSummary(
        available=True,
        analysed_at=run.created_at,
        project_version_number=run.project_version_number,
        total_checks=run.total_checks,
        conforme_count=run.conforme_count,
        # "Pendente" reúne o que não foi possível verificar: para o cliente, a
        # distinção interna entre `atencao` e `nao_verificavel` não muda o que
        # ele precisa fazer — falta informação ao projeto.
        pending_count=run.nao_verificavel_count + run.atencao_count,
        blocking_count=run.nao_conforme_count,
    )


def _build(db: Session, project: Project, user: User) -> PortalProject:
    eap = (
        tenant_query(db, EAPItem, user)
        .filter(EAPItem.project_id == project.id)
        .order_by(EAPItem.code)
        .all()
    )
    # Progresso físico é a média simples das etapas cadastradas. Sem etapa
    # cadastrada o valor é zero — e zero aqui significa "nada medido", não
    # "obra parada". A interface diz isso.
    progress = round(sum(item.progress_percent for item in eap) / len(eap), 1) if eap else 0.0

    documents = (
        tenant_query(db, Document, user)
        .filter(
            Document.project_id == project.id,
            Document.status == DocumentState.VIGENTE,
        )
        .order_by(Document.created_at.desc())
        .all()
    )

    protocols = (
        tenant_query(db, ProtocolProcess, user)
        .filter(ProtocolProcess.project_id == project.id)
        .order_by(ProtocolProcess.created_at.desc())
        .all()
    )

    open_tasks = (
        tenant_query(db, TaskItem, user)
        .filter(TaskItem.project_id == project.id, TaskItem.status != "concluido")
        .count()
    )

    version = project.current_version

    return PortalProject(
        id=project.id,
        name=project.name,
        address=project.address,
        district=project.district,
        city_name=project.city_name,
        state=project.state,
        licensing_status=project.licensing_status,
        use_type=project.use_type,
        units_count=project.units_count,
        technical_responsible_name=project.technical_responsible_name,
        version_number=version.version_number if version else None,
        version_state=version.state if version else None,
        has_official_baseline=project.official_baseline is not None,
        physical_progress_percent=progress,
        milestones=[
            PortalMilestone(name=item.name, progress_percent=item.progress_percent)
            for item in eap
        ],
        open_tasks=open_tasks,
        current_documents=[PortalDocument.model_validate(d) for d in documents],
        protocols=[
            PortalProtocol(
                protocol_number=p.protocol_number,
                agency=p.agency,
                status=p.status,
                submitted_at=p.submitted_at,
                decided_at=p.decided_at,
                open_requirements=[
                    PortalRequirement(
                        description=r.description,
                        status=r.status,
                        raised_at=r.raised_at,
                        due_date=r.due_date,
                    )
                    for r in p.requirements
                    if r.status in RequirementStatus.OPEN
                ],
            )
            for p in protocols
        ],
        compliance=_compliance(db, project),
    )


# =============================================================================
# Rotas
# =============================================================================

@router.get("/portal/projects", response_model=List[PortalProject])
def portal_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Empreendimentos da organização, na visão de acompanhamento."""
    projects = (
        tenant_query(db, Project, user).order_by(Project.created_at.desc()).all()
    )
    return [_build(db, project, user) for project in projects]


@router.get("/portal/projects/{project_id}", response_model=PortalProject)
def portal_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id, user)
    return _build(db, project, user)
