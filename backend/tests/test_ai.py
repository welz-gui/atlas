"""Assistente: consulta ao catálogo, sem inventar base legal."""

from app.api.v1.endpoints.ai import AIChatRequest, atlas_ai_chat
from app.models.domain import Organization, Project
from app.regulatory.catalog import catalog


def _project(db_session):
    org = Organization(name="Org do Assistente")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Residencial Teste AI",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=400.0,
        built_area=240.0,
    )
    db_session.add(project)
    db_session.commit()
    return project


def test_responde_consulta_sobre_parametros(db_session):
    project = _project(db_session)
    req = AIChatRequest(
        prompt="Quais são as regras de recuo frontal e taxa de ocupação em Lajeado?",
        project_id=project.id,
    )

    response = atlas_ai_chat(req, db_session)

    assert "Lajeado" in response.answer
    assert len(response.law_citations) >= 2
    assert len(response.suggested_actions) >= 1
    assert "lajeado_recuo_frontal_z2" in response.matched_rules
    assert "lajeado_taxa_ocupacao_max_z2" in response.matched_rules


def test_resposta_sempre_traz_ressalva(db_session):
    response = atlas_ai_chat(AIChatRequest(prompt="recuo frontal"), db_session)

    assert response.disclaimer
    assert "não substitui o responsável técnico" in response.disclaimer
    assert response.is_ai_generated is False


def test_nao_afirma_numero_de_artigo_nao_conferido(db_session):
    """Regressão: o protótipo citava 'Art. 42', 'Art. 35' etc. sem fonte."""
    prompts = [
        "recuo frontal", "taxa de ocupação", "permeabilidade",
        "vagas de garagem", "acessibilidade", "gabarito",
    ]
    for prompt in prompts:
        response = atlas_ai_chat(AIChatRequest(prompt=prompt), db_session)
        for citation in response.law_citations:
            if "Art." in citation:
                rule_id = response.matched_rules[0]
                rule = catalog.get(rule_id)
                assert rule and rule.source.is_verified, (
                    f"citação com artigo para regra não conferida: {citation}"
                )


def test_citacao_vem_do_catalogo_e_nao_de_dicionario_proprio(db_session):
    """Motor e assistente têm de citar a mesma fonte para a mesma regra."""
    response = atlas_ai_chat(AIChatRequest(prompt="permeabilidade"), db_session)
    rule = catalog.get("lajeado_taxa_permeabilidade_min_z2")

    assert rule is not None
    assert any(rule.source.citation() in citation for citation in response.law_citations)


def test_avisa_quando_a_regra_nao_foi_validada(db_session):
    response = atlas_ai_chat(AIChatRequest(prompt="recuo frontal"), db_session)
    assert "em validação" in response.answer


def test_consulta_sem_correspondencia_nao_inventa_resposta(db_session):
    response = atlas_ai_chat(
        AIChatRequest(prompt="qual o custo do metro quadrado de alvenaria?"), db_session
    )

    assert "Não encontrei" in response.answer
    assert response.matched_rules == []
