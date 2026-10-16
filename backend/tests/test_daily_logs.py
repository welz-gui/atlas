
CONTEUDO = {
    "date": "2026-08-14",
    "weather_condition": "ensolarado",
    "manpower_own": 12,
    "manpower_subcontracted": 3,
    "activities_done": "Concretagem da laje do 2º pavimento.",
    "occurrences": "Chuva a partir das 16h.",
}

def _criar(client, headers, project_id, **extras):
    corpo = {**CONTEUDO, **extras}
    response = client.post(
        f"/api/v1/projects/{project_id}/daily-logs", headers=headers, json=corpo
    )
    assert response.status_code == 201, response.text
    return response.json()

def test_list_project_daily_logs_empty(client, engineer_headers, project):
    response = client.get(
        f"/api/v1/projects/{project['id']}/daily-logs", headers=engineer_headers
    )
    assert response.status_code == 200
    assert response.json() == []

def test_list_project_daily_logs_populated(client, engineer_headers, project):
    log1 = _criar(client, engineer_headers, project["id"], date="2026-08-14")
    log2 = _criar(client, engineer_headers, project["id"], date="2026-08-15")

    response = client.get(
        f"/api/v1/projects/{project['id']}/daily-logs", headers=engineer_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # The order should be descending by date
    assert data[0]["id"] == log2["id"]
    assert data[1]["id"] == log1["id"]

def test_list_project_daily_logs_404(client, engineer_headers):
    response = client.get(
        f"/api/v1/projects/not-found/daily-logs", headers=engineer_headers
    )
    assert response.status_code == 404

def test_list_project_daily_logs_other_tenant(client, engineer_headers, project, db_session):
    from tests.conftest import auth_headers, make_org, make_user
    from app.models.domain import UserRole

    # Create logs for the current project
    _criar(client, engineer_headers, project["id"])

    # Create another organization and user
    outra = make_org(db_session, name="Outra Construtora")
    intruso = make_user(
        db_session, outra, UserRole.ENGINEER, email="intruso2@atlas-qa.com"
    )
    headers = auth_headers(client, intruso.email)

    # Attempt to list logs from the other organization's project
    resposta = client.get(
        f"/api/v1/projects/{project['id']}/daily-logs", headers=headers
    )
    assert resposta.status_code == 404
