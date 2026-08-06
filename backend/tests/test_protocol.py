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
