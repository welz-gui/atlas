"""Importação do catálogo de semente (YAML) para o banco.

Idempotente por `(jurisdiction, rule_key)`. Regras já promovidas a `vigente`
por um validador **não são sobrescritas**: quem publicou assume a
responsabilidade técnica, e uma reimportação de arquivo não pode desfazer isso
silenciosamente.
"""

from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from app.models.domain import RegulatoryRule
from app.regulatory.catalog import RegulatoryCatalog, RuleState


def import_seed_catalog(
    db: Session, overwrite_validated: bool = False
) -> Dict[str, int]:
    """Sincroniza os YAML de semente com a tabela `regulatory_rules`."""
    summary = {"created": 0, "updated": 0, "skipped_validated": 0}

    catalogs = list(RegulatoryCatalog.load_seed_files())
    if not catalogs:
        return summary

    jurisdiction_rule_keys = {}
    for catalog in catalogs:
        jurisdiction = catalog["jurisdiction"]
        rule_keys = [raw["rule_id"] for raw in catalog["rules"]]
        jurisdiction_rule_keys.setdefault(jurisdiction, []).extend(rule_keys)

    existing_rules_map = {}
    for jurisdiction, keys in jurisdiction_rule_keys.items():
        if not keys:
            continue

        chunk_size = 500
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i:i + chunk_size]
            existing_rules_query = (
                db.query(RegulatoryRule)
                .filter(
                    RegulatoryRule.jurisdiction == jurisdiction,
                    RegulatoryRule.rule_key.in_(chunk)
                )
                .all()
            )
            for r in existing_rules_query:
                existing_rules_map.setdefault(r.jurisdiction, {})[r.rule_key] = r

    new_rules_to_add = []

    for catalog in catalogs:
        jurisdiction = catalog["jurisdiction"]
        catalog_version = catalog["catalog_version"]

        existing_rules = existing_rules_map.setdefault(jurisdiction, {})

        for raw in catalog["rules"]:
            rule_key = raw["rule_id"]
            existing = existing_rules.get(rule_key)

            if (
                existing
                and existing.state == RuleState.VIGENTE
                and not overwrite_validated
            ):
                summary["skipped_validated"] += 1
                continue

            source = raw.get("source") or {}
            values = dict(
                jurisdiction=jurisdiction,
                rule_key=rule_key,
                title=raw.get("title", rule_key),
                state=raw["state"],
                severity=raw.get("severity", "bloqueio"),
                applies_to=raw.get("applies_to") or {},
                check=raw.get("check"),
                requires_manual_review=bool(raw.get("requires_manual_review", False)),
                manual_review_reason=raw.get("manual_review_reason"),
                evidence_required=raw.get("evidence_required") or [],
                source_document_label=source.get("document"),
                source_article=source.get("article"),
                effective_from=_as_text(raw.get("effective_from")),
                effective_until=_as_text(raw.get("effective_until")),
                notes=raw.get("notes"),
                catalog_version=catalog_version,
            )

            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                summary["updated"] += 1
            else:
                new_rule = RegulatoryRule(**values)
                existing_rules[rule_key] = new_rule
                new_rules_to_add.append(new_rule)
                summary["created"] += 1

    if new_rules_to_add:
        db.add_all(new_rules_to_add)

    db.commit()
    return summary


def _as_text(value) -> str | None:
    return None if value is None else str(value)
