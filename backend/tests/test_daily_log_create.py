from app.models.domain import DailyLogState

CONTEUDO = {
    "date": "2026-08-14",
    "weather_condition": "ensolarado",
    "manpower_own": 12,
    "manpower_subcontracted": 3,
    "activities_done": "Concretagem da laje do 2º pavimento.",
    "occurrences": "Chuva a partir das 16h.",
}

def test_criar_diario_basico(client, engineer_headers, project):
    corpo = {**CONTEUDO}
    response = client.post(
        f"/api/v1/projects/{project['id']}/daily-logs",
        headers=engineer_headers,
        json=corpo
    )
    assert response.status_code == 201
    log = response.json()
    assert log["date"] == "2026-08-14"
    assert log["weather_condition"] == "ensolarado"
    assert log["status"] == DailyLogState.RASCUNHO
    assert "id" in log

def test_criacao_e_idempotente_com_client_token(client, engineer_headers, project):
    corpo = {**CONTEUDO, "client_token": "token-xyz-123"}
    # Primeira chamada
    r1 = client.post(
        f"/api/v1/projects/{project['id']}/daily-logs",
        headers=engineer_headers,
        json=corpo
    )
    assert r1.status_code == 201
    log1 = r1.json()

    # Segunda chamada com o mesmo client_token
    r2 = client.post(
        f"/api/v1/projects/{project['id']}/daily-logs",
        headers=engineer_headers,
        json=corpo
    )
    assert r2.status_code == 201
    log2 = r2.json()

    # Deve retornar o mesmo registro, não criar um novo
    assert log1["id"] == log2["id"]

def test_criar_diario_projeto_inexistente(client, engineer_headers):
    corpo = {**CONTEUDO}
    response = client.post(
        f"/api/v1/projects/proj-inexistente/daily-logs",
        headers=engineer_headers,
        json=corpo
    )
    assert response.status_code == 404
def test_criar_diario_campos_opcionais_vazios(client, engineer_headers, project):
    corpo = {
        "date": "2026-08-14",
        "activities_done": "Concretagem da laje do 2º pavimento.",
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/daily-logs",
        headers=engineer_headers,
        json=corpo
    )
    assert response.status_code == 201
    log = response.json()
    assert log["weather_condition"] == "ensolarado"  # default
    assert log["manpower_own"] == 0  # default
    assert log["manpower_subcontracted"] == 0  # default
    assert log["occurrences"] is None

def test_criar_diario_sem_permissao(client, project, db_session):
    from tests.conftest import auth_headers, make_user, make_org
    from app.models.domain import UserRole

    outra_org = make_org(db_session, name="Outra Org")
    intruso = make_user(db_session, outra_org, UserRole.ENGINEER, email="intruso@atlas-qa.com")
    headers = auth_headers(client, intruso.email)

    corpo = {**CONTEUDO}
    response = client.post(
        f"/api/v1/projects/{project['id']}/daily-logs",
        headers=headers,
        json=corpo
    )
    assert response.status_code == 404
