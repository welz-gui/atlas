from unittest.mock import patch

def test_update_project_success(client, engineer_headers, project):
    """Verifica a atualização de campos de identidade (caminho feliz)."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"name": "Novo Nome do Projeto", "description": "Nova descrição"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Novo Nome do Projeto"
    assert data["description"] == "Nova descrição"

def test_update_project_not_found(client, engineer_headers):
    """Verifica comportamento ao tentar atualizar projeto inexistente."""
    response = client.patch(
        "/api/v1/projects/projeto-inexistente-123",
        headers=engineer_headers,
        json={"name": "Nome que não será salvo"},
    )
    assert response.status_code == 404

def test_update_project_unauthorized(client, project):
    """Verifica recusa de atualização sem autenticação."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Invasor"},
    )
    assert response.status_code == 401

def test_update_project_partial_update(client, engineer_headers, project):
    """Verifica que a atualização é parcial (PATCH)."""
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

def test_update_project_ignore_urbanistic_parameters(client, engineer_headers, project):
    """Verifica que parâmetros urbanísticos não podem ser alterados por aqui."""
    original_front_setback = project["current_version"]["front_setback"]
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"name": "Nome Atualizado", "front_setback": 1.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nome Atualizado"
    assert data["current_version"]["front_setback"] == original_front_setback

def test_update_project_triggers_evaluation(client, engineer_headers, project):
    """Verifica se a avaliação de regras é chamada ao atualizar."""
    with patch("app.api.v1.endpoints.projects.RegulatoryEngine.evaluate_project") as mock_evaluate:
        response = client.patch(
            f"/api/v1/projects/{project['id']}",
            headers=engineer_headers,
            json={"name": "Test Eval Trigger"},
        )
        assert response.status_code == 200
        mock_evaluate.assert_called_once()
        args, kwargs = mock_evaluate.call_args
        assert args[1].id == project['id']
