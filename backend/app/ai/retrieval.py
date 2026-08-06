"""Recuperação sobre o catálogo regulatório — o "R" do RAG (§6.8).

O corpus é o próprio catálogo: o modelo só enxerga regras cadastradas, nunca a
lei bruta. Essa restrição é deliberada e é o que sustenta a promessa de fonte
única (§3.4) — se a resposta tem de vir de uma regra do contexto, e o contexto
é o catálogo, então não existe caminho pelo qual uma citação inventada chegue
ao usuário.

A busca é **lexical**, não vetorial: sobreposição de termos normalizados, com
peso maior para o título e para o campo verificado. Para um catálogo municipal
— dezenas a poucas centenas de regras por jurisdição — isso recupera bem e não
introduz dependência de embeddings, serviço externo ou índice a manter. Quando
o catálogo crescer a ponto de a busca lexical errar, o lugar de trocar por
pgvector é aqui: a interface `retrieve()` não muda.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from app.regulatory.catalog import Rule

#: Palavras que aparecem em quase toda regra e não ajudam a distinguir.
STOPWORDS = {
    "a", "as", "o", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
    "nos", "nas", "para", "por", "com", "que", "qual", "quais", "um", "uma",
    "ao", "aos", "se", "sobre", "the", "minimo", "minima", "maximo", "maxima",
    "quanto", "quando", "onde", "como", "posso", "pode", "preciso", "qualquer",
    "meu", "minha", "e", "ou",
}

#: Sinônimos do jargão de aprovação. Um usuário escreve "afastamento" ou
#: "alinhamento predial"; o catálogo diz "recuo". Sem esta ponte, a busca
#: lexical falharia justamente nas consultas mais comuns.
SYNONYMS: Dict[str, Sequence[str]] = {
    "afastamento": ("recuo",),
    "alinhamento": ("recuo", "frontal"),
    "posterior": ("fundos",),
    "gabarito": ("pavimento", "altura", "floors"),
    "andar": ("pavimento",),
    "andares": ("pavimento",),
    "garagem": ("vaga", "estacionamento"),
    "vagas": ("vaga", "estacionamento"),
    "drenante": ("permeabilidade", "permeavel"),
    "solo": ("permeabilidade",),
    "impermeavel": ("permeabilidade",),
    "adensamento": ("ocupacao",),
    "construir": ("area", "construida"),
    "rampa": ("acessibilidade",),
    "nbr": ("acessibilidade",),
}


def fold(text: str) -> str:
    """Minúsculas sem acento — a consulta do usuário raramente os acerta."""
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def tokenize(text: str) -> List[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9_]+", fold(text))
        if token and token not in STOPWORDS and len(token) > 1
    ]


def expand(tokens: Iterable[str]) -> List[str]:
    """Acrescenta sinônimos do jargão, preservando os termos originais."""
    expanded = list(tokens)
    for token in list(tokens):
        expanded.extend(SYNONYMS.get(token, ()))
    return expanded


@dataclass
class RetrievedRule:
    rule: Rule
    score: float

    @property
    def rule_key(self) -> str:
        return self.rule.rule_id


def rule_terms(rule: Rule) -> Dict[str, float]:
    """Termos da regra com seus pesos.

    O título pesa mais que o resto porque é onde o vocabulário do usuário
    costuma bater; o campo verificado entra com peso alto por ser o que
    identifica a regra sem ambiguidade.
    """
    weighted: Dict[str, float] = {}

    def add(text: str, weight: float) -> None:
        for token in tokenize(text):
            weighted[token] = max(weighted.get(token, 0.0), weight)

    add(rule.title, 3.0)
    add(rule.rule_id.replace("_", " "), 2.0)
    if rule.check:
        add(str(rule.check.get("field", "")).replace("_", " "), 3.0)
    for zone in (rule.applies_to or {}).get("zone", []) or []:
        add(str(zone), 1.5)
    for kind in (rule.applies_to or {}).get("building_type", []) or []:
        add(str(kind).replace("_", " "), 1.0)
    for evidence in rule.evidence_required or []:
        add(str(evidence).replace("_", " "), 0.8)
    add(rule.notes or "", 0.5)

    return weighted


def retrieve(
    query: str, rules: Sequence[Rule], limit: int = 6, min_score: float = 1.0
) -> List[RetrievedRule]:
    """Regras mais próximas da pergunta, da mais relevante para a menos.

    Devolver lista vazia é um resultado legítimo e frequente: significa que o
    catálogo não cobre o assunto. O serviço trata isso dizendo que não sabe, em
    vez de mandar o modelo responder sem contexto.
    """
    query_tokens = expand(tokenize(query))
    if not query_tokens:
        return []

    scored: List[RetrievedRule] = []
    for rule in rules:
        terms = rule_terms(rule)
        score = sum(terms.get(token, 0.0) for token in set(query_tokens))
        if score <= 0:
            continue
        # Normaliza pelo tamanho da regra, para que uma regra com muitos termos
        # não vença apenas por ter mais superfície de colisão.
        score = score / math.sqrt(len(terms) or 1)
        scored.append(RetrievedRule(rule=rule, score=round(score, 4)))

    scored.sort(key=lambda item: (-item.score, item.rule.rule_id))
    best = scored[0].score if scored else 0.0
    # `min_score` é relativo ao melhor resultado: o que interessa é descartar a
    # cauda de coincidências fracas, não atingir um valor absoluto.
    cutoff = best / (min_score * 3)
    return [item for item in scored if item.score >= cutoff][:limit]


def format_context(retrieved: Sequence[RetrievedRule]) -> str:
    """Serializa as regras recuperadas para o prompt.

    Formato deliberadamente seco e rotulado: o modelo precisa conseguir apontar
    para uma chave, e o validador humano precisa reconhecer o que foi entregue
    ao ler a proveniência.
    """
    blocks: List[str] = []
    for item in retrieved:
        rule = item.rule
        linhas = [
            f"rule_key: {rule.rule_id}",
            f"titulo: {rule.title}",
            f"jurisdicao: {rule.jurisdiction}",
            f"estado: {rule.state}",
            f"severidade: {rule.severity}",
            f"limite: {rule.expected_label()}",
            f"fonte: {rule.source.citation()}",
            f"fonte_conferida: {'sim' if rule.source.is_verified else 'nao'}",
            f"validada_por: {rule.validated_by or 'ninguem — regra ainda nao validada'}",
        ]
        if rule.applies_to:
            linhas.append(f"aplica_se_a: {rule.applies_to}")
        if rule.evidence_required:
            linhas.append(f"evidencia_exigida: {', '.join(rule.evidence_required)}")
        if rule.requires_manual_review:
            linhas.append(
                f"analise_manual: {rule.manual_review_reason or 'exige conferencia tecnica'}"
            )
        blocks.append("\n".join(linhas))
    return "\n\n---\n\n".join(blocks)
