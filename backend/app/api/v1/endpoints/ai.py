"""Assistente normativo e extração assistida de regras (§3.3, §6.8).

Toda a lógica vive em `app.ai.service`. O que este arquivo garante é o
contorno: quem pode pedir o quê, e o que a resposta declara sobre si mesma.

A resposta sempre diz **como** foi produzida (`method`, `is_ai_generated`,
`model`), porque a diferença entre uma busca no catálogo e uma resposta de
modelo importa para quem vai usá-la em um protocolo. E nunca cita artigo de lei
por texto do modelo: a citação é resolvida a partir do catálogo, que é a fonte
única (§3.4).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import service as ai_service
from app.ai.provider import get_provider
from app.api.deps import get_current_user, require_permission
from app.core.database import get_db
from app.models.domain import AIInteraction, Project, RegulatoryDocument, User
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()


class AIChatRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=4000)
    project_id: Optional[str] = None


class AIChatResponse(BaseModel):
    answer: str
    law_citations: List[str] = []
    suggested_actions: List[str] = []
    matched_rules: List[str] = []
    disclaimer: str
    #: Falso quando a resposta veio da busca determinística no catálogo.
    is_ai_generated: bool = False
    method: str
    model: Optional[str] = None
    #: Falso quando o modelo referenciou regra fora do contexto entregue.
    grounded: bool = True
    warnings: List[str] = []
    interaction_id: Optional[str] = None
    served_from_cache: bool = False


class RuleDraftRequest(BaseModel):
    legal_text: str = Field(
        min_length=40,
        max_length=60000,
        description="Trecho do texto legal a partir do qual extrair regras.",
    )
    jurisdiction: str = Field(default="BR-RS-4311403")
    regulatory_document_id: Optional[str] = None


class RuleDraftResponse(BaseModel):
    created_rule_ids: List[str] = []
    drafts: List[dict] = []
    notes: Optional[str] = None
    interaction_id: Optional[str] = None
    error: Optional[str] = None
    #: Constante: rascunho de IA nasce e permanece em rascunho até validação.
    state: str = "rascunho_extraido_por_ia"
    reminder: str = (
        "Rascunhos não são aplicados pelo motor nem entram em laudo. Confira cada um "
        "contra o texto legal publicado e publique pela fila de validação (§7.5)."
    )


class AIStatusResponse(BaseModel):
    provider: str
    available: bool
    model: Optional[str] = None
    description: str


@router.get("/ai/status", response_model=AIStatusResponse)
def ai_status(user: User = Depends(get_current_user)):
    """Diz se há modelo por trás — a interface precisa poder ser honesta."""
    provider = get_provider()
    return AIStatusResponse(
        provider=provider.name,
        available=provider.available,
        model=getattr(provider, "model", None),
        description=provider.describe(),
    )


@router.post("/ai/chat", response_model=AIChatResponse)
def atlas_ai_chat(
    req: AIChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project: Optional[Project] = None
    if req.project_id:
        project = (
            db.query(Project)
            .filter(
                Project.id == req.project_id,
                Project.organization_id == user.organization_id,
            )
            .first()
        )

    # Situação das verificações do projeto, quando houver análise registrada.
    statuses = {}
    if project:
        run = RegulatoryEngine.latest_run(db, project.id)
        if run:
            statuses = {v.rule_id: v.status for v in run.validations}

    resposta = ai_service.ask(db, req.prompt, user, project=project, statuses=statuses)
    return AIChatResponse(**resposta.__dict__)


@router.post(
    "/ai/rule-drafts",
    response_model=RuleDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def extract_rule_drafts(
    req: RuleDraftRequest,
    user: User = Depends(require_permission("catalog:validate")),
    db: Session = Depends(get_db),
):
    """Propõe regras a partir de texto legal, como rascunho (§7.4).

    Restrito a quem valida o catálogo — não porque a extração publique algo
    (ela não publica), mas porque quem enfileira trabalho de conferência deve
    ser quem vai conferir.
    """
    document: Optional[RegulatoryDocument] = None
    if req.regulatory_document_id:
        document = (
            db.query(RegulatoryDocument)
            .filter(RegulatoryDocument.id == req.regulatory_document_id)
            .first()
        )
        if not document:
            raise HTTPException(
                status_code=404, detail="Documento regulatório não encontrado."
            )

    resultado = ai_service.extract_rule_drafts(
        db,
        legal_text=req.legal_text,
        jurisdiction=req.jurisdiction,
        user=user,
        document=document,
    )
    return RuleDraftResponse(
        created_rule_ids=resultado.created_rule_ids,
        drafts=resultado.drafts,
        notes=resultado.notes,
        interaction_id=resultado.interaction_id,
        error=resultado.error,
    )


@router.get("/ai/interactions", response_model=List[dict])
def list_ai_interactions(
    limit: int = 50,
    user: User = Depends(require_permission("catalog:validate")),
    db: Session = Depends(get_db),
):
    """Proveniência das consultas ao modelo (§3.5).

    Existe para responder à pergunta que aparece meses depois: *de onde saiu
    esta frase?*
    """
    registros = (
        db.query(AIInteraction)
        .filter(AIInteraction.organization_id == user.organization_id)
        .order_by(AIInteraction.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "purpose": r.purpose,
            "provider": r.provider,
            "model": r.model,
            "prompt": r.prompt,
            "retrieved_rule_keys": r.retrieved_rule_keys,
            "cited_rule_keys": r.cited_rule_keys,
            "grounded": r.grounded,
            "answer_is_advisory": r.answer_is_advisory,
            "served_from_cache": r.served_from_cache,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "latency_ms": r.latency_ms,
            "error": r.error,
            "created_by_id": r.created_by_id,
        }
        for r in registros
    ]
