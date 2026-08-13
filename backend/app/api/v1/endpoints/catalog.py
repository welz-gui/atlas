"""Catálogo regulatório e validação técnica de regras (§7, §15.12).

A fila de validação é o que destrava a publicação: enquanto uma regra não for
conferida contra o texto legal por um responsável identificado, ela executa mas
não pode constar de laudo entregue ao cliente (§7.5).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.database import get_db
from app.models.domain import (
    RegulatoryDocument,
    RegulatoryDocumentState,
    RegulatoryRule,
    RuleValidationEvent,
    User,
)
from app.regulatory.catalog import ALLOWED_TRANSITIONS, Rule, RuleState
from app.regulatory.jurisdiction import jurisdiction_chain
from app.regulatory.importer import import_seed_catalog
from app.schemas.domain import (
    CatalogImportResponse,
    RegulatoryDocumentCreate,
    RegulatoryDocumentResponse,
    RegulatoryRuleResponse,
    RuleValidationEventResponse,
    RuleValidationRequest,
)

router = APIRouter()

#: Ação da tela de validação → estado de destino.
ACTION_TARGET_STATE = {
    "publicar": RuleState.VIGENTE,
    "rejeitar": RuleState.RASCUNHO_EXTRAIDO_POR_IA,
    "suspender": RuleState.SUSPENSA,
    "revogar": RuleState.REVOGADA,
    "reabrir": RuleState.EM_VALIDACAO,
}


def _to_response(row: RegulatoryRule) -> RegulatoryRuleResponse:
    rule: Rule = Rule.from_orm(row)
    payload = RegulatoryRuleResponse.model_validate(row)
    payload.is_executable = rule.is_executable
    payload.is_publishable = rule.is_publishable
    return payload


# --- Regras ------------------------------------------------------------------

@router.get("/catalog/rules", response_model=List[RegulatoryRuleResponse])
def list_rules(
    jurisdiction: Optional[str] = None,
    state: Optional[str] = Query(default=None, description="Filtra por estado (§7.4)"),
    user: User = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    query = db.query(RegulatoryRule)
    if jurisdiction:
        query = query.filter(RegulatoryRule.jurisdiction.in_(jurisdiction_chain(jurisdiction)))
    if state:
        query = query.filter(RegulatoryRule.state == state)
    return [_to_response(row) for row in query.order_by(RegulatoryRule.rule_key).all()]


@router.get("/catalog/validation-queue", response_model=List[RegulatoryRuleResponse])
def validation_queue(
    jurisdiction: Optional[str] = None,
    user: User = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    """Regras aguardando conferência humana."""
    query = db.query(RegulatoryRule).filter(
        RegulatoryRule.state.in_([RuleState.EM_VALIDACAO, RuleState.RASCUNHO_EXTRAIDO_POR_IA])
    )
    if jurisdiction:
        query = query.filter(RegulatoryRule.jurisdiction.in_(jurisdiction_chain(jurisdiction)))
    return [_to_response(row) for row in query.order_by(RegulatoryRule.rule_key).all()]


@router.get("/catalog/rules/{rule_id}", response_model=RegulatoryRuleResponse)
def get_rule(
    rule_id: str,
    user: User = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    row = db.query(RegulatoryRule).filter(RegulatoryRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    return _to_response(row)


@router.get(
    "/catalog/rules/{rule_id}/events", response_model=List[RuleValidationEventResponse]
)
def list_rule_events(
    rule_id: str,
    user: User = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    return (
        db.query(RuleValidationEvent)
        .filter(RuleValidationEvent.rule_id == rule_id)
        .order_by(RuleValidationEvent.created_at.desc())
        .all()
    )


@router.post("/catalog/rules/{rule_id}/validate", response_model=RegulatoryRuleResponse)
def validate_rule(
    rule_id: str,
    payload: RuleValidationRequest,
    user: User = Depends(require_permission("catalog:validate")),
    db: Session = Depends(get_db),
):
    """Registra o ato de validação técnica de uma regra.

    Publicar exige fonte legal conferida — documento **e** artigo. É a
    contrapartida de §7.5: quem publica assume a responsabilidade técnica, e a
    regra passa a poder constar de laudo entregue ao cliente.
    """
    row = db.query(RegulatoryRule).filter(RegulatoryRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")

    target_state = ACTION_TARGET_STATE.get(payload.action)
    if target_state is None:
        raise HTTPException(
            status_code=422,
            detail=f"Ação inválida. Válidas: {', '.join(sorted(ACTION_TARGET_STATE))}",
        )

    allowed = ALLOWED_TRANSITIONS.get(row.state, set())
    if target_state not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transição não permitida: '{row.state}' → '{target_state}'. "
                f"A partir de '{row.state}', os destinos possíveis são: "
                f"{', '.join(sorted(allowed)) or 'nenhum (estado terminal)'}."
            ),
        )

    previous_state = row.state

    if target_state == RuleState.VIGENTE:
        source_document_id = payload.source_document_id or row.source_document_id
        source_article = payload.source_article or row.source_article

        if not source_document_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Para publicar uma regra é obrigatório vincular o documento "
                    "regulatório de origem (source_document_id)."
                ),
            )
        document = (
            db.query(RegulatoryDocument)
            .filter(RegulatoryDocument.id == source_document_id)
            .first()
        )
        if not document:
            raise HTTPException(
                status_code=422, detail="Documento regulatório não encontrado."
            )
        if not source_article:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Para publicar uma regra é obrigatório informar o artigo conferido "
                    "no texto legal (source_article). Sem artigo, a fonte permanece "
                    "não verificada e a regra não pode ser vigente."
                ),
            )

        row.source_document_id = source_document_id
        row.source_article = source_article
        row.source_document_label = document.title
        row.validated_by_id = user.id
        row.validated_by_name = user.name
        row.validated_at = datetime.utcnow()
        if payload.effective_from:
            row.effective_from = payload.effective_from
    else:
        # Sair de vigente retira a validação: a regra deixa de ser publicável.
        row.validated_by_id = None
        row.validated_by_name = None
        row.validated_at = None

    row.state = target_state
    if payload.notes:
        row.notes = payload.notes

    db.add(
        RuleValidationEvent(
            rule_id=row.id,
            from_state=previous_state,
            to_state=target_state,
            action=payload.action,
            notes=payload.notes,
            actor_id=user.id,
            actor_name=user.name,
        )
    )
    db.commit()
    db.refresh(row)
    return _to_response(row)


# --- Documentos regulatórios -------------------------------------------------

@router.get("/catalog/documents", response_model=List[RegulatoryDocumentResponse])
def list_regulatory_documents(
    jurisdiction: Optional[str] = None,
    user: User = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    query = db.query(RegulatoryDocument)
    if jurisdiction:
        query = query.filter(
            RegulatoryDocument.jurisdiction.in_(jurisdiction_chain(jurisdiction))
        )
    return query.order_by(RegulatoryDocument.title).all()


@router.post(
    "/catalog/documents",
    response_model=RegulatoryDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_regulatory_document(
    payload: RegulatoryDocumentCreate,
    user: User = Depends(require_permission("catalog:validate")),
    db: Session = Depends(get_db),
):
    if payload.state not in RegulatoryDocumentState.ALL:
        raise HTTPException(
            status_code=422,
            detail=(
                "Estado inválido. Válidos: "
                f"{', '.join(sorted(RegulatoryDocumentState.ALL))}"
            ),
        )

    document = RegulatoryDocument(**payload.model_dump(), consulted_at=datetime.utcnow())
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/catalog/import", response_model=CatalogImportResponse)
def import_catalog(
    user: User = Depends(require_permission("catalog:validate")),
    db: Session = Depends(get_db),
):
    """Reimporta os arquivos de semente.

    Regras já publicadas por um validador não são sobrescritas.
    """
    return CatalogImportResponse(**import_seed_catalog(db))
