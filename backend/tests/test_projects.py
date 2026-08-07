import pytest
from app.models.domain import Organization, User, UserRole
from app.core.security import hash_password

def test_list_organizations(client, engineer_headers, org):
    response = client.get("/api/v1/organizations", headers=engineer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == org.id

def test_create_project(client, engineer_headers, seeded_catalog, org):
    response = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={
            "name": "Novo Empreendimento",
            "organization_id": org.id,
            "zone": "Z2",
            "building_type": "residencial_unifamiliar",
            "lot_area": 500.0,
            "built_area": 250.0,
            "floors": 2,
            "front_setback": 5.0,
            "rear_setback": 4.0,
            "permeability_rate": 20.0,
            "parking_spaces": 2,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Novo Empreendimento"

def test_list_projects(client, engineer_headers, project):
    response = client.get("/api/v1/projects", headers=engineer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == project["id"]

def test_get_project(client, engineer_headers, project):
    response = client.get(f"/api/v1/projects/{project['id']}", headers=engineer_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project["id"]
    assert data["name"] == project["name"]

def test_get_project_not_found(client, engineer_headers):
    response = client.get("/api/v1/projects/invalid-id", headers=engineer_headers)
    assert response.status_code == 404

def test_update_project(client, engineer_headers, project):
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"name": "Nome Atualizado"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nome Atualizado"
    # Ensure urban parameters are not updated
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"front_setback": 1.0},
    )
    assert response.status_code == 200
    assert response.json()["current_version"]["front_setback"] == 4.5

def test_create_project_unauthorized(client, validator_headers, org):
    # Validator should not have project:write permission
    response = client.post(
        "/api/v1/projects",
        headers=validator_headers,
        json={
            "name": "Novo Empreendimento Sem Permissão",
            "organization_id": org.id,
            "zone": "Z2",
            "building_type": "residencial_unifamiliar",
            "lot_area": 500.0,
            "built_area": 250.0,
            "floors": 2,
            "front_setback": 5.0,
            "rear_setback": 4.0,
            "permeability_rate": 20.0,
            "parking_spaces": 2,
        },
    )
    assert response.status_code == 403

def test_create_project_invalid_input(client, engineer_headers, org):
    # Missing required field `name`
    response = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={
            "organization_id": org.id,
            "zone": "Z2",
            "building_type": "residencial_unifamiliar",
            "lot_area": 500.0,
            "built_area": 250.0,
            "floors": 2,
            "front_setback": 5.0,
            "rear_setback": 4.0,
            "permeability_rate": 20.0,
            "parking_spaces": 2,
        },
    )
    assert response.status_code == 422

def test_get_project_different_org(client, db_session, project):
    # Create a new org and user manually to avoid importing conftest
    other_org = Organization(name="Outra Org")
    db_session.add(other_org)
    db_session.commit()

    other_user = User(
        organization_id=other_org.id,
        name="Usuário Outra Org",
        email="outro@atlas-qa.com",
        role=UserRole.ENGINEER,
        password_hash=hash_password("senha-de-teste-123"),
    )
    db_session.add(other_user)
    db_session.commit()

    # Login to get token
    login_response = client.post(
        "/api/v1/auth/login", json={"email": other_user.email, "password": "senha-de-teste-123"}
    )
    other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    # Try to access the project from the first org
    response = client.get(f"/api/v1/projects/{project['id']}", headers=other_headers)
    assert response.status_code == 404
