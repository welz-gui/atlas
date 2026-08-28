import pytest
from fastapi import HTTPException

from app.api.deps import get_project_or_404
from app.models.domain import UserRole
from tests.conftest import make_org, make_user


def test_get_project_or_404_success(db_session, project, engineer):
    """Testa a busca de um projeto existente e pertencente ao tenant do usuário."""
    fetched = get_project_or_404(db_session, project["id"], engineer)
    assert str(fetched.id) == project["id"]
    assert fetched.organization_id == engineer.organization_id


def test_get_project_or_404_not_found(db_session, engineer):
    """Testa a busca de um projeto que não existe."""
    with pytest.raises(HTTPException) as exc_info:
        get_project_or_404(
            db_session, "00000000-0000-0000-0000-000000000000", engineer
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Empreendimento não encontrado."


def test_get_project_or_404_wrong_tenant(db_session, project):
    """Testa a busca de um projeto que pertence a outra organização (vazamento entre tenants)."""
    outra_org = make_org(db_session, "Outra Construtora")
    intruso = make_user(
        db_session, outra_org, UserRole.ENGINEER, "intruso@outra-qa.com"
    )

    with pytest.raises(HTTPException) as exc_info:
        get_project_or_404(db_session, project["id"], intruso)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Empreendimento não encontrado."
