import pytest

from app.models.domain import Project

def test_evaluate_project_rules_success(client, engineer_headers, seeded_catalog):
    # Create project
    payload = {
        "name": "Projeto Sucesso",
        "zone": "Z2",
        "building_type": "residencial_unifamiliar",
        "lot_area": 450.0,
        "built_area": 240.0,
        "floors": 2,
        "front_setback": 4.50,
        "side_setback": 1.80,
        "rear_setback": 3.50,
        "permeability_rate": 22.5,
        "parking_spaces": 2,
    }
    response = client.post("/api/v1/projects", headers=engineer_headers, json=payload)
    assert response.status_code == 201
    projeto = response.json()

    # Evaluate
    response = client.post(f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers)
    assert response.status_code == 200
    report = response.json()
    assert report["project_id"] == projeto["id"]
    assert report["total_checks"] > 0
    assert "analysis_run_id" in report
    assert "project_version_number" in report
    assert "catalog_version" in report
    assert "engine_version" in report
    assert "conforme_count" in report
    assert "nao_conforme_count" in report
    assert "atencao_count" in report
    assert "nao_verificavel_count" in report
    assert "is_publishable" in report
    assert "content_hash" in report
    assert "results" in report

def test_evaluate_project_rules_no_version(client, engineer_headers, db_session, seeded_catalog):
    # Create project
    payload = {
        "name": "Projeto Sem Versao",
        "zone": "Z2",
        "building_type": "residencial_unifamiliar",
        "lot_area": 450.0,
        "built_area": 240.0,
        "floors": 2,
        "front_setback": 4.50,
        "side_setback": 1.80,
        "rear_setback": 3.50,
        "permeability_rate": 22.5,
        "parking_spaces": 2,
    }
    response = client.post("/api/v1/projects", headers=engineer_headers, json=payload)
    assert response.status_code == 201
    projeto = response.json()

    # Remove all versions from the project so it fails with ValueError in RegulatoryEngine
    project = db_session.get(Project, projeto["id"])
    for version in project.versions:
        db_session.delete(version)
    db_session.commit()

    # Evaluate
    response = client.post(f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "O empreendimento não possui nenhuma versão de projeto para analisar."
