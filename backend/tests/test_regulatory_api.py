"""API regulatória: GET é somente leitura, histórico é preservado."""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.domain import AnalysisRun, Organization, Project


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def project(db_session):
    org = Organization(name="Org API")
    db_session.add(org)
    db_session.commit()
    project = Project(
        organization_id=org.id,
        name="Residencial API",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=450.0,
        built_area=240.0,
        floors=2,
        front_setback=4.5,
        rear_setback=3.5,
        permeability_rate=22.0,
        parking_spaces=2,
    )
    db_session.add(project)
    db_session.commit()
    return project


def test_laudo_sem_analise_previa_retorna_409(client, project):
    """O GET não pode disparar avaliação; sem análise, ele recusa."""
    response = client.get(f"/api/v1/projects/{project.id}/report/pdf")
    assert response.status_code == 409
    assert "evaluate" in response.json()["detail"]


def test_get_do_laudo_nao_cria_analise(client, project, db_session):
    """Regressão: no protótipo, o GET do PDF reavaliava e apagava o histórico."""
    client.post(f"/api/v1/projects/{project.id}/evaluate")
    antes = db_session.query(AnalysisRun).filter_by(project_id=project.id).count()

    for _ in range(3):
        response = client.get(f"/api/v1/projects/{project.id}/report/pdf")
        assert response.status_code == 200

    depois = db_session.query(AnalysisRun).filter_by(project_id=project.id).count()
    assert antes == depois == 1


def test_laudo_sinaliza_uso_interno_no_cabecalho(client, project):
    client.post(f"/api/v1/projects/{project.id}/evaluate")
    response = client.get(f"/api/v1/projects/{project.id}/report/pdf")

    assert response.headers["X-Atlas-Publishable"] == "false"
    assert "USO_INTERNO_" in response.headers["content-disposition"]
    assert len(response.headers["X-Atlas-Content-Hash"]) == 64
    assert len(response.headers["X-Atlas-Pdf-Sha256"]) == 64
    assert response.content.startswith(b"%PDF")


def test_historico_de_analises_e_acumulativo(client, project):
    client.post(f"/api/v1/projects/{project.id}/evaluate")
    client.patch(f"/api/v1/projects/{project.id}", json={"front_setback": 2.0})
    client.post(f"/api/v1/projects/{project.id}/evaluate")

    runs = client.get(f"/api/v1/projects/{project.id}/analysis-runs").json()
    assert len(runs) == 3
    assert {r["trigger"] for r in runs} == {"manual", "project_updated"}

    # É possível reemitir o laudo de uma análise antiga.
    antiga = runs[-1]["id"]
    response = client.get(
        f"/api/v1/projects/{project.id}/report/pdf", params={"run_id": antiga}
    )
    assert response.status_code == 200
    assert response.headers["X-Atlas-Analysis-Run"] == antiga


def test_validations_retorna_apenas_a_analise_mais_recente(client, project):
    client.post(f"/api/v1/projects/{project.id}/evaluate")
    client.post(f"/api/v1/projects/{project.id}/evaluate")

    validations = client.get(f"/api/v1/projects/{project.id}/validations").json()
    run_ids = {v["analysis_run_id"] for v in validations}
    assert len(run_ids) == 1


def test_taxa_de_ocupacao_e_somente_leitura(client, project):
    """A taxa é derivada; enviá-la no PATCH não pode sobrescrever nada."""
    response = client.patch(
        f"/api/v1/projects/{project.id}", json={"occupancy_rate": 12.0}
    )
    assert response.status_code == 200
    # 240 / 450 = 53,3%
    assert response.json()["occupancy_rate"] == 53.3
