from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.database import Base
from app.models.domain import Organization, Project
from app.services.pdf_report_generator import RegulatoryReportGenerator
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

def test_pdf_report_generation(db_session):
    org = Organization(name="Org Test Report")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Projeto Teste PDF",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=450.0,
        built_area=240.0,
        front_setback=4.50,
        rear_setback=3.50,
        occupancy_rate=53.3,
        permeability_rate=22.0
    )
    db_session.add(project)
    db_session.commit()

    records = RegulatoryEngine.evaluate_project(db_session, project)
    
    project_dict = {
        "id": project.id,
        "name": project.name,
        "city_name": project.city_name,
        "zone": project.zone,
        "lot_area": project.lot_area,
        "built_area": project.built_area,
        "front_setback": project.front_setback,
        "rear_setback": project.rear_setback,
        "occupancy_rate": project.occupancy_rate,
        "permeability_rate": project.permeability_rate
    }
    
    validations_list = [
        {
            "rule_title": r.rule_title,
            "expected_value": r.expected_value,
            "actual_value": r.actual_value,
            "status": r.status,
            "source_citation": r.source_citation
        }
        for r in records
    ]

    pdf_bytes = RegulatoryReportGenerator.generate_pdf(project_dict, validations_list)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
