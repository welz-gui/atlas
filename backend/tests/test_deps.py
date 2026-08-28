"""Testes para dependências (deps.py)."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from app.api.deps import require_permission
from app.models.domain import UserRole

# Permissões conhecidas (app/core/security.py)
# - "project:read" -> não exige MFA
# - "org:manage" -> exige MFA


def test_require_permission_success():
    """Deve retornar o usuário quando a permissão é válida e não exige MFA."""
    dependency = require_permission("project:read")
    user_mock = MagicMock()
    user_mock.role = UserRole.ENGINEER

    # Executa a dependência sem levantar erro
    result = dependency(user_mock)

    assert result == user_mock


def test_require_permission_denied():
    """Deve levantar 403 Forbidden se o usuário não tiver o papel necessário."""
    dependency = require_permission("project:write")
    user_mock = MagicMock()
    user_mock.role = UserRole.CLIENT  # Client não pode escrever

    with pytest.raises(HTTPException) as excinfo:
        dependency(user_mock)

    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
    assert excinfo.value.detail == f"O papel '{UserRole.CLIENT}' não tem permissão para 'project:write'."


def test_require_permission_mfa_required_but_inactive():
    """Deve levantar 403 com cabeçalho X-Atlas-MFA-Required se a permissão exige MFA, mas ele não está ativo."""
    dependency = require_permission("org:manage")
    user_mock = MagicMock()
    user_mock.role = UserRole.OWNER  # Owner tem permissão, mas org:manage exige MFA
    user_mock.mfa_active = False

    with pytest.raises(HTTPException) as excinfo:
        dependency(user_mock)

    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
    assert excinfo.value.detail == "'org:manage' exige segundo fator. Cadastre-o em POST /auth/mfa/enroll."
    assert excinfo.value.headers == {"X-Atlas-MFA-Required": "true"}


def test_require_permission_mfa_required_and_active():
    """Deve retornar o usuário se a permissão exige MFA e ele está ativo."""
    dependency = require_permission("org:manage")
    user_mock = MagicMock()
    user_mock.role = UserRole.OWNER
    user_mock.mfa_active = True

    # Executa a dependência sem levantar erro
    result = dependency(user_mock)

    assert result == user_mock
