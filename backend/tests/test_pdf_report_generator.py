from app.services.pdf_report_generator import RegulatoryReportGenerator
from unittest.mock import patch

def test_fmt_none():
    assert RegulatoryReportGenerator._fmt(None) == "não informado"

def test_fmt_float_percentage():
    assert RegulatoryReportGenerator._fmt(0.1234, unit="%", decimals=1) == "0.1%"

def test_fmt_float_no_percentage():
    assert RegulatoryReportGenerator._fmt(10.5, unit="m", decimals=2) == "10.50 m"

def test_fmt_integer():
    assert RegulatoryReportGenerator._fmt(10, unit="m") == "10 m"

@patch("app.services.pdf_report_generator.SimpleDocTemplate")
def test_generate_pdf(mock_doc_template):
    mock_doc_instance = mock_doc_template.return_value
    mock_doc_instance.build.return_value = None

    project_data = {
        "name": "Test Project",
        "city_name": "Test City",
        "state": "TS",
        "zone": "Z1",
        "lot_area": 1000.0,
        "built_area": 500.0,
        "front_setback": 5.0,
        "rear_setback": 5.0,
        "occupancy_rate": 50.0,
        "permeability_rate": 20.0,
        "floors": 2,
        "is_official_baseline": True,
        "version_number": 1,
        "version_state": "draft",
    }
    validations = [
        {
            "status": "conforme",
            "rule_title": "Rule 1",
            "expected_value": "1",
            "actual_value": "1",
            "source_citation": "Lei 1",
            "source_is_verified": True,
        },
        {
            "status": "nao_verificavel",
            "rule_title": "Rule 2",
            "expected_value": "2",
            "actual_value": "2",
            "details": "Detail",
            "evidence_required": "Evidence",
        }
    ]
    run_data = {
        "id": "run-123",
        "content_hash": "hash123",
        "catalog_version": "v1",
        "engine_version": "v1",
        "is_publishable": False,
    }
    pdf_bytes = RegulatoryReportGenerator.generate_pdf(project_data, validations, run_data)
    assert isinstance(pdf_bytes, bytes)
    mock_doc_instance.build.assert_called_once()
