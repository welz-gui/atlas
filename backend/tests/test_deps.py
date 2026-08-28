"""Testes para dependências de autenticação e organização."""

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import CREDENTIALS_ERROR, get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.core.tenant import current_organization_id, set_current_organization

from app.models.domain import UserRole


@pytest.fixture(autouse=True)
def clean_tenant_context():
    """Garante que a ContextVar seja limpa após cada teste, já que
    testar get_current_user diretamente pula o middleware que faria isso.
    """
    set_current_organization(None)
    yield
    set_current_organization(None)


def test_get_current_user_no_credentials(db_session):
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=None, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_empty_credentials(db_session):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_invalid_token(db_session):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_missing_sub(db_session, engineer):
    token = jwt.encode(
        {"org": engineer.organization_id, "role": engineer.role},
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_not_found(db_session, org):
    token = create_access_token("user-not-found-id", org.id, UserRole.ENGINEER)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_inactive(db_session, engineer):
    engineer.is_active = False
    db_session.commit()
    token = create_access_token(engineer.id, engineer.organization_id, engineer.role)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_org_mismatch(db_session, engineer):
    # O token pertence ao engenheiro, mas diz que ele está em outra organização.
    token = create_access_token(engineer.id, "outra-org", engineer.role)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_happy_path(db_session, engineer):
    token = create_access_token(engineer.id, engineer.organization_id, engineer.role)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = get_current_user(credentials=creds, db=db_session)

    assert user.id == engineer.id
    # A dependência garante a publicação da organização no escopo local.
    assert current_organization_id() == engineer.organization_id
