"""Métricas do §11 (D5).

O que estes testes protegem, acima de tudo: **ausência de base amostral devolve
`null`, nunca zero**. Uma organização que nunca protocolou nada não tem "zero
falsos negativos críticos" — ela não tem a informação, e o portão não pode ser
atravessado por isso.
"""


from tests.conftest import auth_headers, make_org, make_user
from app.models.domain import UserRole


def _metrics(client, headers):
    response = client.get("/api/v1/metrics", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- Permissão ---------------------------------------------------------------


def test_engenheiro_nao_le_metricas(client, engineer_headers):
    """Métrica de acerto é instrumento de decisão, não painel de obra."""
    response = client.get("/api/v1/metrics", headers=engineer_headers)
    assert response.status_code == 403


def test_validador_le_metricas(client, validator_headers):
    assert client.get("/api/v1/metrics", headers=validator_headers).status_code == 200


def test_sem_autenticacao_e_recusado(client):
    assert client.get("/api/v1/metrics").status_code == 401


# --- A regra que governa o módulo -------------------------------------------


def test_organizacao_vazia_devolve_null_e_nao_zero(client, validator_headers):
    body = _metrics(client, validator_headers)
    aprovacao = body["approval"]

    # Contagens de coisas que existem podem ser zero — são fatos.
    assert aprovacao["projects"] == 0
    assert aprovacao["protocols"] == 0

    # Já derivadas sem base amostral não podem afirmar nada.
    assert aprovacao["critical_false_negatives"] is None
    assert aprovacao["blocking_recall_percent"] is None
    assert aprovacao["precision_percent"] is None
    assert aprovacao["days_to_permit_avg"] is None
    assert aprovacao["unverifiable_percent"] is None
    assert aprovacao["notification_cycles_total"] is None


def test_portao_nao_e_atravessado_por_falta_de_dado(client, validator_headers):
    """O caso que motivou o D5: sem medição, o veredicto é `null`, não `true`."""
    portao = _metrics(client, validator_headers)["gate_0_to_1"]

    assert portao["overall"] is None
    assert any(c["met"] is None for c in portao["criteria"])

    # E nenhum critério não medido pode aparecer como atingido.
    for criterio in portao["criteria"]:
        if criterio["measured"] is None:
            assert criterio["met"] is None


def test_portao_reprova_quando_ha_dado_e_ele_nao_alcanca(
    client, validator_headers, project, db_session
):
    """Com projeto analisado, os critérios mensuráveis passam a ter veredicto."""
    portao = _metrics(client, validator_headers)["gate_0_to_1"]
    por_nome = {c["name"]: c for c in portao["criteria"]}

    # Um projeto só: o critério é mensurável e reprova.
    assert por_nome["projetos_concluidos"]["measured"] == 1
    assert por_nome["projetos_concluidos"]["met"] is False

    # O catálogo semente não tem regra publicada — mensurável, e reprova.
    assert por_nome["regras_publicadas"]["measured"] == 0
    assert por_nome["regras_publicadas"]["met"] is False

    # Recall continua sem base: nenhuma exigência foi registrada.
    assert por_nome["recall_de_bloqueios"]["measured"] is None
    assert portao["overall"] is None


# --- Cobertura do catálogo ---------------------------------------------------


def test_cobertura_reflete_o_catalogo_nao_conferido(
    client, validator_headers, project
):
    """Enquanto o D3 não acontecer, a cobertura é 0% — e isso é um fato, não
    ausência: as regras existem e nenhuma está publicável."""
    aprovacao = _metrics(client, validator_headers)["approval"]

    assert aprovacao["catalog_rules"] == 7
    assert aprovacao["catalog_publishable_rules"] == 0
    assert aprovacao["catalog_coverage_percent"] == 0.0


# --- Recall e falsos negativos ----------------------------------------------


def _protocolar(client, headers, project_id, numero="2026/PMU-001"):
    response = client.post(
        f"/api/v1/projects/{project_id}/protocols",
        headers=headers,
        json={"protocol_number": numero, "agency": "Prefeitura de Lajeado"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _projeto_com_recuo_insuficiente(client, headers):
    """Recuo frontal 3,5 m contra o mínimo de 4,0 m: o motor aponta.

    A taxa de ocupação fica conforme (240/450 ≈ 53%, limite 60%), de modo que
    uma exigência sobre ela é falso negativo — que é o caso que o Portão 0 → 1
    de fato mede.
    """
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Residencial com Recuo Insuficiente",
            "zone": "Z2",
            "building_type": "residencial_unifamiliar",
            "lot_area": 450.0,
            "built_area": 240.0,
            "floors": 2,
            "front_setback": 3.5,
            "rear_setback": 3.5,
            "permeability_rate": 22.0,
            "parking_spaces": 2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_recall_e_falsos_negativos_saem_das_exigencias_vinculadas(
    client, engineer_headers, validator_headers, seeded_catalog
):
    projeto = _projeto_com_recuo_insuficiente(client, engineer_headers)
    client.post(f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers)
    processo = _protocolar(client, engineer_headers, projeto["id"])

    # Uma exigência sobre regra que o motor apontou; outra sobre regra que ele
    # deu como conforme. `was_predicted` não é enviado — é derivado.
    for descricao, regra in [
        ("Recuo frontal insuficiente", "lajeado_recuo_frontal_z2"),
        ("Taxa de ocupação questionada pelo órgão", "lajeado_taxa_ocupacao_max_z2"),
    ]:
        response = client.post(
            f"/api/v1/protocols/{processo['id']}/requirements",
            headers=engineer_headers,
            json={"description": descricao, "linked_rule_key": regra},
        )
        assert response.status_code == 201, response.text

    aprovacao = _metrics(client, validator_headers)["approval"]

    assert aprovacao["requirements_linked_to_rules"] == 2
    assert aprovacao["blocking_recall_percent"] == 50.0
    assert aprovacao["critical_false_negatives"] == 1


def test_recall_ignora_was_predicted_enviado_pelo_cliente(
    client, engineer_headers, validator_headers, seeded_catalog
):
    """O sistema não aceita afirmação do cliente sobre a própria acurácia.

    `was_predicted` é derivado da análise mais recente
    (`endpoints/protocol.py`). Cliente que jura ter sido previsto não muda o
    recall — do contrário a métrica mediria a boa vontade de quem preenche.
    """
    projeto = _projeto_com_recuo_insuficiente(client, engineer_headers)
    client.post(f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers)
    processo = _protocolar(client, engineer_headers, projeto["id"])

    response = client.post(
        f"/api/v1/protocols/{processo['id']}/requirements",
        headers=engineer_headers,
        json={
            "description": "Taxa de ocupação questionada pelo órgão",
            "linked_rule_key": "lajeado_taxa_ocupacao_max_z2",
            "was_predicted": True,  # mentira: o motor deu conforme
        },
    )
    assert response.status_code == 201, response.text

    aprovacao = _metrics(client, validator_headers)["approval"]

    assert aprovacao["blocking_recall_percent"] == 0.0
    assert aprovacao["critical_false_negatives"] == 1


def test_exigencia_sem_regra_nao_conta_como_falso_negativo(
    client, engineer_headers, validator_headers, project
):
    """Exigência documental que nenhuma regra poderia prever não é falha do
    motor — entra no total, fica fora do recall."""
    processo = _protocolar(client, engineer_headers, project["id"])
    response = client.post(
        f"/api/v1/protocols/{processo['id']}/requirements",
        headers=engineer_headers,
        json={"description": "Apresentar laudo de sondagem de solo"},
    )
    assert response.status_code == 201, response.text

    aprovacao = _metrics(client, validator_headers)["approval"]

    assert aprovacao["requirements_total"] == 1
    assert aprovacao["requirements_linked_to_rules"] == 0
    assert aprovacao["blocking_recall_percent"] is None
    assert aprovacao["critical_false_negatives"] is None


# --- Isolamento --------------------------------------------------------------


def test_metricas_nao_atravessam_organizacoes(
    client, db_session, validator_headers, project, engineer_headers
):
    """A métrica de uma organização não enxerga o trabalho de outra (I12)."""
    outra_org = make_org(db_session, name="Outra Construtora")
    outro_validador = make_user(
        db_session, outra_org, UserRole.VALIDATOR, email="val@outra.com"
    )
    outros_headers = auth_headers(client, outro_validador.email)

    minhas = _metrics(client, validator_headers)["approval"]
    dela = _metrics(client, outros_headers)["approval"]

    assert minhas["projects"] == 1
    assert dela["projects"] == 0
    # Sem projeto, não há jurisdição — logo não há catálogo a cobrir.
    assert dela["catalog_coverage_percent"] is None


# --- IA ----------------------------------------------------------------------


def test_metricas_de_ia_sem_interacao(client, validator_headers):
    ia = _metrics(client, validator_headers)["ai"]

    assert ia["interactions"] == 0
    assert ia["grounded_percent"] is None
    assert ia["input_tokens"] is None
    assert ia["draft_acceptance_percent"] is None


def test_custo_e_reportado_em_tokens_e_nunca_em_dinheiro(client, validator_headers):
    """Converter token em dinheiro exigiria tabela de preços que não existe.
    Preço estimado é suposição com cara de medição."""
    ia = _metrics(client, validator_headers)["ai"]

    assert "input_tokens" in ia and "output_tokens" in ia
    assert not any("cost" in chave or "custo" in chave for chave in ia)
