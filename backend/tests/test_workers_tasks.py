import pytest
from app.workers.tasks import run_analysis
from app.models.domain import JobRecord, JobType, Project, ProjectVersion
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

    run_analysis(db_session, record)

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

def test_generate_report_missing_project_id(org):
    from app.workers.tasks import generate_report
    record = JobRecord(
        job_type=JobType.GERACAO_LAUDO,
        payload={},
        organization_id=org.id
    )
    with pytest.raises(ValueError, match="payload.project_id é obrigatório."):
        generate_report(None, record)

def test_generate_report_project_not_found(db_session, org):
    from app.workers.tasks import generate_report
    record = JobRecord(
        job_type=JobType.GERACAO_LAUDO,
        payload={"project_id": "non_existent"},
        organization_id=org.id
    )
    with pytest.raises(LookupError, match="Empreendimento 'non_existent' não encontrado na organização do trabalho."):
        generate_report(db_session, record)

def test_generate_report_run_not_found(db_session, project, org):
    from app.workers.tasks import generate_report
    record = JobRecord(
        job_type=JobType.GERACAO_LAUDO,
        payload={
            "project_id": project["id"],
            "analysis_run_id": "non_existent_run"
        },
        organization_id=org.id
    )
    with pytest.raises(LookupError, match="Análise 'non_existent_run' não pertence a este empreendimento."):
        generate_report(db_session, record)

def test_generate_report_no_run_found(db_session, project, org):
    from app.workers.tasks import generate_report
    from app.models.domain import AnalysisRun

    # O cadastro do empreendimento já dispara uma avaliação (via endpoint),
    # então o cenário precisa ser montado removendo as análises.
    db_session.query(AnalysisRun).filter(
        AnalysisRun.project_id == project["id"]
    ).delete()
    db_session.commit()

    record = JobRecord(
        job_type=JobType.GERACAO_LAUDO,
        payload={"project_id": project["id"]},
        organization_id=org.id
    )
    with pytest.raises(ValueError, match="Nenhuma análise registrada para este empreendimento; não há o que emitir."):
        generate_report(db_session, record)

def test_generate_report_success(db_session, project, org, monkeypatch):
    from app.workers.tasks import generate_report
    from app.models.domain import AnalysisRun

    # Criar um run manual no banco
    run = AnalysisRun(
        id="run_123",
        project_id=project["id"],
        organization_id=org.id,
        project_version_number=1,
        trigger="manual",
        total_checks=10,
        nao_conforme_count=2,
        nao_verificavel_count=1,
        is_publishable=False,
        content_hash="hash_conteudo",
        jurisdiction="jurisdicao",
        catalog_version="1",
        engine_version="1",
        conforme_count=7,
        atencao_count=0
    )
    db_session.add(run)
    db_session.commit()

    record = JobRecord(
        job_type=JobType.GERACAO_LAUDO,
        payload={"project_id": project["id"]},
        organization_id=org.id
    )

    from unittest.mock import MagicMock

    mock_build_report = MagicMock(return_value=(b"pdf_content", "relatorio.pdf", "hash_pdf"))
    monkeypatch.setattr("app.services.report_builder.build_report", mock_build_report)

    mock_build_key = MagicMock(return_value="path/to/relatorio.pdf")
    monkeypatch.setattr("app.services.storage.build_key", mock_build_key)

    mock_writer = MagicMock()
    mock_writer.result.key = "path/to/relatorio.pdf"
    mock_writer.result.backend = "s3"
    mock_writer.result.size_bytes = 1024

    mock_writer_context = MagicMock()
    mock_writer_context.__enter__.return_value = mock_writer

    mock_storage = MagicMock()
    mock_storage.writer.return_value = mock_writer_context

    monkeypatch.setattr("app.workers.tasks.get_storage", MagicMock(return_value=mock_storage))

    result = generate_report(db_session, record)

    assert result == {
        "analysis_run_id": "run_123",
        "storage_key": "path/to/relatorio.pdf",
        "storage_backend": "s3",
        "filename": "relatorio.pdf",
        "size_bytes": 1024,
        "sha256": "hash_pdf",
        "is_publishable": False,
    }

    mock_build_report.assert_called_once()
    mock_build_key.assert_called_once_with(".pdf")
    mock_storage.writer.assert_called_once_with("path/to/relatorio.pdf")
    mock_writer.write.assert_called_once_with(b"pdf_content")
