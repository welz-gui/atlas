"""Assistente normativo e extração de rascunhos de regra (§3.3, §3.4, §6.8).

Este módulo é onde a política do produto vira código. Três regras governam
tudo o que acontece aqui:

**1. A IA não publica.** Ela propõe. Um rascunho extraído de texto legal nasce
em `rascunho_extraido_por_ia` e só sai desse estado pela mão de um validador
(§7.4, §7.5). Não há caminho — nem parâmetro, nem atalho de administrador —
que faça uma regra proposta por modelo entrar em laudo entregue ao cliente.

**2. A IA não cita a lei; ela aponta para o catálogo.** O modelo devolve
`rule_key`, não "art. 45". Toda chave devolvida é conferida contra o que foi
efetivamente entregue no contexto; chave que não estava lá é descartada, a
interação fica marcada como `grounded=False` e o usuário recebe o aviso. Uma
citação legal inventada é precisamente o dano que este sistema não pode
causar, então não basta pedir ao modelo que não invente: é preciso que não haja
por onde.

**3. A IA não emite veredicto.** Conformidade vem do motor determinístico
(§3.4). O assistente explica, localiza e sugere providências — e todas as
respostas saem com a ressalva de que não substituem o responsável técnico.

Sem provedor configurado nada disso deixa de funcionar: a resposta passa a vir
da busca determinística sobre o catálogo, e diz que veio.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.ai.provider import AIProvider, AIResult, get_provider
from app.ai.retrieval import RetrievedRule, format_context, retrieve
from app.ai.schemas import AssistantAnswer, RuleDraft, RuleDraftBatch
from app.core.config import settings
from app.models.domain import (
    AIInteraction,
    Project,
    RegulatoryDocument,
    RegulatoryRule,
    RuleValidationEvent,
    User,
)
from app.regulatory.catalog import RegulatoryCatalog, Rule, RuleState

DISCLAIMER = (
    "Resposta assistiva do Atlas — não é interpretação jurídica, não substitui o "
    "responsável técnico e não constitui manifestação de órgão público. "
    "A conformidade do empreendimento é determinada pelo motor de regras, não por "
    "este assistente."
)

#: Prefixo estável do sistema. Vai marcado para cache no provedor: é longo,
#: idêntico a cada consulta, e é ele que carrega a política.
ASSISTANT_POLICY = """\
Você assiste profissionais de arquitetura e engenharia na aprovação de projetos \
junto a prefeituras brasileiras, dentro do sistema Atlas.

Regras que você não pode quebrar:

1. Responda EXCLUSIVAMENTE com base nas regras do catálogo fornecidas no \
contexto. Não use conhecimento próprio sobre legislação urbanística brasileira, \
ainda que você acredite estar certo: o catálogo é a fonte única deste sistema.
2. NUNCA cite artigo, lei, decreto ou norma pelo número. Para sustentar uma \
afirmação, referencie a regra pela sua `rule_key`. O Atlas resolve a citação \
legal a partir do cadastro.
3. Se o contexto não contiver o que foi perguntado, diga que o catálogo não \
cobre o assunto e marque `answered_from_context` como falso. Não improvise: \
uma resposta plausível e errada custa mais caro que "não sei".
4. Você não emite veredicto de conformidade. Quem decide se o projeto atende \
é o motor determinístico do Atlas.
5. Quando uma regra do contexto tiver `validada_por: ninguem`, avise que o \
parâmetro ainda não foi conferido contra o texto legal publicado.

Escreva em português do Brasil, de forma direta e técnica.\
"""

EXTRACTION_POLICY = """\
Você extrai regras urbanísticas estruturadas a partir de texto legal, para \
conferência posterior por um responsável técnico do sistema Atlas.

Regras que você não pode quebrar:

1. Extraia APENAS o que está escrito no texto fornecido. Não complete lacunas \
com o que é usual em outros municípios.
2. `verbatim_excerpt` deve ser cópia literal do trecho, sem reescrita. É por \
ele que o validador confere seu trabalho sem reabrir a lei.
3. `source_article` só é preenchido quando o próprio texto identifica o \
dispositivo de forma inequívoca. Na dúvida, deixe nulo. Artigo errado é pior \
que artigo ausente.
4. Se a exigência não for verificável por um número — exige análise gráfica ou \
documental — deixe `check` nulo em vez de inventar um limite.
5. Marque `confidence` como baixa sempre que o trecho depender de remissão a \
outro artigo, de tabela não fornecida ou de interpretação.

Você está produzindo RASCUNHOS. Nenhuma regra que você propuser será aplicada \
antes de ser conferida e publicada por uma pessoa.\
"""


# =============================================================================
# Resultado do assistente
# =============================================================================

@dataclass
class AssistantResponse:
    answer: str
    law_citations: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    matched_rules: List[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    is_ai_generated: bool = False
    method: str = "busca_por_palavra_chave_no_catalogo"
    model: Optional[str] = None
    grounded: bool = True
    warnings: List[str] = field(default_factory=list)
    interaction_id: Optional[str] = None
    served_from_cache: bool = False


def _request_hash(prompt: str, rule_keys: Sequence[str], model: Optional[str]) -> str:
    """Identidade da pergunta: texto, contexto recuperado e modelo.

    O catálogo entra pelo conteúdo das regras, não só pelas chaves: uma regra
    corrigida invalida o cache, como deve.
    """
    payload = json.dumps(
        {"prompt": prompt.strip().lower(), "rules": sorted(rule_keys), "model": model},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _context_signature(retrieved: Sequence[RetrievedRule]) -> List[str]:
    """Assinatura das regras entregues, sensível ao conteúdo.

    Inclui estado, limite e validador: quando qualquer um deles muda, a
    resposta em cache deixa de valer — é o que impede o assistente de repetir
    "regra ainda não validada" depois de a regra ter sido publicada.
    """
    return [
        f"{item.rule.rule_id}|{item.rule.state}|{item.rule.expected_label()}|"
        f"{item.rule.validated_by or ''}"
        for item in retrieved
    ]


def _lookup_cache(
    db: Session, organization_id: str, request_hash: str
) -> Optional[AIInteraction]:
    if settings.AI_CACHE_HOURS <= 0:
        return None
    cutoff = datetime.utcnow() - timedelta(hours=settings.AI_CACHE_HOURS)
    return (
        db.query(AIInteraction)
        .filter(
            AIInteraction.organization_id == organization_id,
            AIInteraction.request_hash == request_hash,
            AIInteraction.error.is_(None),
            AIInteraction.grounded.is_(True),
            AIInteraction.created_at >= cutoff,
        )
        .order_by(AIInteraction.created_at.desc())
        .first()
    )


def _record(
    db: Session,
    *,
    organization_id: str,
    user: Optional[User],
    project: Optional[Project],
    purpose: str,
    prompt: str,
    request_hash: str,
    retrieved_keys: Sequence[str],
    cited_keys: Sequence[str] = (),
    result: Optional[AIResult] = None,
    response_json: Optional[dict] = None,
    grounded: bool = True,
    served_from_cache: bool = False,
    provider_name: str = "none",
) -> AIInteraction:
    """Grava a proveniência. Chamado em todos os caminhos, inclusive nas falhas."""
    interaction = AIInteraction(
        organization_id=organization_id,
        project_id=project.id if project else None,
        purpose=purpose,
        provider=result.provider if result else provider_name,
        model=result.model if result else None,
        prompt=prompt,
        request_hash=request_hash,
        retrieved_rule_keys=list(retrieved_keys),
        cited_rule_keys=list(cited_keys),
        response_text=result.text if result else None,
        response_json=response_json,
        stop_reason=result.stop_reason if result else None,
        input_tokens=result.input_tokens if result else None,
        output_tokens=result.output_tokens if result else None,
        latency_ms=result.latency_ms if result else None,
        grounded=grounded,
        served_from_cache=served_from_cache,
        error=result.error if result else None,
        created_by_id=user.id if user else None,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


# =============================================================================
# Resposta determinística — o piso, não o improviso
# =============================================================================

def _unvalidated_warning(rules: Sequence[Rule]) -> Optional[str]:
    pendentes = [r for r in rules if not r.is_publishable]
    if not pendentes:
        return None
    return (
        f"{len(pendentes)} de {len(rules)} regra(s) citada(s) ainda estão em validação "
        "e tiveram a referência de artigo omitida por não terem sido conferidas contra "
        "o texto legal publicado. Não utilize estes valores como base para protocolo "
        "sem conferência do responsável técnico."
    )


def deterministic_answer(
    query: str,
    retrieved: Sequence[RetrievedRule],
    catalog: RegulatoryCatalog,
    jurisdiction: str,
    municipality: str,
    statuses: Optional[Dict[str, str]] = None,
    project: Optional[Project] = None,
) -> AssistantResponse:
    """Resposta montada a partir do catálogo, sem modelo de linguagem.

    É o que responde quando não há provedor configurado, quando o provedor
    falha e quando a resposta do modelo não se sustenta no contexto. Não é um
    consolo: é a garantia de que o sistema continua dizendo apenas o que está
    cadastrado.
    """
    statuses = statuses or {}
    lines: List[str] = []
    citations: List[str] = []
    actions: List[str] = []

    if retrieved:
        lines.append(
            f"O catálogo regulatório do Atlas para {municipality} registra os "
            f"seguintes parâmetros relacionados à sua consulta:"
        )
        for item in retrieved:
            rule = item.rule
            limite = (
                rule.expected_label()
                if rule.check
                else "verificação documental (não derivável de parâmetros numéricos)"
            )
            pendente = "" if rule.is_publishable else " — regra ainda não validada tecnicamente"
            linha = f"• {rule.title}: {limite}{pendente}."
            if rule.rule_id in statuses:
                linha += (
                    f" No empreendimento analisado, esta verificação está "
                    f"'{statuses[rule.rule_id]}'."
                )
            lines.append(linha)
            citations.append(f"{rule.title} — {rule.source.citation()}")
            if rule.check:
                actions.append(
                    f"Conferir '{rule.check['field']}' no projeto contra o limite "
                    f"{rule.expected_label()} e anexar evidência: "
                    f"{', '.join(rule.evidence_required) or 'não especificada'}."
                )
            else:
                actions.append(
                    f"Providenciar análise técnica de {rule.title.lower()} "
                    f"({', '.join(rule.evidence_required) or 'evidência não especificada'})."
                )
    else:
        disponiveis = catalog.for_jurisdiction(jurisdiction)
        lines.append(
            f"Não encontrei no catálogo de {municipality} nenhum parâmetro "
            f"correspondente a '{query}'."
        )
        if disponiveis:
            lines.append(
                "Parâmetros cadastrados para esta jurisdição: "
                + "; ".join(rule.title for rule in disponiveis)
                + "."
            )
        citations.append(
            f"Catálogo regulatório de {municipality} "
            f"(versão {catalog.version_for(jurisdiction)})"
        )
        actions.append(
            "Reformule a consulta usando um dos parâmetros cadastrados, ou solicite "
            "o cadastro da norma faltante ao responsável pelo catálogo."
        )

    # O aviso de regra não validada faz parte da resposta, não de um rodapé
    # que a interface possa deixar de mostrar (§7.5).
    aviso = _unvalidated_warning([item.rule for item in retrieved])
    warnings: List[str] = []
    if aviso:
        warnings.append(aviso)
        lines.append("")
        lines.append(f"Atenção: {aviso}")

    if project:
        version = project.current_version
        lines.append("")
        lines.append(
            f"Empreendimento em contexto: '{project.name}' — {municipality}, "
            f"zona {version.zone if version else '—'}, "
            f"lote {(version.lot_area if version else None) or 'não informado'} m², "
            f"área construída {(version.built_area if version else None) or 'não informado'} m²."
        )

    return AssistantResponse(
        answer="\n".join(lines),
        law_citations=citations,
        suggested_actions=actions,
        matched_rules=[item.rule.rule_id for item in retrieved],
        is_ai_generated=False,
        method="busca_por_palavra_chave_no_catalogo",
        warnings=warnings,
    )


# =============================================================================
# Assistente
# =============================================================================

def ask(
    db: Session,
    query: str,
    user: User,
    project: Optional[Project] = None,
    statuses: Optional[Dict[str, str]] = None,
    provider: Optional[AIProvider] = None,
) -> AssistantResponse:
    """Responde a uma consulta normativa, com proveniência registrada."""
    jurisdiction = project.city_ibge if project else "BR-RS-4311403"
    municipality = project.city_name if project else "Lajeado"

    catalog = RegulatoryCatalog.from_db(db, jurisdiction)
    candidatas = catalog.for_jurisdiction(jurisdiction)
    retrieved = retrieve(query, candidatas)
    retrieved_keys = [item.rule.rule_id for item in retrieved]

    engine = provider or get_provider()
    baseline = deterministic_answer(
        query, retrieved, catalog, jurisdiction, municipality, statuses, project
    )

    if not engine.available:
        baseline.interaction_id = _record(
            db,
            organization_id=user.organization_id,
            user=user,
            project=project,
            purpose="consulta_normativa",
            prompt=query,
            request_hash=_request_hash(query, _context_signature(retrieved), None),
            retrieved_keys=retrieved_keys,
            cited_keys=retrieved_keys,
            provider_name=engine.name,
        ).id
        return baseline

    request_hash = _request_hash(
        query, _context_signature(retrieved), getattr(engine, "model", None)
    )

    cached = _lookup_cache(db, user.organization_id, request_hash)
    if cached and cached.response_json:
        resposta = AssistantResponse(**cached.response_json)
        resposta.interaction_id = cached.id
        resposta.served_from_cache = True
        return resposta

    if not retrieved:
        # Sem contexto não se pergunta ao modelo: seria convidá-lo a preencher
        # a lacuna com conhecimento próprio, que é exatamente o que a política
        # proíbe. A resposta determinística já diz que o catálogo não cobre.
        baseline.warnings.append(
            "O catálogo não cobre este assunto; o modelo não foi consultado para "
            "evitar resposta sem base cadastrada."
        )
        baseline.interaction_id = _record(
            db,
            organization_id=user.organization_id,
            user=user,
            project=project,
            purpose="consulta_normativa",
            prompt=query,
            request_hash=request_hash,
            retrieved_keys=[],
            provider_name=engine.name,
        ).id
        return baseline

    contexto = format_context(retrieved)
    prompt = (
        f"Município: {municipality} (jurisdição {jurisdiction}).\n\n"
        f"REGRAS DO CATÁLOGO DISPONÍVEIS:\n\n{contexto}\n\n"
        f"PERGUNTA DO USUÁRIO:\n{query}"
    )

    result = engine.complete(
        system=f"Consulta normativa para {municipality}.",
        prompt=prompt,
        output_model=AssistantAnswer,
        cacheable_prefix=ASSISTANT_POLICY,
    )

    if not result.ok:
        # Falha ou recusa do modelo devolve a resposta determinística — com o
        # motivo à vista, nunca disfarçada de resposta de IA.
        baseline.warnings.append(
            result.error or "O modelo não respondeu; usando busca no catálogo."
        )
        baseline.interaction_id = _record(
            db,
            organization_id=user.organization_id,
            user=user,
            project=project,
            purpose="consulta_normativa",
            prompt=query,
            request_hash=request_hash,
            retrieved_keys=retrieved_keys,
            cited_keys=retrieved_keys,
            result=result,
        ).id
        return baseline

    parsed: AssistantAnswer = result.parsed  # type: ignore[assignment]

    # Conferência: chave citada que não estava no contexto é descartada.
    permitidas = set(retrieved_keys)
    citadas = [key for key in parsed.cited_rule_keys if key in permitidas]
    inventadas = [key for key in parsed.cited_rule_keys if key not in permitidas]
    grounded = not inventadas and parsed.answered_from_context

    if inventadas:
        baseline.warnings.append(
            "A resposta do modelo referenciou regra fora do catálogo consultado e foi "
            "substituída pela consulta determinística."
        )
        baseline.interaction_id = _record(
            db,
            organization_id=user.organization_id,
            user=user,
            project=project,
            purpose="consulta_normativa",
            prompt=query,
            request_hash=request_hash,
            retrieved_keys=retrieved_keys,
            cited_keys=citadas,
            result=result,
            response_json=parsed.model_dump(),
            grounded=False,
        ).id
        return baseline

    if not parsed.answered_from_context:
        # O próprio modelo disse que o contexto não bastava. Melhor entregar o
        # que o catálogo tem do que uma resposta que ele mesmo não sustenta.
        baseline.warnings.append(
            "O modelo indicou que o catálogo não sustenta uma resposta completa para "
            "esta consulta."
        )
        baseline.interaction_id = _record(
            db,
            organization_id=user.organization_id,
            user=user,
            project=project,
            purpose="consulta_normativa",
            prompt=query,
            request_hash=request_hash,
            retrieved_keys=retrieved_keys,
            cited_keys=citadas,
            result=result,
            response_json=parsed.model_dump(),
            grounded=True,
        ).id
        return baseline

    # A citação legal é resolvida pelo Atlas, a partir do catálogo — nunca pelo
    # texto que o modelo escreveu.
    regras_citadas = [item.rule for item in retrieved if item.rule.rule_id in citadas]
    citacoes = [f"{r.title} — {r.source.citation()}" for r in regras_citadas]

    warnings: List[str] = []
    aviso = _unvalidated_warning(regras_citadas)
    if aviso:
        warnings.append(aviso)

    resposta = AssistantResponse(
        answer=parsed.answer,
        law_citations=citacoes,
        suggested_actions=list(parsed.suggested_actions),
        matched_rules=citadas,
        is_ai_generated=True,
        method="modelo_de_linguagem_sobre_catalogo",
        model=result.model,
        grounded=grounded,
        warnings=warnings,
    )

    interaction = _record(
        db,
        organization_id=user.organization_id,
        user=user,
        project=project,
        purpose="consulta_normativa",
        prompt=query,
        request_hash=request_hash,
        retrieved_keys=retrieved_keys,
        cited_keys=citadas,
        result=result,
        response_json={
            k: v
            for k, v in resposta.__dict__.items()
            if k not in {"interaction_id", "served_from_cache"}
        },
        grounded=True,
    )
    resposta.interaction_id = interaction.id
    return resposta


# =============================================================================
# Extração de rascunhos de regra
# =============================================================================

@dataclass
class DraftResult:
    created_rule_ids: List[str] = field(default_factory=list)
    drafts: List[Dict[str, Any]] = field(default_factory=list)
    notes: Optional[str] = None
    interaction_id: Optional[str] = None
    error: Optional[str] = None


def _draft_to_rule(
    draft: RuleDraft, jurisdiction: str, document: Optional[RegulatoryDocument]
) -> RegulatoryRule:
    """Converte o rascunho em linha do catálogo — sempre em estado de rascunho.

    `state` não vem do modelo: é fixado aqui. E `source_article` entra sem
    marcar a fonte como conferida, porque `is_verified` exige documento **e**
    artigo validados por pessoa (§7.5).
    """
    applies_to: Dict[str, Any] = {}
    if draft.zones:
        applies_to["zone"] = draft.zones
    if draft.building_types:
        applies_to["building_type"] = draft.building_types

    check = None
    if draft.check:
        check = {
            "field": draft.check.field,
            "operator": draft.check.operator,
            "value": draft.check.value,
            "unit": draft.check.unit,
        }

    return RegulatoryRule(
        rule_key=draft.rule_key,
        jurisdiction=jurisdiction,
        title=draft.title,
        state=RuleState.RASCUNHO_EXTRAIDO_POR_IA,
        severity=draft.severity if draft.severity in {"bloqueio", "alerta"} else "alerta",
        applies_to=applies_to,
        check=check,
        requires_manual_review=check is None,
        manual_review_reason=(
            None if check else "Exigência não verificável por parâmetro numérico."
        ),
        evidence_required=list(draft.evidence_required),
        source_document_id=document.id if document else None,
        source_document_label=document.title if document else None,
        source_article=draft.source_article,
        notes=(
            f"Rascunho extraído por modelo de linguagem (confiança: {draft.confidence}).\n"
            f"Trecho de origem: «{draft.verbatim_excerpt}»\n"
            "Conferir contra o texto legal publicado antes de publicar."
        ),
    )


def extract_rule_drafts(
    db: Session,
    legal_text: str,
    jurisdiction: str,
    user: User,
    document: Optional[RegulatoryDocument] = None,
    provider: Optional[AIProvider] = None,
) -> DraftResult:
    """Propõe regras a partir de texto legal — como rascunho, sempre.

    O resultado entra na fila de validação humana (§7.5). Regra com `rule_key`
    já existente na jurisdição é ignorada: sobrescrever cadastro publicado a
    partir de saída de modelo seria alterar a base legal sem que ninguém
    tivesse conferido.
    """
    engine = provider or get_provider()
    request_hash = _request_hash(legal_text, [jurisdiction], getattr(engine, "model", None))

    if not engine.available:
        return DraftResult(
            error=(
                "Nenhum provedor de modelo configurado. A extração de rascunhos exige "
                "AI_PROVIDER configurado; o cadastro manual continua disponível."
            ),
            interaction_id=_record(
                db,
                organization_id=user.organization_id,
                user=user,
                project=None,
                purpose="extracao_de_regra",
                prompt=legal_text[:4000],
                request_hash=request_hash,
                retrieved_keys=[],
                provider_name=engine.name,
            ).id,
        )

    result = engine.complete(
        system=f"Extração de regras urbanísticas para a jurisdição {jurisdiction}.",
        prompt=f"TEXTO LEGAL:\n\n{legal_text}",
        output_model=RuleDraftBatch,
        max_tokens=8192,
        cacheable_prefix=EXTRACTION_POLICY,
    )

    if not result.ok:
        return DraftResult(
            error=result.error or "O modelo não produziu rascunhos.",
            interaction_id=_record(
                db,
                organization_id=user.organization_id,
                user=user,
                project=None,
                purpose="extracao_de_regra",
                prompt=legal_text[:4000],
                request_hash=request_hash,
                retrieved_keys=[],
                result=result,
            ).id,
        )

    batch: RuleDraftBatch = result.parsed  # type: ignore[assignment]
    criadas: List[str] = []

    for draft in batch.drafts:
        existente = (
            db.query(RegulatoryRule)
            .filter(
                RegulatoryRule.jurisdiction == jurisdiction,
                RegulatoryRule.rule_key == draft.rule_key,
            )
            .first()
        )
        if existente:
            continue

        rule = _draft_to_rule(draft, jurisdiction, document)
        db.add(rule)
        db.flush()
        db.add(
            RuleValidationEvent(
                rule_id=rule.id,
                from_state=None,
                to_state=RuleState.RASCUNHO_EXTRAIDO_POR_IA,
                action="extraida_por_ia",
                notes=(
                    f"Extraída por {result.provider}/{result.model} a partir de texto "
                    f"legal enviado por {user.name}. Aguarda conferência humana."
                ),
                actor_id=user.id,
                actor_name=user.name,
            )
        )
        criadas.append(rule.id)

    db.commit()

    interaction = _record(
        db,
        organization_id=user.organization_id,
        user=user,
        project=None,
        purpose="extracao_de_regra",
        prompt=legal_text[:4000],
        request_hash=request_hash,
        retrieved_keys=[],
        cited_keys=[d.rule_key for d in batch.drafts],
        result=result,
        response_json=batch.model_dump(),
    )

    return DraftResult(
        created_rule_ids=criadas,
        drafts=[d.model_dump() for d in batch.drafts],
        notes=batch.notes,
        interaction_id=interaction.id,
    )
