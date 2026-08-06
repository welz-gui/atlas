from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.database import Base
from app.models.domain import Organization, Project
from app.api.v1.endpoints.ai import atlas_ai_chat, AIChatRequest

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_atlas_ai_chat_response(db_session):
    org = Organization(name="Org Test AI")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Residencial Teste AI",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
        built_area=240.0,
        lot_area=400.0
    )
    db_session.add(project)
    db_session.commit()

    req = AIChatRequest(
        prompt="Quais são as regras de recuo frontal e taxa de ocupação em Lajeado?",
        project_id=project.id
    )

    response = atlas_ai_chat(req, db_session)
    assert response is not None
    assert "Lajeado" in response.answer
    assert len(response.law_citations) >= 2
    assert len(response.suggested_actions) >= 1
