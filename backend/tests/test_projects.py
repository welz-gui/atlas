"""Empreendimentos: cadastro, leitura, atualização e isolamento (§8.2, §3.1).

A atualização por `PATCH` altera apenas dados de identidade do empreendimento.
Parâmetro urbanístico pertence a `ProjectVersion` e só muda criando versão nova,
com autor, motivo e hash — ver `test_atualizacao_ignora_parametros_urbanisticos`,
que trava essa fronteira (§3.2, §14.15).
"""

from app.core.security import hash_password
from app.models.domain import Organization, User, UserRole

# --- Organizações ------------------------------------------------------------


def test_lista_organizacoes_do_usuario(client, engineer_headers, org):
    response = client.get("/api/v1/organizations", headers=engineer_headers)
    assert response.status_code == 200
    assert any(o["id"] == org.id for o in response.json())


# --- Cadastro ----------------------------------------------------------------


def _payload(org_id: str, **overrides) -> dict:
    payload = {
        "name": "Novo Empreendimento",
        "organization_id": org_id,
        "zone": "Z2",
        "building_type": "residencial_unifamiliar",
        "lot_area": 500.0,
        "built_area": 250.0,
        "floors": 2,
        "front_setback": 5.0,
        "rear_setback": 4.0,
        "permeability_rate": 20.0,
        "parking_spaces": 2,
    }
    payload.update(overrides)
    return payload


def test_cria_empreendimento(client, engineer_headers, seeded_catalog, org):
    response = client.post(
        "/api/v1/projects", headers=engineer_headers, json=_payload(org.id)
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Novo Empreendimento"


def test_cadastro_exige_permissao_de_escrita(client, validator_headers, org):
    """`validator` publica regra; não cadastra empreendimento."""
    response = client.post(
        "/api/v1/projects",
        headers=validator_headers,
        json=_payload(org.id, name="Sem Permissão"),
    )
    assert response.status_code == 403


def test_cadastro_sem_nome_e_recusado(client, engineer_headers, org):
    payload = _payload(org.id)
    del payload["name"]
    response = client.post("/api/v1/projects", headers=engineer_headers, json=payload)
    assert response.status_code == 422


# --- Leitura -----------------------------------------------------------------


def test_lista_empreendimentos(client, engineer_headers, project):
    response = client.get("/api/v1/projects", headers=engineer_headers)
    assert response.status_code == 200
    assert any(p["id"] == project["id"] for p in response.json())


def test_le_empreendimento(client, engineer_headers, project):
    response = client.get(
        f"/api/v1/projects/{project['id']}", headers=engineer_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project["id"]
    assert data["name"] == project["name"]


def test_empreendimento_inexistente_responde_404(client, engineer_headers):
    response = client.get("/api/v1/projects/nao-existe", headers=engineer_headers)
    assert response.status_code == 404


def test_empreendimento_de_outro_tenant_responde_404(client, db_session, project):
    """404, nunca 403 — 403 confirmaria que o recurso existe (§3.1)."""
    outra_org = Organization(name="Outra Org")
    db_session.add(outra_org)
    db_session.commit()

    senha = "senha-de-teste-123"
    outro_usuario = User(
        organization_id=outra_org.id,
        name="Usuário Outra Org",
        email="outro@atlas-qa.com",
        role=UserRole.ENGINEER,
        password_hash=hash_password(senha),
    )
    db_session.add(outro_usuario)
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": outro_usuario.email, "password": senha},
    )
    outros_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(
        f"/api/v1/projects/{project['id']}", headers=outros_headers
    )
    assert response.status_code == 404


# --- Atualização -------------------------------------------------------------


def test_atualiza_dados_de_identidade(client, engineer_headers, project):
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"name": "Novo Nome do Projeto", "description": "Nova descrição"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Novo Nome do Projeto"
    assert data["description"] == "Nova descrição"


def test_atualizacao_e_parcial(client, engineer_headers, project):
    nome_original = project["name"]
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"description": "Atualizando apenas a descrição"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Atualizando apenas a descrição"
    assert data["name"] == nome_original


def test_atualizacao_ignora_parametros_urbanisticos(
    client, engineer_headers, project
):
    """Parâmetro urbanístico não muda por PATCH; muda criando versão (I5, §3.2)."""
    recuo_original = project["current_version"]["front_setback"]
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"name": "Nome Atualizado", "front_setback": 1.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nome Atualizado"
    assert data["current_version"]["front_setback"] == recuo_original


def test_atualizacao_de_inexistente_responde_404(client, engineer_headers):
    response = client.patch(
        "/api/v1/projects/nao-existe",
        headers=engineer_headers,
        json={"name": "Nome que não será salvo"},
    )
    assert response.status_code == 404


def test_atualizacao_sem_autenticacao_e_recusada(client, project):
    response = client.patch(
        f"/api/v1/projects/{project['id']}", json={"name": "Invasor"}
    )
    assert response.status_code == 401
