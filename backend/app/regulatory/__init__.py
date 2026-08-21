"""Subsistema de Operação Regulatória (Plano de Implementação §7).

Nível 1 — manual assistido: as regras vivem como dado versionado (YAML), com
estado, vigência, severidade e proveniência, e não como código.
"""

from app.regulatory.catalog import (
    Rule,
    RuleState,
    Severity,
    CheckOutcome,
    EXECUTABLE_STATES,
    PUBLISHABLE_STATES,
)

__all__ = [
    "Rule",
    "RuleState",
    "Severity",
    "CheckOutcome",
    "EXECUTABLE_STATES",
    "PUBLISHABLE_STATES",
]
