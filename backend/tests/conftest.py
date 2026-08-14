import os
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# `app.models.domain` é importado primeiro para registrar as tabelas em
# Base.metadata. A importação da instância FastAPI vem depois: fazer
# `import app.models.domain` após `from app.main import app` religa o nome
# `app` ao pacote e sombreia a aplicação.
from app.models.domain import Organization, User, UserRole  # noqa: E402
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app

TEST_PASSWORD = "senha-de-teste-123"


@pytest.fixture
def db_session():
    # StaticPool mantém uma única conexão para o banco em memória, de modo que
    # o TestClient — que atende as requisições em outra thread — enxergue as
    # mesmas tabelas.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_org(db_session, name="Organização de Teste"):
    org = Organization(name=name)
    db_session.add(org)
    db_session.commit()
    return org


#: Papéis que, em produção, precisam de segundo fator para exercer as
#: permissões `org:manage` e `catalog:validate` (§8.1, D2). As fixturas os
#: criam já com o fator ativo, porque é o estado real de quem publica regra ou
#: gere a organização — um validador sem MFA não consegue trabalhar, e testar
#: com ele mediria a exceção em vez da regra.
#:
#: Para exercitar o cadastro do fator, use `usuario_sem_mfa`.
MFA_ROLES = {UserRole.OWNER, UserRole.ADMIN, UserRole.VALIDATOR}


#: Segredos em claro dos usuários de teste, por e-mail. Existe para que
#: `auth_headers` gere o código no login sem que cada teste precise saber que o
#: usuário tem segundo fator.
_MFA_SECRETS: dict = {}


def activate_mfa(db_session, user):
    """Liga o segundo fator direto no banco, como se já tivesse sido cadastrado."""
    from app.core import mfa

    secret = mfa.generate_secret()
    user.mfa_secret = mfa.encrypt_secret(secret)
    user.mfa_activated_at = datetime.utcnow()
    db_session.commit()
    _MFA_SECRETS[user.email] = secret
    return user


def make_user(db_session, org, role=UserRole.ENGINEER, email=None, with_mfa=None):
    email = email or f"{role}-{org.id[:8]}@atlas-qa.com"
    user = User(
        organization_id=org.id,
        name=f"Usuário {role}",
        email=email,
        role=role,
        password_hash=hash_password(TEST_PASSWORD),
    )
    db_session.add(user)
    db_session.commit()

    if with_mfa if with_mfa is not None else role in MFA_ROLES:
        activate_mfa(db_session, user)
    return user


def auth_headers(client, email):
    """Autentica, acrescentando o segundo fator quando o usuário o tem.

    Chamadores não precisam saber se o papel exige MFA: a fixture que ativou o
    fator guardou o segredo em `_MFA_SECRETS`, e o código sai daí.
    """
    corpo = {"email": email, "password": TEST_PASSWORD}

    secret = _MFA_SECRETS.get(email)
    if secret:
        import pyotp

        corpo["mfa_code"] = pyotp.TOTP(secret).now()

    response = client.post("/api/v1/auth/login", json=corpo)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def org(db_session):
    return make_org(db_session)


@pytest.fixture
def engineer(db_session, org):
    return make_user(db_session, org, UserRole.ENGINEER)


@pytest.fixture
def engineer_headers(client, engineer):
    return auth_headers(client, engineer.email)


@pytest.fixture
def validator(db_session, org):
    """Validador como em produção: com segundo fator ativo."""
    return make_user(db_session, org, UserRole.VALIDATOR)


@pytest.fixture
def usuario_sem_mfa(db_session, org):
    """Validador **sem** o fator, para exercitar o cadastro (§8.1, D2)."""
    return make_user(
        db_session, org, UserRole.VALIDATOR, email="sem-mfa@atlas-qa.com", with_mfa=False
    )


@pytest.fixture
def headers_sem_mfa(client, usuario_sem_mfa):
    return auth_headers(client, usuario_sem_mfa.email)


@pytest.fixture
def validator_headers(client, validator):
    return auth_headers(client, validator.email)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Aponta o storage local para um diretório descartável (§6.6).

    O backend é memorizado por `lru_cache`, então trocar a configuração exige
    limpar o cache — antes, para o teste enxergar o diretório novo, e depois,
    para não vazar o diretório temporário para o teste seguinte.
    """
    from app.core.config import settings
    from app.services import storage as storage_module

    directory = tmp_path / "uploads"
    directory.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(directory))
    storage_module.reset_storage_cache()
    yield directory
    storage_module.reset_storage_cache()


@pytest.fixture
def seeded_catalog(db_session):
    from app.regulatory.importer import import_seed_catalog

    import_seed_catalog(db_session)
    return db_session


@pytest.fixture
def project(client, engineer_headers, seeded_catalog):
    response = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={
            "name": "Residencial de Teste",
            "zone": "Z2",
            "building_type": "residencial_unifamiliar",
            "lot_area": 450.0,
            "built_area": 240.0,
            "floors": 2,
            "front_setback": 4.5,
            "rear_setback": 3.5,
            "permeability_rate": 22.0,
            "parking_spaces": 2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
