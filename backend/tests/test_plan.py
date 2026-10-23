"""Testes da EAP (Estrutura Analítica do Projeto) e Tarefas."""

from app.models.domain import EAPItem, TaskItem

def test_list_project_eap_empty(client, engineer_headers, project):
    """Uma EAP recém-criada (ou não criada) deve retornar lista vazia."""
    response = client.get(f"/api/v1/projects/{project['id']}/eap", headers=engineer_headers)
    assert response.status_code == 200
    assert response.json() == []

def test_list_project_eap_with_items(client, engineer_headers, db_session, org, project):
    """A lista de itens da EAP deve vir ordenada por código."""
    # Insert EAP items directly in a non-alphabetical order by code
    item1 = EAPItem(
        organization_id=org.id,
        project_id=project["id"],
        code="02",
        name="Fundações",
        item_type="etapa"
    )
    item2 = EAPItem(
        organization_id=org.id,
        project_id=project["id"],
        code="01",
        name="Serviços Preliminares",
        item_type="etapa"
    )
    item3 = EAPItem(
        organization_id=org.id,
        project_id=project["id"],
        code="01.01",
        name="Limpeza do Terreno",
        item_type="atividade"
    )
    db_session.add_all([item1, item2, item3])
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project['id']}/eap", headers=engineer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    # Ensure ordered by code
    assert data[0]["code"] == "01"
    assert data[1]["code"] == "01.01"
    assert data[2]["code"] == "02"

def test_list_project_eap_project_not_found(client, engineer_headers):
    """Tentativa de listar EAP de projeto inexistente deve retornar 404."""
    response = client.get("/api/v1/projects/invalid-id/eap", headers=engineer_headers)
    assert response.status_code == 404

def test_list_project_eap_different_tenant(client, db_session, project):
    """Tentativa de listar EAP de projeto de outra organização deve retornar 404."""
    from tests.conftest import make_org, make_user, auth_headers
    outra_org = make_org(db_session, "Outra Construtora")
    outro_user = make_user(db_session, outra_org, email="outro@construtora.com")
    headers = auth_headers(client, outro_user.email)

    response = client.get(f"/api/v1/projects/{project['id']}/eap", headers=headers)
    assert response.status_code == 404


def test_list_project_tasks_empty(client, engineer_headers, project):
    """Uma lista de tarefas recém-criada (ou não criada) deve retornar lista vazia."""
    response = client.get(f"/api/v1/projects/{project['id']}/tasks", headers=engineer_headers)
    assert response.status_code == 200
    assert response.json() == []

def test_list_project_tasks_with_items(client, engineer_headers, db_session, org, project, engineer):
    """A lista de tarefas deve vir ordenada por data de criação descrescente."""
    import datetime

    # Insert Task items directly
    item1 = TaskItem(
        organization_id=org.id,
        project_id=project["id"],
        title="Tarefa Antiga",
        created_by_id=engineer.id
    )
    # fake created_at
    item1.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)

    item2 = TaskItem(
        organization_id=org.id,
        project_id=project["id"],
        title="Tarefa Recente",
        created_by_id=engineer.id
    )
    # fake created_at
    item2.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    db_session.add_all([item1, item2])
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project['id']}/tasks", headers=engineer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Ensure ordered by created_at desc
    assert data[0]["title"] == "Tarefa Recente"
    assert data[1]["title"] == "Tarefa Antiga"

def test_list_project_tasks_project_not_found(client, engineer_headers):
    """Tentativa de listar tarefas de projeto inexistente deve retornar 404."""
    response = client.get("/api/v1/projects/invalid-id/tasks", headers=engineer_headers)
    assert response.status_code == 404

def test_list_project_tasks_different_tenant(client, db_session, project):
    """Tentativa de listar tarefas de projeto de outra organização deve retornar 404."""
    from tests.conftest import make_org, make_user, auth_headers
    outra_org = make_org(db_session, "Outra Construtora")
    outro_user = make_user(db_session, outra_org, email="outro@construtora.com")
    headers = auth_headers(client, outro_user.email)

    response = client.get(f"/api/v1/projects/{project['id']}/tasks", headers=headers)
    assert response.status_code == 404
