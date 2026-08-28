"""Versionamento de projeto e linha de base oficial (§3.2, §14.15)."""

from app.models.domain import ProjectVersion, ProjectVersionState


def _versions(client, headers, project_id):
    response = client.get(f"/api/v1/projects/{project_id}/versions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_cadastro_cria_versao_1(client, engineer_headers, project):
    versions = _versions(client, engineer_headers, project["id"])

    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["state"] == ProjectVersionState.ESTUDO_PRELIMINAR
    assert versions[0]["front_setback"] == 4.5
    assert project["current_version"]["version_number"] == 1


def test_alterar_parametro_cria_versao_nova_sem_tocar_na_anterior(
    client, engineer_headers, project
):
    """§14.15 — nenhuma alteração silenciosa."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=engineer_headers,
        json={"front_setback": 2.0, "change_reason": "Ajuste solicitado pelo cliente."},
    )
    assert response.status_code == 201, response.text

    versions = _versions(client, engineer_headers, project["id"])
    assert len(versions) == 2

    nova, original = versions[0], versions[1]
    assert nova["version_number"] == 2
    assert nova["front_setback"] == 2.0
    assert nova["change_reason"] == "Ajuste solicitado pelo cliente."

    # A versão 1 permanece exatamente como estava.
    assert original["version_number"] == 1
    assert original["front_setback"] == 4.5


def test_versao_nova_herda_o_que_nao_mudou(client, engineer_headers, project):
    client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=engineer_headers,
        json={"front_setback": 6.0},
    )
    nova = _versions(client, engineer_headers, project["id"])[0]

    assert nova["front_setback"] == 6.0
    assert nova["built_area"] == 240.0   # herdado
    assert nova["rear_setback"] == 3.5   # herdado
    assert nova["parking_spaces"] == 2   # herdado


def test_patch_no_projeto_nao_altera_parametros_urbanisticos(
    client, engineer_headers, project
):
    """Parâmetros pertencem à versão; o PATCH de identidade não os alcança."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=engineer_headers,
        json={"name": "Nome novo", "front_setback": 0.5},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nome novo"
    assert response.json()["current_version"]["front_setback"] == 4.5
    assert len(_versions(client, engineer_headers, project["id"])) == 1


def test_analise_registra_a_versao_avaliada(client, engineer_headers, project):
    client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=engineer_headers,
        json={"front_setback": 2.0},
    )
    runs = client.get(
        f"/api/v1/projects/{project['id']}/analysis-runs", headers=engineer_headers
    ).json()

    assert {run["project_version_number"] for run in runs} == {1, 2}
    mais_recente = runs[0]
    assert mais_recente["project_version_number"] == 2


def test_linha_de_base_exige_versao_aprovada(client, engineer_headers, project):
    version_id = project["current_version"]["id"]

    recusa = client.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/baseline",
        headers=engineer_headers,
    )
    assert recusa.status_code == 409
    assert "aprovada" in recusa.json()["detail"]

    client.patch(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/state",
        headers=engineer_headers,
        json={"state": ProjectVersionState.APROVADA},
    )
    aceita = client.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/baseline",
        headers=engineer_headers,
    )
    assert aceita.status_code == 200
    assert aceita.json()["is_official_baseline"] is True
    assert aceita.json()["baseline_marked_at"] is not None


def test_linha_de_base_e_exclusiva(client, engineer_headers, project):
    """Promover uma versão desmarca a anterior — só há uma linha de base."""
    v1 = project["current_version"]["id"]
    for version_id in (v1,):
        client.patch(
            f"/api/v1/projects/{project['id']}/versions/{version_id}/state",
            headers=engineer_headers,
            json={"state": ProjectVersionState.APROVADA},
        )
        client.post(
            f"/api/v1/projects/{project['id']}/versions/{version_id}/baseline",
            headers=engineer_headers,
        )

    nova = client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=engineer_headers,
        json={"built_area": 250.0, "state": ProjectVersionState.APROVADA},
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/versions/{nova['id']}/baseline",
        headers=engineer_headers,
    )

    versions = _versions(client, engineer_headers, project["id"])
    marcadas = [v for v in versions if v["is_official_baseline"]]
    assert len(marcadas) == 1
    assert marcadas[0]["version_number"] == 2


def test_estado_invalido_e_recusado(client, engineer_headers, project):
    response = client.patch(
        f"/api/v1/projects/{project['id']}/versions/{project['current_version']['id']}/state",
        headers=engineer_headers,
        json={"state": "estado_inventado"},
    )
    assert response.status_code == 422


def test_hash_da_versao_muda_com_os_parametros(client, engineer_headers, project, db_session):
    client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=engineer_headers,
        json={"front_setback": 2.0},
    )
    hashes = [
        v.content_hash
        for v in db_session.query(ProjectVersion)
        .filter(ProjectVersion.project_id == project["id"])
        .order_by(ProjectVersion.version_number)
        .all()
    ]
    assert len(hashes) == 2
    assert all(len(h) == 64 for h in hashes)
    assert hashes[0] != hashes[1]


def test_taxa_de_ocupacao_e_derivada_da_versao(client, engineer_headers, project):
    # 240 / 450 = 53,3%
    assert project["current_version"]["occupancy_rate"] == 53.3

    nova = client.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers=engineer_headers,
        json={"built_area": 300.0},
    ).json()
    assert nova["occupancy_rate"] == 66.7


def test_mark_official_baseline_value_error(client, engineer_headers, project, monkeypatch):
    version_id = project["current_version"]["id"]
    client.patch(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/state",
        headers=engineer_headers,
        json={"state": "aprovada"},
    )

    def mock_set_official_baseline(*args, **kwargs):
        raise ValueError("Simulated error")

    monkeypatch.setattr("app.api.v1.endpoints.projects.project_versions.set_official_baseline", mock_set_official_baseline)

    response = client.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/baseline",
        headers=engineer_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Simulated error"
