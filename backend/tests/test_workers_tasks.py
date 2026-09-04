import pytest
from app.workers.tasks import run_analysis
from app.models.domain import JobRecord, JobType, Project, ProjectVersion, User
from app.services.regulatory_engine import RegulatoryEngine
from unittest.mock import MagicMock

def test_run_analysis_no_project_id():
    record = JobRecord(
        job_type=JobType.ANALISE_REGULATORIA,
        payload={},
        organization_id="org_id"
    )
    with pytest.raises(ValueError, match="payload.project_id é obrigatório."):
        run_analysis(None, record)

def test_run_analysis_success(db_session, monkeypatch, project):
    mock_run = MagicMock()
    mock_run.id = "run_123"
    mock_run.project_version_number = 1
    mock_run.total_checks = 10
    mock_run.nao_conforme_count = 2
    mock_run.nao_verificavel_count = 1
    mock_run.is_publishable = False
    mock_run.content_hash = "hash123"

    mock_eval = MagicMock(return_value=mock_run)
    monkeypatch.setattr(RegulatoryEngine, "evaluate_project", mock_eval)

    project_db = db_session.query(Project).filter(Project.id == project["id"]).first()

    record = JobRecord(
        job_type=JobType.ANALISE_REGULATORIA,
        payload={"project_id": project["id"]},
        organization_id=project_db.organization_id
    )

    result = run_analysis(db_session, record)

    assert result == {
        "analysis_run_id": "run_123",
        "project_version_number": 1,
        "total_checks": 10,
        "nao_conforme_count": 2,
        "nao_verificavel_count": 1,
        "is_publishable": False,
        "content_hash": "hash123",
    }
    mock_eval.assert_called_once_with(
        db_session,
        project_db,
        trigger="assincrono",
        user=None,
        version=None
    )

def test_run_analysis_with_version_and_user(db_session, monkeypatch, project, engineer):
    mock_run = MagicMock()
    mock_run.id = "run_123"
    mock_run.project_version_number = 2
    mock_run.total_checks = 10
    mock_run.nao_conforme_count = 2
    mock_run.nao_verificavel_count = 1
    mock_run.is_publishable = False
    mock_run.content_hash = "hash123"

    mock_eval = MagicMock(return_value=mock_run)
    monkeypatch.setattr(RegulatoryEngine, "evaluate_project", mock_eval)

    project_db = db_session.query(Project).filter(Project.id == project["id"]).first()

    version = ProjectVersion(project_id=project_db.id, organization_id=project_db.organization_id, version_number=2)
    db_session.add(version)
    db_session.commit()

    record = JobRecord(
        job_type=JobType.ANALISE_REGULATORIA,
        payload={
            "project_id": project["id"],
            "project_version_id": version.id,
            "trigger": "sync"
        },
        organization_id=project_db.organization_id,
        requested_by_id=engineer.id
    )

    result = run_analysis(db_session, record)

    mock_eval.assert_called_once_with(
        db_session,
        project_db,
        trigger="sync",
        user=engineer,
        version=version
    )

def test_run_analysis_invalid_version(db_session, project):
    project_db = db_session.query(Project).filter(Project.id == project["id"]).first()

    record = JobRecord(
        job_type=JobType.ANALISE_REGULATORIA,
        payload={
            "project_id": project["id"],
            "project_version_id": "invalid_id"
        },
        organization_id=project_db.organization_id
    )

    with pytest.raises(LookupError, match="Versão 'invalid_id' não pertence a este projeto."):
        run_analysis(db_session, record)
