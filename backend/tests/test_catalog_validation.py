"""Catálogo em banco e validação técnica de regras (§7.4, §7.5, §15.12)."""

import pytest

from app.models.domain import RegulatoryRule
from app.regulatory.catalog import ALLOWED_TRANSITIONS, RegulatoryCatalog, RuleState


@pytest.fixture
def rule(seeded_catalog):
    return (
        seeded_catalog.query(RegulatoryRule)
        .filter(RegulatoryRule.rule_key == "lajeado_recuo_frontal_z2")
        .one()
    )


@pytest.fixture
def source_document(client, validator_headers):
    response = client.post(
        "/api/v1/catalog/documents",
        headers=validator_headers,
        json={
            "jurisdiction": "BR-RS-4311403",
            "doc_type": "plano_diretor",
            "title": "Plano Diretor de Lajeado",
            "issuing_body": "Prefeitura Municipal de Lajeado",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Importação --------------------------------------------------------------

def test_importacao_traz_as_regras_de_semente(seeded_catalog):
    rules = seeded_catalog.query(RegulatoryRule).all()
    assert len(rules) == 7
    assert all(r.state == RuleState.EM_VALIDACAO for r in rules)
    assert all(r.validated_by_id is None for r in rules)
    assert seeded_catalog.query(RegulatoryRule).filter_by(
        rule_key="brasil_acessibilidade_edificacoes", jurisdiction="BR"
    ).one()


def test_importacao_e_idempotente(db_session):
    from app.regulatory.importer import import_seed_catalog

    first = import_seed_catalog(db_session)
    second = import_seed_catalog(db_session)

    assert first["created"] == 7
    assert second["created"] == 0
    assert second["updated"] == 7
    assert db_session.query(RegulatoryRule).count() == 7


def test_importacao_nao_sobrescreve_regra_publicada(db_session, seeded_catalog):
    from app.regulatory.importer import import_seed_catalog

    rule = seeded_catalog.query(RegulatoryRule).first()
    rule.state = RuleState.VIGENTE
    rule.validated_by_name = "Eng. Responsável"
    db_session.commit()

    summary = import_seed_catalog(db_session)

    assert summary["skipped_validated"] == 1
    db_session.refresh(rule)
    assert rule.state == RuleState.VIGENTE


# --- Fila de validação -------------------------------------------------------

def test_fila_lista_regras_pendentes(client, validator_headers, seeded_catalog):
    queue = client.get("/api/v1/catalog/validation-queue", headers=validator_headers).json()
    assert len(queue) == 7
    assert all(item["is_publishable"] is False for item in queue)
    assert all(item["is_executable"] is True for item in queue)


def test_publicar_exige_documento_de_origem(client, validator_headers, rule):
    response = client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "publicar", "source_article": "Art. 45"},
    )
    assert response.status_code == 422
    assert "source_document_id" in response.json()["detail"]


def test_publicar_exige_artigo_conferido(client, validator_headers, rule, source_document):
    """§7.5 — sem artigo conferido a fonte não é verificada, logo a regra não é vigente."""
    response = client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "publicar", "source_document_id": source_document["id"]},
    )
    assert response.status_code == 422
    assert "artigo" in response.json()["detail"].lower()


def test_publicar_registra_validador_e_torna_publicavel(
    client, validator_headers, validator, rule, source_document
):
    response = client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={
            "action": "publicar",
            "source_document_id": source_document["id"],
            "source_article": "Art. 45",
            "notes": "Conferido contra o texto publicado.",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["state"] == RuleState.VIGENTE
    assert body["validated_by_name"] == validator.name
    assert body["validated_at"] is not None
    assert body["source_article"] == "Art. 45"
    assert body["is_publishable"] is True


def test_transicao_invalida_e_recusada(client, validator_headers, rule):
    """De `em_validacao` não se vai direto para `suspensa`."""
    response = client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "suspender"},
    )
    assert response.status_code == 409
    assert "Transição não permitida" in response.json()["detail"]


def test_suspender_retira_a_validacao(
    client, validator_headers, rule, source_document
):
    client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={
            "action": "publicar",
            "source_document_id": source_document["id"],
            "source_article": "Art. 45",
        },
    )
    response = client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "suspender", "notes": "Lei alterada; aguardando conferência."},
    )

    assert response.status_code == 200
    assert response.json()["state"] == RuleState.SUSPENSA
    assert response.json()["validated_by_name"] is None
    assert response.json()["is_publishable"] is False


def test_regra_suspensa_sai_do_motor(client, engineer_headers, validator_headers, project, rule):
    """Estado não executável remove a regra da análise (§7.4)."""
    antes = client.post(
        f"/api/v1/projects/{project['id']}/evaluate", headers=engineer_headers
    ).json()
    assert any(r["rule_id"] == "lajeado_recuo_frontal_z2" for r in antes["results"])

    client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "rejeitar", "notes": "Parâmetro não confere com a lei."},
    )
    client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "revogar"},
    )

    depois = client.post(
        f"/api/v1/projects/{project['id']}/evaluate", headers=engineer_headers
    ).json()
    assert not any(r["rule_id"] == "lajeado_recuo_frontal_z2" for r in depois["results"])


def test_eventos_de_validacao_sao_registrados(client, validator_headers, validator, rule):
    client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={"action": "rejeitar", "notes": "Falta conferir a lei."},
    )
    events = client.get(
        f"/api/v1/catalog/rules/{rule.id}/events", headers=validator_headers
    ).json()

    assert len(events) == 1
    assert events[0]["action"] == "rejeitar"
    assert events[0]["from_state"] == RuleState.EM_VALIDACAO
    assert events[0]["actor_name"] == validator.name


def test_analise_so_e_publicavel_com_todas_as_regras_validadas(
    client, engineer_headers, validator_headers, project, seeded_catalog, source_document
):
    """§7.5 — uma única regra pendente já impede a entrega do laudo."""
    report = client.post(
        f"/api/v1/projects/{project['id']}/evaluate", headers=engineer_headers
    ).json()
    assert report["is_publishable"] is False

    for row in seeded_catalog.query(RegulatoryRule).all():
        client.post(
            f"/api/v1/catalog/rules/{row.id}/validate",
            headers=validator_headers,
            json={
                "action": "publicar",
                "source_document_id": source_document["id"],
                "source_article": "Art. conferido",
            },
        )

    report = client.post(
        f"/api/v1/projects/{project['id']}/evaluate", headers=engineer_headers
    ).json()
    assert report["is_publishable"] is True
    assert all(r["source_is_verified"] for r in report["results"])

    pdf = client.get(
        f"/api/v1/projects/{project['id']}/report/pdf", headers=engineer_headers
    )
    assert pdf.headers["X-Atlas-Publishable"] == "true"
    assert "USO_INTERNO_" not in pdf.headers["content-disposition"]


def test_catalogo_do_banco_alimenta_o_motor(db_session, seeded_catalog):
    catalog = RegulatoryCatalog.from_db(db_session, "BR-RS-4311403")
    assert len(catalog.all_rules) == 7
    assert len(catalog.executable_for("BR-RS-4311403")) == 7
    assert {rule.rule_id for rule in catalog.for_jurisdiction("BR-SP-3550308")} == {
        "brasil_acessibilidade_edificacoes"
    }


def test_catalogo_municipal_inclui_regra_nacional_e_exclui_outro_municipio(db_session, seeded_catalog):
    arroio = RegulatoryCatalog.from_db(db_session, "BR-RS-4301008")
    assert {rule.rule_id for rule in arroio.for_jurisdiction("BR-RS-4301008")} == {
        "brasil_acessibilidade_edificacoes"
    }


def test_transicoes_terminais_nao_tem_saida():
    assert ALLOWED_TRANSITIONS[RuleState.REVOGADA] == set()
    assert ALLOWED_TRANSITIONS[RuleState.SUBSTITUIDA] == set()
