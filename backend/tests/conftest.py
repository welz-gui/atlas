import os
import sys

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


def make_user(db_session, org, role=UserRole.ENGINEER, email=None):
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
    return user


def auth_headers(client, email):
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
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
    return make_user(db_session, org, UserRole.VALIDATOR)


@pytest.fixture
def validator_headers(client, validator):
    return auth_headers(client, validator.email)


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
