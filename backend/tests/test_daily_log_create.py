"""Diário de obra: criação e listagem (§3.7). A idempotência por `client_token`
e a assinatura têm testes próprios (`test_jobs.py`, `test_daily_log_signature.py`).
"""

from app.models.domain import DailyLogState, UserRole
from tests.conftest import auth_headers, make_org, make_user


def _criar(client, headers, project_id, **corpo):
    corpo = {"date": "2026-08-14", "activities_done": "Concretagem da laje.", **corpo}
    return client.post(f"/api/v1/projects/{project_id}/daily-logs", headers=headers, json=corpo)


def test_diario_so_com_o_obrigatorio_nasce_com_os_padroes(client, engineer_headers, project):
    response = _criar(client, engineer_headers, project["id"])

    assert response.status_code == 201, response.text
    log = response.json()
    assert log["status"] == DailyLogState.RASCUNHO
    assert log["weather_condition"] == "ensolarado"
    assert log["manpower_own"] == 0
    assert log["manpower_subcontracted"] == 0
    assert log["occurrences"] is None


def test_diario_de_projeto_inexistente_ou_de_outro_tenant_responde_404(
    client, db_session, engineer_headers, project
):
    intruso = make_user(
        db_session, make_org(db_session, "Outra Construtora"), UserRole.ENGINEER, "intruso-diario@atlas-qa.com"
    )
    alheio = auth_headers(client, intruso.email)

    assert _criar(client, engineer_headers, "nao-existe").status_code == 404
    assert _criar(client, alheio, project["id"]).status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/daily-logs", headers=alheio).status_code == 404
    assert client.get("/api/v1/projects/nao-existe/daily-logs", headers=engineer_headers).status_code == 404


def test_lista_de_diarios_vem_do_dia_mais_recente_para_o_mais_antigo(
    client, engineer_headers, project
):
    caminho = f"/api/v1/projects/{project['id']}/daily-logs"
    assert client.get(caminho, headers=engineer_headers).json() == []

    antigo = _criar(client, engineer_headers, project["id"], date="2026-08-14").json()
    recente = _criar(client, engineer_headers, project["id"], date="2026-08-15").json()

    ids = [log["id"] for log in client.get(caminho, headers=engineer_headers).json()]
    assert ids == [recente["id"], antigo["id"]]


def test_assinar_diario_inexistente_responde_404(client, engineer_headers):
    assert client.post("/api/v1/daily-logs/nao-existe/sign", headers=engineer_headers).status_code == 404