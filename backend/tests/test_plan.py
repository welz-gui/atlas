"""Testes da EAP (Estrutura Analítica do Projeto) e Tarefas."""

from app.models.domain import EAPItem

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


def test_lista_de_tarefas_vem_da_mais_recente_para_a_mais_antiga(
    client, engineer_headers, db_session, org, project, engineer
):
    from datetime import datetime, timedelta

    from app.models.domain import TaskItem

    caminho = f"/api/v1/projects/{project['id']}/tasks"
    assert client.get(caminho, headers=engineer_headers).json() == []

    agora = datetime.utcnow()
    for titulo, idade in (("Antiga", 2), ("Recente", 1)):
        db_session.add(
            TaskItem(
                organization_id=org.id,
                project_id=project["id"],
                title=titulo,
                created_by_id=engineer.id,
                created_at=agora - timedelta(days=idade),
            )
        )
    db_session.commit()

    titulos = [t["title"] for t in client.get(caminho, headers=engineer_headers).json()]
    assert titulos == ["Recente", "Antiga"]


def test_tarefas_de_projeto_inexistente_ou_de_outro_tenant_respondem_404(
    client, db_session, engineer_headers, project
):
    from tests.conftest import auth_headers, make_org, make_user

    intruso = make_user(db_session, make_org(db_session, "Outra Construtora"), email="intruso-tarefas@atlas-qa.com")

    assert client.get("/api/v1/projects/nao-existe/tasks", headers=engineer_headers).status_code == 404
    assert client.get(
        f"/api/v1/projects/{project['id']}/tasks", headers=auth_headers(client, intruso.email)
    ).status_code == 404