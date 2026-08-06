from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.database import Base
from app.models.domain import Organization, Project
from app.services.regulatory_engine import RegulatoryEngine

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

def test_regulatory_engine_conforming_project(db_session):
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Projeto Teste Conforme",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=450.0,
        built_area=240.0, # 53.3% (< 60%)
        floors=2, # <= 3
        front_setback=4.50, # >= 4.0m
        side_setback=1.80
    )
    db_session.add(project)
    db_session.commit()

    records = RegulatoryEngine.evaluate_project(db_session, project)
    
    status_map = {r.rule_id: r.status for r in records}
    assert status_map["lajeado_recuo_frontal_z2"] == "conforme"
    assert status_map["lajeado_taxa_ocupacao_max_z2"] == "conforme"
    assert status_map["lajeado_gabarito_maximo_z2"] == "conforme"
    assert status_map["lajeado_acessibilidade_nbr9050"] == "nao_verificavel"

def test_regulatory_engine_non_conforming_project(db_session):
    org = Organization(name="Test Org 2")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Projeto Teste Inconforme",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=300.0,
        built_area=210.0, # 70% (> 60% Max)
        floors=2,
        front_setback=3.00, # < 4.0m Min
        side_setback=1.00
    )
    db_session.add(project)
    db_session.commit()

    records = RegulatoryEngine.evaluate_project(db_session, project)
    
    status_map = {r.rule_id: r.status for r in records}
    assert status_map["lajeado_recuo_frontal_z2"] == "nao_conforme"
    assert status_map["lajeado_taxa_ocupacao_max_z2"] == "nao_conforme"
