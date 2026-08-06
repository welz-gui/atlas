"""Carregamento e interpretação do catálogo regulatório (§7.2 a §7.6).

Regras são dado, não código. Este módulo lê os arquivos YAML de
`app/regulatory/data/`, valida a estrutura e expõe a execução determinística
de cada regra sobre um conjunto de parâmetros.

É também a **fonte única** das citações legais: nem o motor nem o assistente
podem manter suas próprias referências (era a origem das citações conflitantes
do protótipo).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import yaml

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# --- Estados da regra (§7.4) -------------------------------------------------

class RuleState:
    RASCUNHO_EXTRAIDO_POR_IA = "rascunho_extraido_por_ia"
    EM_VALIDACAO = "em_validacao"
    VIGENTE = "vigente"
    SUSPENSA = "suspensa"
    REVOGADA = "revogada"
    SUBSTITUIDA = "substituida"

    ALL = {
        RASCUNHO_EXTRAIDO_POR_IA,
        EM_VALIDACAO,
        VIGENTE,
        SUSPENSA,
        REVOGADA,
        SUBSTITUIDA,
    }


#: Estados cujas regras o motor pode executar.
#: `em_validacao` executa, mas o resultado é marcado como não publicável.
EXECUTABLE_STATES = {RuleState.EM_VALIDACAO, RuleState.VIGENTE}

#: Estados cujas regras podem constar de laudo entregue ao cliente (§7.5).
PUBLISHABLE_STATES = {RuleState.VIGENTE}


class Severity:
    BLOQUEIO = "bloqueio"
    ALERTA = "alerta"


# --- Estados da verificação (§7.7) -------------------------------------------

class CheckOutcome:
    CONFORME = "conforme"
    NAO_CONFORME = "nao_conforme"
    ATENCAO = "atencao"
    NAO_APLICAVEL = "nao_aplicavel"
    NAO_VERIFICAVEL = "nao_verificavel"


_OPERATORS = {
    ">=": lambda a, b, tol: a >= b - tol,
    "<=": lambda a, b, tol: a <= b + tol,
    ">": lambda a, b, tol: a > b - tol,
    "<": lambda a, b, tol: a < b + tol,
    "==": lambda a, b, tol: abs(a - b) <= tol,
    "!=": lambda a, b, tol: abs(a - b) > tol,
}


@dataclass
class RuleSource:
    document: Optional[str] = None
    article: Optional[str] = None
    url: Optional[str] = None
    consulted_at: Optional[str] = None

    @property
    def is_verified(self) -> bool:
        """Uma fonte só é verificada quando aponta para um artigo concreto."""
        return bool(self.document and self.article)

    def citation(self) -> str:
        if not self.document:
            return "Fonte não informada"
        if self.article:
            return f"{self.document}, {self.article}"
        return f"{self.document} (artigo não verificado)"


@dataclass
class Rule:
    rule_id: str
    title: str
    jurisdiction: str
    state: str
    severity: str
    applies_to: Dict[str, Any] = field(default_factory=dict)
    check: Optional[Dict[str, Any]] = None
    requires_manual_review: bool = False
    manual_review_reason: Optional[str] = None
    evidence_required: List[str] = field(default_factory=list)
    source: RuleSource = field(default_factory=RuleSource)
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    validated_by: Optional[str] = None
    validated_at: Optional[str] = None
    notes: Optional[str] = None

    # -- estado ------------------------------------------------------------
    @property
    def is_executable(self) -> bool:
        return self.state in EXECUTABLE_STATES

    @property
    def is_publishable(self) -> bool:
        """§7.5 — regra não validada não entra em laudo entregue ao cliente."""
        return self.state in PUBLISHABLE_STATES and self.validated_by is not None

    def is_in_force_on(self, reference: date) -> bool:
        if self.effective_from and reference < self.effective_from:
            return False
        if self.effective_until and reference > self.effective_until:
            return False
        return True

    # -- aplicabilidade ----------------------------------------------------
    def applies_to_project(self, params: Dict[str, Any], jurisdiction: str) -> bool:
        if jurisdiction != self.jurisdiction:
            return False
        for key, allowed in (self.applies_to or {}).items():
            if key == "conditions":
                continue
            if not allowed:
                continue
            if params.get(key) not in allowed:
                return False
        for condition in (self.applies_to or {}).get("conditions") or []:
            actual = params.get(condition["field"])
            if actual is None:
                return False
            op = _OPERATORS.get(condition["operator"])
            if op is None or not op(actual, condition["value"], 0):
                return False
        return True

    # -- descrição do limite ----------------------------------------------
    def expected_label(self) -> str:
        if not self.check:
            return "Análise documental / gráfica"
        return f"{self.check['operator']} {self.format_value(self.check['value'])}".strip()

    def format_value(self, value: Any) -> str:
        if value is None:
            return "não informado"
        unit = (self.check or {}).get("unit") or ""
        sep = "" if unit == "%" else " "
        if unit == "m":
            return f"{float(value):.2f}{sep}{unit}".strip()
        if unit == "%":
            return f"{float(value):.1f}{sep}{unit}".strip()
        return f"{value}{sep}{unit}".strip()

    # -- execução ----------------------------------------------------------
    def evaluate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executa a regra e devolve o resultado da verificação (§7.7)."""
        if self.requires_manual_review or not self.check:
            return {
                "outcome": CheckOutcome.NAO_VERIFICAVEL,
                "actual": None,
                "actual_label": "Pendente de análise técnica",
                "details": self.manual_review_reason
                or "Esta regra exige verificação manual sobre as pranchas do projeto.",
            }

        field_name = self.check["field"]
        actual = params.get(field_name)

        if actual is None:
            return {
                "outcome": CheckOutcome.NAO_VERIFICAVEL,
                "actual": None,
                "actual_label": "não informado",
                "details": (
                    f"O parâmetro '{field_name}' não foi informado no cadastro nem "
                    "extraído de documento. Sem evidência, o Atlas não emite verdicto."
                ),
            }

        operator = _OPERATORS.get(self.check["operator"])
        if operator is None:
            return {
                "outcome": CheckOutcome.NAO_VERIFICAVEL,
                "actual": actual,
                "actual_label": self.format_value(actual),
                "details": f"Operador '{self.check['operator']}' não suportado pelo motor.",
            }

        tolerance = self.check.get("tolerance") or 0
        passed = operator(actual, self.check["value"], tolerance)
        actual_label = self.format_value(actual)

        if passed:
            return {
                "outcome": CheckOutcome.CONFORME,
                "actual": actual,
                "actual_label": actual_label,
                "details": "Parâmetro dentro do limite previsto pela regra cadastrada.",
            }

        outcome = (
            CheckOutcome.NAO_CONFORME
            if self.severity == Severity.BLOQUEIO
            else CheckOutcome.ATENCAO
        )
        return {
            "outcome": outcome,
            "actual": actual,
            "actual_label": actual_label,
            "details": (
                f"O valor apurado ({actual_label}) não satisfaz o limite "
                f"{self.expected_label()}."
            ),
        }


class RegulatoryCatalog:
    """Coleção de regras carregadas dos arquivos YAML versionados."""

    def __init__(self, rules: List[Rule], versions: Dict[str, str]):
        self._rules = rules
        self.versions = versions

    # -- carregamento ------------------------------------------------------
    @classmethod
    def load(cls, data_dir: str = DATA_DIR) -> "RegulatoryCatalog":
        rules: List[Rule] = []
        versions: Dict[str, str] = {}

        if not os.path.isdir(data_dir):
            return cls(rules, versions)

        for filename in sorted(os.listdir(data_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            with open(os.path.join(data_dir, filename), "r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}

            jurisdiction = (payload.get("jurisdiction") or {}).get("code")
            if not jurisdiction:
                raise ValueError(f"{filename}: catálogo sem `jurisdiction.code`")
            versions[jurisdiction] = payload.get("catalog_version", "desconhecida")

            for raw in payload.get("rules") or []:
                rules.append(cls._parse_rule(raw, jurisdiction, filename))

        return cls(rules, versions)

    @staticmethod
    def _parse_rule(raw: Dict[str, Any], jurisdiction: str, filename: str) -> Rule:
        rule_id = raw.get("rule_id")
        if not rule_id:
            raise ValueError(f"{filename}: regra sem `rule_id`")

        state = raw.get("state")
        if state not in RuleState.ALL:
            raise ValueError(f"{filename}/{rule_id}: estado inválido '{state}' (§7.4)")

        severity = raw.get("severity", Severity.BLOQUEIO)
        if severity not in (Severity.BLOQUEIO, Severity.ALERTA):
            raise ValueError(f"{filename}/{rule_id}: severidade inválida '{severity}'")

        check = raw.get("check")
        if check is not None:
            for required in ("field", "operator", "value"):
                if required not in check:
                    raise ValueError(
                        f"{filename}/{rule_id}: `check` sem campo obrigatório '{required}'"
                    )

        return Rule(
            rule_id=rule_id,
            title=raw.get("title", rule_id),
            jurisdiction=jurisdiction,
            state=state,
            severity=severity,
            applies_to=raw.get("applies_to") or {},
            check=check,
            requires_manual_review=bool(raw.get("requires_manual_review", False)),
            manual_review_reason=raw.get("manual_review_reason"),
            evidence_required=raw.get("evidence_required") or [],
            source=RuleSource(**(raw.get("source") or {})),
            effective_from=raw.get("effective_from"),
            effective_until=raw.get("effective_until"),
            validated_by=raw.get("validated_by"),
            validated_at=raw.get("validated_at"),
            notes=raw.get("notes"),
        )

    # -- consulta ----------------------------------------------------------
    @property
    def all_rules(self) -> List[Rule]:
        return list(self._rules)

    def get(self, rule_id: str) -> Optional[Rule]:
        return next((r for r in self._rules if r.rule_id == rule_id), None)

    def for_jurisdiction(self, jurisdiction: str) -> List[Rule]:
        return [r for r in self._rules if r.jurisdiction == jurisdiction]

    def executable_for(
        self, jurisdiction: str, reference: Optional[date] = None
    ) -> List[Rule]:
        reference = reference or date.today()
        return [
            r
            for r in self.for_jurisdiction(jurisdiction)
            if r.is_executable and r.is_in_force_on(reference)
        ]

    def version_for(self, jurisdiction: str) -> str:
        return self.versions.get(jurisdiction, "desconhecida")


#: Catálogo carregado uma vez por processo.
catalog = RegulatoryCatalog.load()
