"""Assistente: consulta ao catálogo, sem inventar base legal."""

from app.models.domain import RegulatoryRule
from app.regulatory.catalog import RegulatoryCatalog


def _ask(client, headers, prompt, project_id=None):
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"prompt": prompt, "project_id": project_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_responde_consulta_sobre_parametros(client, engineer_headers, project):
    body = _ask(
        client,
        engineer_headers,
        "Quais são as regras de recuo frontal e taxa de ocupação em Lajeado?",
        project["id"],
    )

    assert "Lajeado" in body["answer"]
    assert len(body["law_citations"]) >= 2
    assert len(body["suggested_actions"]) >= 1
    assert "lajeado_recuo_frontal_z2" in body["matched_rules"]
    assert "lajeado_taxa_ocupacao_max_z2" in body["matched_rules"]


def test_resposta_sempre_traz_ressalva(client, engineer_headers, seeded_catalog):
    body = _ask(client, engineer_headers, "recuo frontal")

    assert "não substitui o responsável técnico" in body["disclaimer"]
    assert body["is_ai_generated"] is False


def test_nao_afirma_numero_de_artigo_nao_conferido(
    client, engineer_headers, db_session, seeded_catalog
):
    """Regressão: o protótipo citava 'Art. 42', 'Art. 35' etc. sem fonte."""
    catalog = RegulatoryCatalog.from_db(db_session, "BR-RS-4311403")

    for prompt in ("recuo frontal", "taxa de ocupação", "permeabilidade", "vagas"):
        body = _ask(client, engineer_headers, prompt)
        for citation in body["law_citations"]:
            if "Art." in citation:
                rule = catalog.get(body["matched_rules"][0])
                assert rule and rule.source.is_verified, citation


def test_citacao_vem_do_catalogo(client, engineer_headers, db_session, seeded_catalog):
    """Motor e assistente têm de citar a mesma fonte para a mesma regra."""
    body = _ask(client, engineer_headers, "permeabilidade")
    rule = RegulatoryCatalog.from_db(db_session, "BR-RS-4311403").get(
        "lajeado_taxa_permeabilidade_min_z2"
    )

    assert rule is not None
    assert any(rule.source.citation() in c for c in body["law_citations"])


def test_avisa_quando_a_regra_nao_foi_validada(client, engineer_headers, seeded_catalog):
    body = _ask(client, engineer_headers, "recuo frontal")
    assert "em validação" in body["answer"]


def test_consulta_sem_correspondencia_nao_inventa_resposta(
    client, engineer_headers, seeded_catalog
):
    body = _ask(client, engineer_headers, "qual o custo do metro quadrado de alvenaria?")

    assert "Não encontrei" in body["answer"]
    assert body["matched_rules"] == []


def test_projeto_de_outro_tenant_nao_entra_no_contexto(
    client, db_session, project, seeded_catalog
):
    """Um id de projeto alheio não pode vazar dados pela resposta do assistente."""
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user

    outra_org = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra_org, UserRole.OWNER, "intruso-ai@atlas-qa.com")

    body = _ask(
        client, auth_headers(client, intruso.email), "recuo frontal", project["id"]
    )
    assert project["name"] not in body["answer"]


def test_citacao_muda_quando_a_regra_e_validada(
    client, engineer_headers, validator_headers, db_session, seeded_catalog
):
    documento = client.post(
        "/api/v1/catalog/documents",
        headers=validator_headers,
        json={
            "jurisdiction": "BR-RS-4311403",
            "title": "Plano Diretor de Lajeado",
            "doc_type": "plano_diretor",
        },
    ).json()
    rule = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.rule_key == "lajeado_recuo_frontal_z2")
        .one()
    )

    antes = _ask(client, engineer_headers, "recuo frontal")
    assert any("não verificado" in c for c in antes["law_citations"])

    client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=validator_headers,
        json={
            "action": "publicar",
            "source_document_id": documento["id"],
            "source_article": "Art. 45",
        },
    )

    depois = _ask(client, engineer_headers, "recuo frontal")
    assert any("Art. 45" in c for c in depois["law_citations"])
