"""Tramitação municipal e recall de bloqueios (§8.5, §11)."""

import pytest

from app.models.domain import ProtocolStatus, RequirementStatus


@pytest.fixture
def project_com_bloqueio(client, engineer_headers, seeded_catalog):
    """Projeto com recuo frontal insuficiente — o motor aponta não conformidade."""
    response = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={
            "name": "Residencial Sol Nascente",
            "zone": "Z2",
            "building_type": "residencial_unifamiliar",
            "lot_area": 360.0,
            "built_area": 220.0,
            "floors": 2,
            "front_setback": 3.2,
            "rear_setback": 3.5,
            "permeability_rate": 22.0,
            "parking_spaces": 1,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def process(client, engineer_headers, project_com_bloqueio):
    response = client.post(
        f"/api/v1/projects/{project_com_bloqueio['id']}/protocols",
        headers=engineer_headers,
        json={
            "protocol_number": "2026/PMU-004821",
            "agency": "Secretaria de Planejamento — Lajeado/RS",
            "submitted_at": "2026-07-15",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_protocolo_registra_evento_e_situacao(client, engineer_headers, process):
    assert process["status"] == ProtocolStatus.PROTOCOLADO
    assert process["protocol_number"] == "2026/PMU-004821"
    assert process["project_version_id"] is not None

    detalhe = client.get(
        f"/api/v1/protocols/{process['id']}", headers=engineer_headers
    ).json()
    assert len(detalhe["events"]) == 1
    assert detalhe["events"][0]["event_type"] == "protocolo_registrado"


def test_protocolo_atualiza_o_licenciamento_do_projeto(
    client, engineer_headers, project_com_bloqueio, process
):
    projeto = client.get(
        f"/api/v1/projects/{project_com_bloqueio['id']}", headers=engineer_headers
    ).json()
    assert projeto["licensing_status"] == ProtocolStatus.PROTOCOLADO


def test_exigencia_prevista_pelo_motor_e_marcada(client, engineer_headers, process):
    """O item já apontado como não conforme conta como antecipado (§11)."""
    response = client.post(
        f"/api/v1/protocols/{process['id']}/requirements",
        headers=engineer_headers,
        json={
            "description": "Ajustar o recuo frontal ao mínimo da zona.",
            "linked_rule_key": "lajeado_recuo_frontal_z2",
            "raised_at": "2026-07-30",
            "due_date": "2026-08-30",
        },
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["was_predicted"] is True
    assert body["status"] == RequirementStatus.ABERTA
    assert body["sequence"] == 1


def test_exigencia_nao_prevista_e_marcada_como_falso_negativo(
    client, engineer_headers, process
):
    """Regra que estava conforme e mesmo assim gerou exigência: falso negativo."""
    response = client.post(
        f"/api/v1/protocols/{process['id']}/requirements",
        headers=engineer_headers,
        json={
            "description": "Recuo dos fundos insuficiente segundo o analista.",
            "linked_rule_key": "lajeado_recuo_fundos_z2",
        },
    )
    assert response.json()["was_predicted"] is False


def test_exigencia_sem_vinculo_nao_entra_na_metrica(client, engineer_headers, process):
    response = client.post(
        f"/api/v1/protocols/{process['id']}/requirements",
        headers=engineer_headers,
        json={"description": "Apresentar ART assinada."},
    )
    assert response.json()["was_predicted"] is None


def test_exigencia_muda_a_situacao_para_notificado(client, engineer_headers, process):
    client.post(
        f"/api/v1/protocols/{process['id']}/requirements",
        headers=engineer_headers,
        json={"description": "Corrigir o recuo frontal."},
    )
    detalhe = client.get(
        f"/api/v1/protocols/{process['id']}", headers=engineer_headers
    ).json()

    assert detalhe["status"] == ProtocolStatus.NOTIFICADO
    assert detalhe["open_requirements_count"] == 1


def test_responder_exigencia(client, engineer_headers, process):
    requirement = client.post(
        f"/api/v1/protocols/{process['id']}/requirements",
        headers=engineer_headers,
        json={"description": "Corrigir o recuo frontal."},
    ).json()

    response = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        headers=engineer_headers,
        json={
            "status": RequirementStatus.ATENDIDA,
            "response_text": "Recuo ajustado para 4,20 m na revisão 2.",
            "responded_at": "2026-08-05",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == RequirementStatus.ATENDIDA

    detalhe = client.get(
        f"/api/v1/protocols/{process['id']}", headers=engineer_headers
    ).json()
    assert detalhe["open_requirements_count"] == 0


def test_historico_do_processo_e_append_only(client, engineer_headers, process):
    client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=engineer_headers,
        json={"status": ProtocolStatus.EM_ANALISE, "description": "Distribuído ao analista."},
    )
    client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=engineer_headers,
        json={"status": ProtocolStatus.APROVADO, "decided_at": "2026-09-01"},
    )

    detalhe = client.get(
        f"/api/v1/protocols/{process['id']}", headers=engineer_headers
    ).json()
    assert detalhe["status"] == ProtocolStatus.APROVADO
    assert detalhe["decided_at"] == "2026-09-01"
    assert len(detalhe["events"]) == 3
    assert [e["to_status"] for e in detalhe["events"]] == [
        ProtocolStatus.PROTOCOLADO, ProtocolStatus.EM_ANALISE, ProtocolStatus.APROVADO
    ]


def test_processo_encerrado_nao_admite_nova_transicao(client, engineer_headers, process):
    client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=engineer_headers,
        json={"status": ProtocolStatus.APROVADO},
    )
    response = client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=engineer_headers,
        json={"status": ProtocolStatus.EM_ANALISE},
    )
    assert response.status_code == 409


def test_situacao_invalida_e_recusada(client, engineer_headers, process):
    response = client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=engineer_headers,
        json={"status": "inventado"},
    )
    assert response.status_code == 422


def test_recall_de_bloqueios(client, engineer_headers, project_com_bloqueio, process):
    """§11 — o que o Atlas antecipou sobre o total de exigências vinculadas."""
    for payload in (
        {"description": "Recuo frontal.", "linked_rule_key": "lajeado_recuo_frontal_z2"},
        {"description": "Recuo fundos.", "linked_rule_key": "lajeado_recuo_fundos_z2"},
        {"description": "ART assinada."},
    ):
        client.post(
            f"/api/v1/protocols/{process['id']}/requirements",
            headers=engineer_headers,
            json=payload,
        )

    metrics = client.get(
        f"/api/v1/projects/{project_com_bloqueio['id']}/prediction-accuracy",
        headers=engineer_headers,
    ).json()

    assert metrics["total_requirements"] == 3
    assert metrics["linked_to_rules"] == 2
    assert metrics["predicted"] == 1
    assert metrics["not_predicted"] == 1
    assert metrics["recall_percent"] == 50.0


def test_recall_sem_exigencias_nao_inventa_numero(
    client, engineer_headers, project_com_bloqueio
):
    metrics = client.get(
        f"/api/v1/projects/{project_com_bloqueio['id']}/prediction-accuracy",
        headers=engineer_headers,
    ).json()

    assert metrics["total_requirements"] == 0
    assert metrics["recall_percent"] is None


def test_protocolo_de_outro_tenant_responde_404(client, db_session, process):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user

    outra_org = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra_org, UserRole.OWNER, "intruso-proto@atlas-qa.com")
    headers = auth_headers(client, intruso.email)

    assert client.get(f"/api/v1/protocols/{process['id']}", headers=headers).status_code == 404
    assert client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=headers,
        json={"status": ProtocolStatus.APROVADO},
    ).status_code == 404


# =============================================================================
# Bordas dos endpoints de protocolo
# =============================================================================
def _exigencia(client, headers, process_id, **extras):
    response = client.post(
        f"/api/v1/protocols/{process_id}/requirements",
        headers=headers,
        json={"description": "Corrigir o recuo frontal.", **extras},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_lista_de_protocolos_vem_do_mais_novo_para_o_mais_antigo(
    client, engineer_headers, project_com_bloqueio, process
):
    segundo = client.post(
        f"/api/v1/projects/{project_com_bloqueio['id']}/protocols",
        headers=engineer_headers,
        json={"protocol_number": "2026/PMU-004822", "agency": "Secretaria", "submitted_at": "2026-07-16"},
    ).json()

    lista = client.get(
        f"/api/v1/projects/{project_com_bloqueio['id']}/protocols", headers=engineer_headers
    ).json()

    assert [p["id"] for p in lista] == [segundo["id"], process["id"]]


def test_recursos_inexistentes_respondem_404(client, engineer_headers):
    """Projeto, processo, exigência: id que não existe é 404 em toda rota."""
    for metodo, caminho, corpo in (
        ("get", "/api/v1/projects/nao-existe/protocols", None),
        ("get", "/api/v1/projects/nao-existe/prediction-accuracy", None),
        ("get", "/api/v1/protocols/nao-existe", None),
        ("patch", "/api/v1/protocols/nao-existe/status", {"status": ProtocolStatus.EM_ANALISE}),
        ("get", "/api/v1/protocols/nao-existe/requirements", None),
        ("patch", "/api/v1/requirements/nao-existe", {"due_date": "2026-10-10"}),
    ):
        kwargs = {"json": corpo} if corpo else {}
        response = getattr(client, metodo)(caminho, headers=engineer_headers, **kwargs)
        assert response.status_code == 404, (caminho, response.status_code)


def test_protocolo_recusa_versao_que_nao_e_do_empreendimento(
    client, engineer_headers, project_com_bloqueio, seeded_catalog
):
    outro = client.post(
        "/api/v1/projects", headers=engineer_headers, json={"name": "Outro", "zone": "Z2"}
    ).json()
    versao_alheia = client.get(
        f"/api/v1/projects/{outro['id']}", headers=engineer_headers
    ).json()["current_version"]["id"]

    for versao in (versao_alheia, "nao-existe"):
        response = client.post(
            f"/api/v1/projects/{project_com_bloqueio['id']}/protocols",
            headers=engineer_headers,
            json={"protocol_number": "2026/PMU-9", "agency": "Secretaria", "project_version_id": versao},
        )
        assert response.status_code == 422, versao
        assert "não pertence a este empreendimento" in response.json()["detail"]


def test_exigencias_listam_na_ordem_de_registro(client, engineer_headers, process):
    assert client.get(
        f"/api/v1/protocols/{process['id']}/requirements", headers=engineer_headers
    ).json() == []

    primeira = _exigencia(client, engineer_headers, process["id"], description="Primeira.")
    segunda = _exigencia(client, engineer_headers, process["id"], description="Segunda.")

    lista = client.get(
        f"/api/v1/protocols/{process['id']}/requirements", headers=engineer_headers
    ).json()
    assert [(r["sequence"], r["id"]) for r in lista] == [(1, primeira["id"]), (2, segunda["id"])]


def test_exigencias_de_outro_tenant_respondem_404(client, db_session, process):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user

    intruso = make_user(
        db_session, make_org(db_session, "Concorrente Req S.A."), UserRole.OWNER, "intruso-reqs@atlas-qa.com"
    )
    headers = auth_headers(client, intruso.email)

    assert client.get(
        f"/api/v1/protocols/{process['id']}/requirements", headers=headers
    ).status_code == 404


def test_atualizar_exigencia_so_mexe_no_que_veio(client, engineer_headers, process):
    exigencia = _exigencia(client, engineer_headers, process["id"])

    response = client.patch(
        f"/api/v1/requirements/{exigencia['id']}",
        headers=engineer_headers,
        json={"due_date": "2026-10-10"},
    )

    assert response.status_code == 200
    assert response.json()["due_date"] == "2026-10-10"
    assert response.json()["status"] == exigencia["status"]
    assert response.json()["description"] == exigencia["description"]


def test_atualizar_exigencia_recusa_situacao_inventada(client, engineer_headers, process):
    exigencia = _exigencia(client, engineer_headers, process["id"])

    response = client.patch(
        f"/api/v1/requirements/{exigencia['id']}",
        headers=engineer_headers,
        json={"status": "inventado"},
    )

    assert response.status_code == 422
    assert "Situação inválida" in response.json()["detail"]


def test_exigencia_vinculada_sem_analise_ou_sem_correspondencia_nao_e_prevista_nem_imprevista(
    client, engineer_headers, db_session, project_com_bloqueio, process
):
    """`was_predicted` só vale quando houve análise *e* ela falou da regra."""
    # Há análise, mas ela não tem essa regra.
    sem_correspondencia = _exigencia(
        client, engineer_headers, process["id"], linked_rule_key="regra_que_nao_existe"
    )
    assert sem_correspondencia["was_predicted"] is None

    # Não há análise alguma.
    from app.models.domain import AnalysisRun

    db_session.query(AnalysisRun).filter_by(project_id=project_com_bloqueio["id"]).delete()
    db_session.commit()
    sem_analise = _exigencia(
        client, engineer_headers, process["id"], linked_rule_key="lajeado_recuo_frontal_z2"
    )
    assert sem_analise["was_predicted"] is None


def test_exigencia_nao_tira_o_processo_de_correcao(client, engineer_headers, process):
    client.patch(
        f"/api/v1/protocols/{process['id']}/status",
        headers=engineer_headers,
        json={"status": ProtocolStatus.EM_CORRECAO},
    )

    _exigencia(client, engineer_headers, process["id"], description="Exigência extra.")

    detalhe = client.get(f"/api/v1/protocols/{process['id']}", headers=engineer_headers).json()
    assert detalhe["status"] == ProtocolStatus.EM_CORRECAO