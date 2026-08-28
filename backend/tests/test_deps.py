import pytest
from fastapi import HTTPException
from app.api.deps import tenant_query, get_project_or_404, get_scoped_or_404
from app.models.domain import Project

def test_tenant_query_filters_by_organization(db_session, org, engineer, project):
    from tests.conftest import make_org, make_user
    outra_org = make_org(db_session, "Outra Organizacao")
    outra_org_user = make_user(db_session, outra_org, email="outro@example.com")

    projeto_outra_org = Project(
        name="Projeto Outra Org",
        organization_id=outra_org.id,
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS"
    )
    db_session.add(projeto_outra_org)
    db_session.commit()

    query = tenant_query(db_session, Project, engineer)
    results = query.all()

    assert len(results) == 1
    assert results[0].id == project['id']

    query_outro = tenant_query(db_session, Project, outra_org_user)
    results_outro = query_outro.all()

    assert len(results_outro) == 1
    assert results_outro[0].id == projeto_outra_org.id

def test_get_project_or_404_success(db_session, engineer, project):
    # Retrieve the project for the user's organization
    retrieved_project = get_project_or_404(db_session, project['id'], engineer)
    assert retrieved_project.id == project['id']
    assert retrieved_project.name == project['name']

def test_get_project_or_404_not_found_wrong_org(db_session, project):
    from tests.conftest import make_org, make_user
    outra_org = make_org(db_session, "Outra Organizacao")
    outra_org_user = make_user(db_session, outra_org, email="intruso@example.com")

    # User from another org tries to access the project
    with pytest.raises(HTTPException) as exc_info:
        get_project_or_404(db_session, project['id'], outra_org_user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Empreendimento não encontrado."

def test_get_project_or_404_not_found_invalid_id(db_session, engineer):
    with pytest.raises(HTTPException) as exc_info:
        get_project_or_404(db_session, "id_inexistente", engineer)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Empreendimento não encontrado."

def test_get_scoped_or_404_success(db_session, engineer, project):
    # Retrieve scoped model using generic function
    retrieved = get_scoped_or_404(db_session, Project, project['id'], engineer, label="Empreendimento")
    assert retrieved.id == project['id']

def test_get_scoped_or_404_not_found_wrong_org(db_session, project):
    from tests.conftest import make_org, make_user
    outra_org = make_org(db_session, "Outra Organizacao")
    outra_org_user = make_user(db_session, outra_org, email="intruso_scoped@example.com")

    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, Project, project['id'], outra_org_user, label="Recurso")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Recurso não encontrado."
