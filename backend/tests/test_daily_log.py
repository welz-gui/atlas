from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.database import Base
from app.models.domain import Organization, Project, DailyLog

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

def test_daily_log_creation_and_query(db_session):
    org = Organization(name="Org Test Log")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Projeto Teste Diário",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar"
    )
    db_session.add(project)
    db_session.commit()

    log = DailyLog(
        project_id=project.id,
        date="2026-08-06",
        weather_condition="ensolarado",
        manpower_own=5,
        manpower_subcontracted=10,
        activities_done="Concretagem de laje do 1º pavimento.",
        occurrences="Nenhuma.",
        status="assinado"
    )
    db_session.add(log)
    db_session.commit()

    fetched = db_session.query(DailyLog).filter(DailyLog.id == log.id).first()
    assert fetched is not None
    assert fetched.weather_condition == "ensolarado"
    assert fetched.manpower_own == 5
    assert fetched.manpower_subcontracted == 10
