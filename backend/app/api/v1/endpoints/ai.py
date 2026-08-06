"""Assistente de consulta ao catálogo regulatório.

Importante sobre o que este módulo **não** é: não há modelo de linguagem aqui.
É uma busca por palavra-chave sobre o catálogo — e a resposta diz isso ao
usuário, em vez de se apresentar como IA.

O módulo também não guarda nenhuma referência legal própria. Toda citação vem
do catálogo (`app/regulatory/data/*.yaml`), que é a fonte única. Foi a
duplicação dessas referências que produziu, no protótipo, artigos conflitantes
entre o motor e o assistente para o mesmo parâmetro.
"""

from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import Project
from app.regulatory.catalog import RuleState, catalog
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()

DISCLAIMER = (
    "Resposta gerada por busca determinística no catálogo regulatório do Atlas — "
    "não é interpretação jurídica, não substitui o responsável técnico e não "
    "constitui manifestação de órgão público."
)

#: Palavras-chave → regras do catálogo.
TOPIC_KEYWORDS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("recuo frontal", "frontal", "alinhamento"), "lajeado_recuo_frontal_z2"),
    (("fundos", "posterior"), "lajeado_recuo_fundos_z2"),
    (("ocupacao", "ocupação", "taxa de ocupacao", "taxa de ocupação"), "lajeado_taxa_ocupacao_max_z2"),
    (("permeabilidade", "permeavel", "permeável", "drenante", "solo"), "lajeado_taxa_permeabilidade_min_z2"),
    (("pavimento", "gabarito", "altura", "andar"), "lajeado_gabarito_maximo_z2"),
    (("vaga", "estacionamento", "garagem"), "lajeado_vagas_estacionamento"),
    (("acessibilidade", "nbr", "rampa", "9050"), "lajeado_acessibilidade_nbr9050"),
)

# "recuo" isolado cobre os dois recuos cadastrados.
BROAD_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("recuo", ("lajeado_recuo_frontal_z2", "lajeado_recuo_fundos_z2")),
    ("afastamento", ("lajeado_recuo_frontal_z2", "lajeado_recuo_fundos_z2")),
)


class AIChatRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None


class AIChatResponse(BaseModel):
    answer: str
    law_citations: List[str]
    suggested_actions: List[str]
    disclaimer: str = DISCLAIMER
    #: Falso por definição enquanto não houver camada de modelo (§6.8).
    is_ai_generated: bool = False
    method: str = "busca_por_palavra_chave_no_catalogo"
    matched_rules: List[str] = []


def _match_rule_ids(prompt: str) -> List[str]:
    lowered = prompt.lower()
    matched: List[str] = []

    for keywords, rule_id in TOPIC_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            matched.append(rule_id)

    for keyword, rule_ids in BROAD_KEYWORDS:
        if keyword in lowered:
            matched.extend(rule_ids)

    seen = set()
    return [r for r in matched if not (r in seen or seen.add(r))]


@router.post("/ai/chat", response_model=AIChatResponse)
def atlas_ai_chat(req: AIChatRequest, db: Session = Depends(get_db)):
    project: Optional[Project] = None
    if req.project_id:
        project = db.query(Project).filter(Project.id == req.project_id).first()

    jurisdiction = project.city_ibge if project else "BR-RS-4311403"
    municipality = project.city_name if project else "Lajeado"

    rule_ids = _match_rule_ids(req.prompt)
    rules = [r for r in (catalog.get(rule_id) for rule_id in rule_ids) if r]

    citations: List[str] = []
    actions: List[str] = []
    lines: List[str] = []

    # Estado das verificações do projeto, quando houver análise registrada.
    statuses: Dict[str, str] = {}
    if project:
        run = RegulatoryEngine.latest_run(db, project.id)
        if run:
            statuses = {v.rule_id: v.status for v in run.validations}

    if rules:
        lines.append(
            f"O catálogo regulatório do Atlas para {municipality} registra os "
            f"seguintes parâmetros relacionados à sua consulta:"
        )
        for rule in rules:
            limit = (
                rule.expected_label()
                if rule.check
                else "verificação documental (não derivável de parâmetros numéricos)"
            )
            pending = " — regra ainda não validada tecnicamente" if not rule.is_publishable else ""
            line = f"• {rule.title}: {limit}{pending}."
            if rule.rule_id in statuses:
                line += f" No empreendimento analisado, esta verificação está '{statuses[rule.rule_id]}'."
            lines.append(line)

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
        available = catalog.for_jurisdiction(jurisdiction)
        lines.append(
            f"Não encontrei no catálogo de {municipality} nenhum parâmetro "
            f"correspondente a '{req.prompt}'."
        )
        if available:
            lines.append(
                "Parâmetros cadastrados para esta jurisdição: "
                + "; ".join(rule.title for rule in available)
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

    unvalidated = [r for r in rules if r.state != RuleState.VIGENTE or not r.validated_by]
    if unvalidated:
        lines.append("")
        lines.append(
            f"Atenção: {len(unvalidated)} de {len(rules)} regra(s) citada(s) estão em "
            "validação e tiveram a referência de artigo removida por não terem sido "
            "conferidas contra o texto legal publicado. Não utilize estes valores como "
            "base para protocolo sem conferência do responsável técnico."
        )

    if project:
        lines.append("")
        lines.append(
            f"Empreendimento em contexto: '{project.name}' — {municipality}, "
            f"zona {project.zone}, lote {project.lot_area or 'não informado'} m², "
            f"área construída {project.built_area or 'não informado'} m²."
        )

    return AIChatResponse(
        answer="\n".join(lines),
        law_citations=citations,
        suggested_actions=actions,
        matched_rules=[rule.rule_id for rule in rules],
    )
