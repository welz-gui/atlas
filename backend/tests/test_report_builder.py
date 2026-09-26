from datetime import datetime
from unittest.mock import patch

from app.models.domain import AnalysisRun, Project, ProjectVersion, ValidationRecord
from app.services.report_builder import (
    build_report,
    project_payload,
    report_filename,
    run_payload,
    validation_payload,
)


def test_project_payload_uses_run_version_if_available():
    project = Project(
        id="proj-1",
        name="Project Name",
        city_name="City",
        state="ST",
        versions=[
            ProjectVersion(version_number=0, zone="Zone C")
        ]
    )

    run_version = ProjectVersion(
        zone="Zone R",
        lot_area=100.0,
        built_area=50.0,
        floors=2,
        front_setback=5.0,
        rear_setback=3.0,
        permeability_rate=20.0,
        is_official_baseline=True,
        version_number=1,
        state="aprovada",
    )

    run = AnalysisRun()
    run.project_version = run_version

    payload = project_payload(project, run)

    assert payload["id"] == "proj-1"
    assert payload["name"] == "Project Name"
    assert payload["city_name"] == "City"
    assert payload["state"] == "ST"
    assert payload["zone"] == "Zone R"
    assert payload["lot_area"] == 100.0
    assert payload["built_area"] == 50.0
    assert payload["floors"] == 2
    assert payload["front_setback"] == 5.0
    assert payload["rear_setback"] == 3.0
    assert payload["occupancy_rate"] == 50.0
    assert payload["permeability_rate"] == 20.0
    assert payload["is_official_baseline"] is True
    assert payload["version_number"] == 1
    assert payload["version_state"] == "aprovada"


def test_project_payload_fallback_to_current_version_when_no_run_version():
    project = Project(
        id="proj-1",
        name="Project Name",
        city_name="City",
        state="ST",
        versions=[
            ProjectVersion(
                zone="Zone C",
                lot_area=200.0,
                built_area=80.0,
                floors=1,
                front_setback=2.0,
                rear_setback=1.0,
                permeability_rate=30.0,
                is_official_baseline=False,
                version_number=2,
                state="revisao_interna",
            )
        ]
    )

    run = AnalysisRun()
    run.project_version = None

    payload = project_payload(project, run)

    assert payload["zone"] == "Zone C"
    assert payload["lot_area"] == 200.0
    assert payload["built_area"] == 80.0
    assert payload["floors"] == 1
    assert payload["front_setback"] == 2.0
    assert payload["rear_setback"] == 1.0
    assert payload["occupancy_rate"] == 40.0
    assert payload["permeability_rate"] == 30.0
    assert payload["is_official_baseline"] is False
    assert payload["version_number"] == 2
    assert payload["version_state"] == "revisao_interna"


def test_project_payload_no_version_available():
    project = Project(
        id="proj-1",
        name="Project Name",
        city_name="City",
        state="ST",
        versions=[]
    )

    run = AnalysisRun()
    run.project_version = None

    payload = project_payload(project, run)

    assert payload["zone"] == "—"
    assert payload["lot_area"] is None
    assert payload["built_area"] is None
    assert payload["floors"] is None
    assert payload["front_setback"] is None
    assert payload["rear_setback"] is None
    assert payload["occupancy_rate"] is None
    assert payload["permeability_rate"] is None
    assert payload["is_official_baseline"] is False
    assert payload["version_number"] is None
    assert payload["version_state"] is None


def test_validation_payload():
    run = AnalysisRun()
    run.validations = [
        ValidationRecord(
            rule_title="Rule 1",
            expected_value="A",
            actual_value="B",
            status="fail",
            details="Failed test",
            source_citation="Doc 1",
            source_is_verified=True,
            evidence_required=False,
        ),
        ValidationRecord(
            rule_title="Rule 2",
            expected_value="C",
            actual_value="C",
            status="pass",
            details="Passed test",
            source_citation="Doc 2",
            source_is_verified=False,
            evidence_required=True,
        ),
    ]

    payload = validation_payload(run)

    assert len(payload) == 2
    assert payload[0] == {
        "rule_title": "Rule 1",
        "expected_value": "A",
        "actual_value": "B",
        "status": "fail",
        "details": "Failed test",
        "source_citation": "Doc 1",
        "source_is_verified": True,
        "evidence_required": False,
    }
    assert payload[1] == {
        "rule_title": "Rule 2",
        "expected_value": "C",
        "actual_value": "C",
        "status": "pass",
        "details": "Passed test",
        "source_citation": "Doc 2",
        "source_is_verified": False,
        "evidence_required": True,
    }


def test_run_payload():
    now = datetime.utcnow()
    run = AnalysisRun(
        id="run-1",
        content_hash="hash123",
        catalog_version="cat-v1",
        engine_version="eng-v1",
        is_publishable=True,
        created_at=now,
    )

    payload = run_payload(run)

    assert payload == {
        "id": "run-1",
        "content_hash": "hash123",
        "catalog_version": "cat-v1",
        "engine_version": "eng-v1",
        "is_publishable": True,
        "created_at": now,
    }


def test_report_filename_publishable():
    project = Project(name="My Project!")
    run = AnalysisRun(is_publishable=True)

    filename = report_filename(project, run)

    assert filename == "Pre_Analise_My_Project_.pdf"


def test_report_filename_not_publishable():
    project = Project(name="A" * 70)
    run = AnalysisRun(is_publishable=False)

    filename = report_filename(project, run)

    assert filename == f"USO_INTERNO_Pre_Analise_{'A' * 60}.pdf"


def test_report_filename_empty_name_or_all_unsafe_chars():
    project = Project(name="$$$")
    run = AnalysisRun(is_publishable=True)

    filename = report_filename(project, run)
    assert filename == "Pre_Analise____.pdf"

def test_report_filename_empty_string():
    project = Project(name="")
    run = AnalysisRun(is_publishable=True)

    filename = report_filename(project, run)

    assert filename == "Pre_Analise_empreendimento.pdf"


@patch("app.services.report_builder.pdf_report_generator")
def test_build_report(mock_generator):
    mock_generator.generate_pdf.return_value = b"fake-pdf-content"

    project = Project(id="proj-1", name="Proj 1", versions=[])

    run = AnalysisRun(
        id="run-1",
        is_publishable=True,
        content_hash="hash",
        catalog_version="v1",
        engine_version="e1",
        created_at=datetime.utcnow(),
    )
    run.validations = []

    pdf_bytes, filename, sha256 = build_report(project, run)

    assert pdf_bytes == b"fake-pdf-content"
    assert filename == "Pre_Analise_Proj_1.pdf"
    import hashlib

    assert sha256 == hashlib.sha256(b"fake-pdf-content").hexdigest()

    mock_generator.generate_pdf.assert_called_once()
