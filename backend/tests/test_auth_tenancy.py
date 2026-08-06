"""Autenticação e isolamento entre organizações (§3.1, §12)."""

import pytest

from app.core.security import PERMISSIONS, hash_password, role_has_permission, verify_password
from app.models.domain import UserRole
from tests.conftest import TEST_PASSWORD, auth_headers, make_org, make_user

# Endpoints de negócio que jamais devem responder sem autenticação.
PROTECTED = [
    ("get", "/api/v1/projects"),
    ("post", "/api/v1/projects"),
    ("get", "/api/v1/catalog/rules"),
    ("get", "/api/v1/catalog/validation-queue"),
    ("post", "/api/v1/ai/chat"),
    ("get", "/api/v1/users"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_endpoints_de_negocio_exigem_autenticacao(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401, f"{method.upper()} {path} respondeu sem token"


def test_health_permanece_publico(client):
    assert client.get("/api/v1/health").status_code == 200


def test_login_e_me(client, engineer):
    headers = auth_headers(client, engineer.email)
    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == engineer.email
    assert "password_hash" not in response.json()


def test_senha_incorreta_e_email_inexistente_dao_a_mesma_resposta(client, engineer):
    errado = client.post(
        "/api/v1/auth/login", json={"email": engineer.email, "password": "senha-errada-x"}
    )
    inexistente = client.post(
        "/api/v1/auth/login",
        json={"email": "ninguem@atlas-qa.com", "password": TEST_PASSWORD},
    )

    assert errado.status_code == inexistente.status_code == 401
    assert errado.json()["detail"] == inexistente.json()["detail"]


def test_token_invalido_e_recusado(client):
    response = client.get(
        "/api/v1/projects", headers={"Authorization": "Bearer nao-e-um-token"}
    )
    assert response.status_code == 401


def test_usuario_desativado_perde_acesso(client, db_session, engineer):
    headers = auth_headers(client, engineer.email)
    assert client.get("/api/v1/projects", headers=headers).status_code == 200

    engineer.is_active = False
    db_session.commit()

    assert client.get("/api/v1/projects", headers=headers).status_code == 401


def test_senha_nao_e_persistida_em_claro(db_session, engineer):
    assert engineer.password_hash != TEST_PASSWORD
    assert engineer.password_hash.startswith("$argon2")
    assert verify_password(TEST_PASSWORD, engineer.password_hash)


def test_hash_da_mesma_senha_difere_entre_usuarios():
    """Salt por hash: senhas iguais não podem gerar hashes iguais."""
    assert hash_password("mesma-senha-longa") != hash_password("mesma-senha-longa")


# --- Isolamento entre tenants ----------------------------------------------

def test_projeto_de_outra_organizacao_responde_404(client, db_session, project):
    outra_org = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra_org, UserRole.OWNER, "intruso@atlas-qa.com")
    headers = auth_headers(client, intruso.email)

    # Existe, mas não para este tenant: 404, não 403 — dizer "existe, mas você
    # não pode ver" já é vazamento entre organizações.
    assert client.get(f"/api/v1/projects/{project['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/validations", headers=headers).status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/documents", headers=headers).status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/report/pdf", headers=headers).status_code == 404


def test_listagem_nao_vaza_projetos_de_outra_organizacao(client, db_session, project):
    outra_org = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra_org, UserRole.OWNER, "intruso2@atlas-qa.com")

    assert client.get("/api/v1/projects", headers=auth_headers(client, intruso.email)).json() == []


def test_alteracao_em_projeto_de_outro_tenant_e_bloqueada(client, db_session, project):
    outra_org = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra_org, UserRole.OWNER, "intruso3@atlas-qa.com")
    headers = auth_headers(client, intruso.email)

    assert client.patch(
        f"/api/v1/projects/{project['id']}", headers=headers, json={"name": "sequestrado"}
    ).status_code == 404
    assert client.post(
        f"/api/v1/projects/{project['id']}/evaluate", headers=headers
    ).status_code == 404


# --- Permissões -------------------------------------------------------------

def test_cliente_nao_altera_projeto(client, db_session, org, project):
    cliente = make_user(db_session, org, UserRole.CLIENT, "cliente@atlas-qa.com")
    headers = auth_headers(client, cliente.email)

    # Lê o que é da sua organização...
    assert client.get(f"/api/v1/projects/{project['id']}", headers=headers).status_code == 200
    # ...mas não escreve.
    assert client.patch(
        f"/api/v1/projects/{project['id']}", headers=headers, json={"name": "novo"}
    ).status_code == 403


def test_engenheiro_nao_publica_regra(client, db_session, engineer_headers, seeded_catalog):
    from app.models.domain import RegulatoryRule

    rule = seeded_catalog.query(RegulatoryRule).first()
    response = client.post(
        f"/api/v1/catalog/rules/{rule.id}/validate",
        headers=engineer_headers,
        json={"action": "publicar"},
    )
    assert response.status_code == 403


def test_engenheiro_nao_gerencia_usuarios(client, engineer_headers):
    assert client.get("/api/v1/users", headers=engineer_headers).status_code == 403


def test_matriz_de_permissoes_nao_da_escrita_ao_cliente():
    for permission, roles in PERMISSIONS.items():
        if permission.endswith((":write", ":manage", ":validate", ":baseline")):
            assert UserRole.CLIENT not in roles, permission
            assert role_has_permission(UserRole.CLIENT, permission) is False


def test_signup_cria_organizacao_com_owner(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Nova Construtora",
            "name": "Fundador",
            "email": "fundador@nova-qa.com",
            "password": "uma-senha-bem-longa",
        },
    )
    assert response.status_code == 201

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["role"] == UserRole.OWNER


def test_signup_recusa_email_duplicado(client, engineer):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Outra",
            "name": "Alguém",
            "email": engineer.email,
            "password": "uma-senha-bem-longa",
        },
    )
    assert response.status_code == 409


def test_signup_recusa_senha_curta(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Outra",
            "name": "Alguém",
            "email": "curta@nova-qa.com",
            "password": "123",
        },
    )
    assert response.status_code == 422
