"""Hierarquia territorial usada pelo catálogo regulatório."""

from __future__ import annotations


def jurisdiction_chain(jurisdiction: str) -> tuple[str, ...]:
    """Devolve os escopos aplicáveis, do nacional ao mais específico."""
    parts = jurisdiction.strip().upper().split("-")
    if not parts or parts[0] != "BR":
        return (jurisdiction,)
    if len(parts) == 1:
        return ("BR",)
    if len(parts) == 2:
        return ("BR", "-".join(parts[:2]))
    return ("BR", "-".join(parts[:2]), "-".join(parts[:3]))


def applicable_jurisdictions(jurisdictions: set[str]) -> set[str]:
    """Expande vários municípios para os escopos que incidem sobre eles."""
    return {
        scope
        for jurisdiction in jurisdictions
        for scope in jurisdiction_chain(jurisdiction)
    }
