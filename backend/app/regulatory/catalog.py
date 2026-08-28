"""Catálogo regulatório: execução de regras e ponte com a persistência (§7).

A lógica de execução vive em `Rule`, uma estrutura pura, sem dependência de
banco. A tabela `regulatory_rules` é a fonte de verdade em produção; os
arquivos YAML de `data/` são **semente de importação**, úteis para versionar o
cadastro inicial de um município em revisão de código.

Este módulo é também a fonte única das citações legais — nem o motor nem o
assistente mantêm referências próprias.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy.orm import Session

from app.regulatory.jurisdiction import jurisdiction_chain

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


#: Estados cujas regras o motor pode executar. `em_validacao` executa, mas o
#: resultado é marcado como não publicável.
EXECUTABLE_STATES = {RuleState.EM_VALIDACAO, RuleState.VIGENTE}

#: Estados cujas regras podem constar de laudo entregue ao cliente (§7.5).
PUBLISHABLE_STATES = {RuleState.VIGENTE}

#: Transições permitidas no fluxo de validação humana.
ALLOWED_TRANSITIONS: Dict[str, set] = {
    RuleState.RASCUNHO_EXTRAIDO_POR_IA: {RuleState.EM_VALIDACAO, RuleState.REVOGADA},
    RuleState.EM_VALIDACAO: {
        RuleState.VIGENTE,
        RuleState.RASCUNHO_EXTRAIDO_POR_IA,
        RuleState.REVOGADA,
    },
    RuleState.VIGENTE: {RuleState.SUSPENSA, RuleState.REVOGADA, RuleState.SUBSTITUIDA},
    RuleState.SUSPENSA: {RuleState.VIGENTE, RuleState.EM_VALIDACAO, RuleState.REVOGADA},
    RuleState.REVOGADA: set(),
    RuleState.SUBSTITUIDA: set(),
}


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
    catalog_version: str = "0.1.0"

    # -- construção --------------------------------------------------------
    @classmethod
    def from_orm(cls, row: Any) -> "Rule":
        """Constrói a regra executável a partir da linha de `regulatory_rules`."""
        document_label = row.source_document_label
        if row.source_document is not None:
            document_label = row.source_document.title

        return cls(
            rule_id=row.rule_key,
            title=row.title,
            jurisdiction=row.jurisdiction,
            state=row.state,
            severity=row.severity,
            applies_to=row.applies_to or {},
            check=row.check,
            requires_manual_review=bool(row.requires_manual_review),
            manual_review_reason=row.manual_review_reason,
            evidence_required=list(row.evidence_required or []),
            source=RuleSource(
                document=document_label,
                article=row.source_article,
                url=row.source_document.url if row.source_document else None,
            ),
            effective_from=_parse_date(row.effective_from),
            effective_until=_parse_date(row.effective_until),
            validated_by=row.validated_by_name,
            validated_at=row.validated_at.isoformat() if row.validated_at else None,
            notes=row.notes,
            catalog_version=row.catalog_version,
        )

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
        if self.jurisdiction not in jurisdiction_chain(jurisdiction):
            return False
        for key, allowed in (self.applies_to or {}).items():
            if key == "conditions" or not allowed:
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
        return (
            f"{self.check['operator']} {self.format_value(self.check['value'])}".strip()
        )

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


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


class RegulatoryCatalog:
    """Coleção de regras executáveis."""

    def __init__(self, rules: List[Rule], versions: Dict[str, str]):
        self._rules = rules
        self.versions = versions

    # -- carregamento do banco --------------------------------------------
    @classmethod
    def from_db(
        cls, db: Session, jurisdiction: Optional[str] = None
    ) -> "RegulatoryCatalog":
        from app.models.domain import RegulatoryRule

        query = db.query(RegulatoryRule).filter(
            RegulatoryRule.superseded_by_id.is_(None)
        )
        if jurisdiction:
            query = query.filter(
                RegulatoryRule.jurisdiction.in_(jurisdiction_chain(jurisdiction))
            )

        rows = query.all()
        rules = [Rule.from_orm(row) for row in rows]
        versions: Dict[str, str] = {}
        for row in rows:
            versions.setdefault(row.jurisdiction, row.catalog_version)
        return cls(rules, versions)

    # -- carregamento dos arquivos de semente ------------------------------
    @classmethod
    def load_seed_files(cls, data_dir: str = DATA_DIR) -> List[Dict[str, Any]]:
        """Lê os YAML de semente. Não toca no banco."""
        catalogs: List[Dict[str, Any]] = []

        # Security: Prevent directory traversal by ensuring data_dir is within DATA_DIR
        abs_data_dir = os.path.abspath(data_dir)
        abs_base_dir = os.path.abspath(DATA_DIR)

        if os.path.commonpath([abs_base_dir, abs_data_dir]) != abs_base_dir:
            raise ValueError("data_dir must be within the designated data directory")

        if not os.path.isdir(data_dir):
            return catalogs

        for filename in sorted(os.listdir(data_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            with open(
                os.path.join(data_dir, filename), "r", encoding="utf-8"
            ) as handle:
                payload = yaml.safe_load(handle) or {}

            jurisdiction = (payload.get("jurisdiction") or {}).get("code")
            if not jurisdiction:
                raise ValueError(f"{filename}: catálogo sem `jurisdiction.code`")

            for raw in payload.get("rules") or []:
                _validate_seed_rule(raw, filename)

            catalogs.append(
                {
                    "filename": filename,
                    "jurisdiction": jurisdiction,
                    "catalog_version": payload.get("catalog_version", "0.1.0"),
                    "rules": payload.get("rules") or [],
                }
            )
        return catalogs

    # -- consulta ----------------------------------------------------------
    @property
    def all_rules(self) -> List[Rule]:
        return list(self._rules)

    def get(self, rule_id: str) -> Optional[Rule]:
        return next((r for r in self._rules if r.rule_id == rule_id), None)

    def for_jurisdiction(self, jurisdiction: str) -> List[Rule]:
        scopes = jurisdiction_chain(jurisdiction)
        return [r for r in self._rules if r.jurisdiction in scopes]

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
        versions = [
            f"{scope}:{self.versions[scope]}"
            for scope in jurisdiction_chain(jurisdiction)
            if scope in self.versions
        ]
        return "|".join(versions) or "desconhecida"


def _validate_seed_rule(raw: Dict[str, Any], filename: str) -> None:
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
        if check["operator"] not in _OPERATORS:
            raise ValueError(
                f"{filename}/{rule_id}: operador '{check['operator']}' não suportado"
            )
