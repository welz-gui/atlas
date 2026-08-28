import pytest
from fastapi import HTTPException
from app.api.deps import require_permission


def test_require_permission_success(engineer):
    dep = require_permission("project:write")
    assert dep(user=engineer) == engineer


def test_require_permission_forbidden(engineer):
    dep = require_permission("org:manage")
    with pytest.raises(HTTPException) as excinfo:
        dep(user=engineer)
    assert excinfo.value.status_code == 403
    assert "não tem permissão" in excinfo.value.detail


def test_require_permission_mfa_required_but_missing(usuario_sem_mfa):
    dep = require_permission("catalog:validate")
    with pytest.raises(HTTPException) as excinfo:
        dep(user=usuario_sem_mfa)
    assert excinfo.value.status_code == 403
    assert "exige segundo fator" in excinfo.value.detail
    assert excinfo.value.headers["X-Atlas-MFA-Required"] == "true"


def test_require_permission_mfa_required_and_present(validator):
    dep = require_permission("catalog:validate")
    assert dep(user=validator) == validator
