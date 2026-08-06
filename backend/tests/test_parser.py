from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.database import Base
from app.models.domain import Organization, Project, Document
from app.services.pdf_parser import PDFPlanParser

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

def test_pdf_parser_text_extraction():
    sample_text = """
    MEMORIAL DESCRITIVO E QUADRO DE ÁREAS
    Projeto Arquitetônico Unifamiliar
    Área do Terreno: 450,00 m²
    Área Construída: 240,00 m²
    Recuo Frontal: 4,50 m
    Recuo Fundos: 3,50 m
    Taxa de Permeabilidade: 20,0 %
    Nº de Pavimentos: 2
    """
    res = PDFPlanParser.parse_text_content(sample_text)
    assert res["lot_area"] == 450.0
    assert res["built_area"] == 240.0
    assert res["front_setback"] == 4.50
    assert res["rear_setback"] == 3.50
    assert res["permeability_rate"] == 20.0
    assert res["floors"] == 2
    assert res["confidence_score"] > 70.0
