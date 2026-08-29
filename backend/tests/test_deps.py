"""Testes de app/api/deps.py: autenticação, permissão e escopo por tenant.

Combina e depura a cobertura proposta em seis PRs do Jules (#96, #102, #105,
#107, #112, #131), todos criando o mesmo arquivo novo — cada um cobrindo uma
função diferente, sem sobreposição real de conteúdo. Em vez de escolher um e
descartar os outros cinco, este arquivo reúne o que cada um tinha de correto
e testado contra o código real.
"""

import jwt
import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import (
    CREDENTIALS_ERROR,
    get_current_user,
    get_project_or_404,
    get_scoped_or_404,
    require_permission,
    tenant_query,
)
from app.core.config import settings
from app.core.security import create_access_token
from app.core.tenant import current_organization_id, set_current_organization
from app.models.domain import Project, TaskItem, UserRole
from tests.conftest import make_org, make_user


@pytest.fixture(autouse=True)
def clean_tenant_context():
    """A ContextVar de organização normalmente é limpa pelo middleware
    `tenant_scope` (app/main.py). Chamar `get_current_user` direto, como os
    testes abaixo fazem, pula o middleware — então a limpeza fica por conta
    do teste.
    """
    set_current_organization(None)
    yield
    set_current_organization(None)


# --- get_current_user --------------------------------------------------------


def test_get_current_user_sem_credencial(db_session):
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=None, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_credencial_vazia(db_session):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_token_invalido(db_session):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-forjado")
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_token_sem_sub(db_session, engineer):
    """Token assinado, mas sem o claim `sub` — não há a quem atribuir a sessão."""
    token = jwt.encode(
        {"org": engineer.organization_id, "role": engineer.role},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_usuario_inexistente(db_session, org):
    token = create_access_token("usuario-que-nao-existe", org.id, UserRole.ENGINEER)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_usuario_inativo(db_session, engineer):
    engineer.is_active = False
    db_session.commit()
    token = create_access_token(engineer.id, engineer.organization_id, engineer.role)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_organizacao_do_token_diverge_do_registro(db_session, engineer):
    """O token diz uma organização; o registro atual do usuário diz outra.

    Cobre o caso de alguém trocado de organização enquanto o token antigo
    ainda não expirou — o registro atual manda, não o token.
    """
    token = create_access_token(engineer.id, "outra-organizacao-qualquer", engineer.role)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=creds, db=db_session)
    assert exc.value == CREDENTIALS_ERROR


def test_get_current_user_caminho_feliz(db_session, engineer):
    token = create_access_token(engineer.id, engineer.organization_id, engineer.role)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = get_current_user(credentials=creds, db=db_session)

    assert user.id == engineer.id
    # A dependência publica a organização na ContextVar antes da 1ª consulta.
    assert current_organization_id() == engineer.organization_id


# --- require_permission -------------------------------------------------------


def test_require_permission_concedida(engineer):
    dep = require_permission("project:write")
    assert dep(user=engineer) == engineer


def test_require_permission_negada(engineer):
    dep = require_permission("org:manage")
    with pytest.raises(HTTPException) as excinfo:
        dep(user=engineer)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
    assert "não tem permissão" in excinfo.value.detail


def test_require_permission_mfa_exigido_e_ausente(usuario_sem_mfa):
    dep = require_permission("catalog:validate")
    with pytest.raises(HTTPException) as excinfo:
        dep(user=usuario_sem_mfa)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
    assert "exige segundo fator" in excinfo.value.detail
    assert excinfo.value.headers["X-Atlas-MFA-Required"] == "true"


def test_require_permission_mfa_exigido_e_presente(validator):
    dep = require_permission("catalog:validate")
    assert dep(user=validator) == validator


# --- tenant_query --------------------------------------------------------------


def test_tenant_query_restringe_a_organizacao(db_session, org, engineer, project):
    outra_org = make_org(db_session, "Outra Organização")
    outro_usuario = make_user(db_session, outra_org, email="outro@atlas-qa.com")

    projeto_de_outra_org = Project(
        name="Projeto de outra organização",
        organization_id=outra_org.id,
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS",
    )
    db_session.add(projeto_de_outra_org)
    db_session.commit()

    resultado = tenant_query(db_session, Project, engineer).all()
    assert [p.id for p in resultado] == [project["id"]]

    resultado_outra_org = tenant_query(db_session, Project, outro_usuario).all()
    assert [p.id for p in resultado_outra_org] == [projeto_de_outra_org.id]


# --- get_project_or_404 ---------------------------------------------------------


def test_get_project_or_404_sucesso(db_session, project, engineer):
    encontrado = get_project_or_404(db_session, project["id"], engineer)
    assert str(encontrado.id) == project["id"]
    assert encontrado.organization_id == engineer.organization_id


def test_get_project_or_404_inexistente(db_session, engineer):
    with pytest.raises(HTTPException) as exc_info:
        get_project_or_404(db_session, "00000000-0000-0000-0000-000000000000", engineer)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Empreendimento não encontrado."


def test_get_project_or_404_outro_tenant_responde_404(db_session, project):
    """Projeto de outra organização — 404, não 403, para não confirmar que existe."""
    outra_org = make_org(db_session, "Outra Construtora")
    intruso = make_user(db_session, outra_org, UserRole.ENGINEER, "intruso@atlas-qa.com")

    with pytest.raises(HTTPException) as exc_info:
        get_project_or_404(db_session, project["id"], intruso)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Empreendimento não encontrado."


# --- get_scoped_or_404 ----------------------------------------------------------


def test_get_scoped_or_404_sucesso(db_session, engineer, project):
    task = TaskItem(
        organization_id=engineer.organization_id,
        project_id=project["id"],
        title="Tarefa de teste",
    )
    db_session.add(task)
    db_session.commit()

    resultado = get_scoped_or_404(db_session, TaskItem, task.id, engineer, "Tarefa")

    assert resultado.id == task.id
    assert resultado.title == "Tarefa de teste"


def test_get_scoped_or_404_inexistente(db_session, engineer):
    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, TaskItem, "id-inexistente", engineer, "Tarefa")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Tarefa não encontrado."


def test_get_scoped_or_404_outro_tenant_responde_404(db_session, engineer, project):
    task = TaskItem(
        organization_id=engineer.organization_id,
        project_id=project["id"],
        title="Tarefa de teste",
    )
    db_session.add(task)
    db_session.commit()

    outra_org = make_org(db_session, "Outra Org")
    outro_usuario = make_user(
        db_session, outra_org, UserRole.ENGINEER, "outro-scoped@atlas-qa.com"
    )

    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, TaskItem, task.id, outro_usuario, "Tarefa")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Tarefa não encontrado."


def test_get_scoped_or_404_label_padrao(db_session, engineer):
    """Sem `label`, a mensagem cai para o genérico 'Recurso'."""
    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, TaskItem, "id-inexistente", engineer)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Recurso não encontrado."
