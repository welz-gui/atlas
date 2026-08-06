"""Contratos de saída do modelo (§3.3, §6.8).

Estes modelos Pydantic são passados ao provedor como *structured output*: o que
volta já chega validado, ou não chega. É o que impede a resposta de virar texto
livre em que uma citação legal se esconde no meio de um parágrafo.

Duas escolhas de modelagem carregam a política do produto:

- `cited_rule_keys` é uma lista de **chaves do catálogo**, não de artigos de
  lei. O modelo não pode citar "art. 45 do Plano Diretor"; ele aponta para uma
  regra cadastrada, e é o Atlas que resolve a citação a partir da fonte única.
  Assim, uma citação inventada não tem por onde entrar;
- `RuleDraft` não tem campo de estado. Rascunho extraído por IA nasce em
  `rascunho_extraido_por_ia` por construção, e quem o move dali é uma pessoa
  (§7.4, §7.5).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AssistantAnswer(BaseModel):
    """Resposta do assistente normativo."""

    answer: str = Field(
        description=(
            "Resposta objetiva em português do Brasil, baseada exclusivamente "
            "nas regras fornecidas no contexto. Se o contexto não contiver a "
            "resposta, diga isso explicitamente."
        )
    )
    cited_rule_keys: List[str] = Field(
        default_factory=list,
        description=(
            "Chaves (rule_key) das regras do contexto que sustentam a resposta. "
            "Use apenas chaves presentes no contexto."
        ),
    )
    suggested_actions: List[str] = Field(
        default_factory=list,
        description="Providências concretas para o responsável técnico.",
    )
    answered_from_context: bool = Field(
        description=(
            "Verdadeiro somente se a resposta se sustenta nas regras fornecidas. "
            "Falso quando o contexto era insuficiente."
        )
    )


class RuleDraftCheck(BaseModel):
    """A verificação numérica proposta, quando a norma admite uma."""

    field: str = Field(
        description=(
            "Parâmetro verificado. Um de: lot_area, built_area, floors, "
            "front_setback, side_setback, rear_setback, permeability_rate, "
            "parking_spaces, occupancy_rate."
        )
    )
    operator: str = Field(description="Um de: >=, <=, >, <, ==, !=")
    value: float = Field(description="Limite numérico previsto no texto legal.")
    unit: Optional[str] = Field(default=None, description="m, %, un — quando houver.")


class RuleDraft(BaseModel):
    """Rascunho de regra proposto a partir de um texto normativo.

    Nasce em `rascunho_extraido_por_ia`; nenhum campo aqui pode promovê-lo.
    """

    rule_key: str = Field(
        description="Identificador estável em snake_case, ex.: lajeado_recuo_frontal_z2."
    )
    title: str = Field(description="Título curto e descritivo da exigência.")
    severity: str = Field(
        description="'bloqueio' quando o descumprimento impede a aprovação; senão 'alerta'."
    )
    zones: List[str] = Field(
        default_factory=list, description="Zonas a que se aplica, se o texto especificar."
    )
    building_types: List[str] = Field(
        default_factory=list, description="Tipos de edificação, se o texto especificar."
    )
    check: Optional[RuleDraftCheck] = Field(
        default=None,
        description=(
            "Deixe nulo quando a exigência não for verificável por um número — "
            "nesses casos ela vira análise documental."
        ),
    )
    evidence_required: List[str] = Field(
        default_factory=list,
        description="Peças que comprovam o atendimento, ex.: implantacao, quadro_areas.",
    )
    source_article: Optional[str] = Field(
        default=None,
        description=(
            "Artigo, parágrafo ou inciso EXATAMENTE como aparece no texto fornecido. "
            "Deixe nulo se não houver identificação inequívoca no trecho."
        ),
    )
    verbatim_excerpt: str = Field(
        description=(
            "Trecho literal do texto fornecido que sustenta esta regra, copiado "
            "sem alteração. Serve para o validador conferir sem reabrir a lei."
        )
    )
    confidence: str = Field(description="alta, media ou baixa.")


class RuleDraftBatch(BaseModel):
    """Conjunto de rascunhos extraídos de um mesmo documento."""

    drafts: List[RuleDraft] = Field(default_factory=list)
    notes: Optional[str] = Field(
        default=None,
        description="Ressalvas sobre trechos ambíguos, remissões ou tabelas ilegíveis.",
    )
