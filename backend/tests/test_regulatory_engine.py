import uuid
"""Motor de regras: aplicabilidade, veredictos e append-only (§3.4, §3.5)."""


from app.models.domain import AnalysisRun, ValidationRecord
from app.regulatory.catalog import CheckOutcome

PARAMS_CONFORMES = {
    "zone": "Z2",
    "building_type": "residencial_unifamiliar",
    "lot_area": 450.0,
    "built_area": 240.0,     # 53,3% < 60%
    "floors": 2,             # <= 3
    "front_setback": 4.50,   # >= 4,00
    "side_setback": 1.80,
    "rear_setback": 3.50,    # >= 3,00
    "permeability_rate": 22.5,
    "parking_spaces": 2,
}


def _criar_projeto(client, headers, nome="Projeto", **overrides):
    payload = {"name": nome, **PARAMS_CONFORMES, **overrides}
    response = client.post("/api/v1/projects", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _status_map(client, headers, project_id):
    validations = client.get(
        f"/api/v1/projects/{project_id}/validations", headers=headers
    ).json()
    return {v["rule_id"]: v["status"] for v in validations}


def test_projeto_conforme(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Conforme")
    status = _status_map(client, engineer_headers, projeto["id"])

    assert status["lajeado_recuo_frontal_z2"] == CheckOutcome.CONFORME
    assert status["lajeado_taxa_ocupacao_max_z2"] == CheckOutcome.CONFORME
    assert status["lajeado_recuo_fundos_z2"] == CheckOutcome.CONFORME
    assert status["lajeado_gabarito_maximo_z2"] == CheckOutcome.CONFORME
    assert status["brasil_acessibilidade_edificacoes"] == CheckOutcome.NAO_VERIFICAVEL


def test_projeto_nao_conforme(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(
        client, engineer_headers, "Inconforme",
        lot_area=300.0, built_area=210.0, front_setback=3.00,
    )
    status = _status_map(client, engineer_headers, projeto["id"])

    assert status["lajeado_recuo_frontal_z2"] == CheckOutcome.NAO_CONFORME
    assert status["lajeado_taxa_ocupacao_max_z2"] == CheckOutcome.NAO_CONFORME


def test_parametro_ausente_nao_vira_nao_conforme(client, engineer_headers, seeded_catalog):
    """Ausência de dado é `nao_verificavel`, jamais um veredicto negativo."""
    response = client.post(
        "/api/v1/projects",
        headers=engineer_headers,
        json={"name": "Sem medidas", "zone": "Z2", "building_type": "residencial_unifamiliar"},
    )
    projeto = response.json()
    report = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()

    assert report["nao_conforme_count"] == 0
    assert report["nao_verificavel_count"] == report["total_checks"]


def test_severidade_alerta_produz_atencao(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Sem vaga", parking_spaces=0)
    status = _status_map(client, engineer_headers, projeto["id"])

    assert status["lajeado_vagas_estacionamento"] == CheckOutcome.ATENCAO


def test_tolerancia_e_respeitada(client, engineer_headers, seeded_catalog):
    """Recuo de 3,99 m passa com tolerância de 0,02 m."""
    projeto = _criar_projeto(client, engineer_headers, "Tolerância", front_setback=3.99)
    status = _status_map(client, engineer_headers, projeto["id"])

    assert status["lajeado_recuo_frontal_z2"] == CheckOutcome.CONFORME


def test_analises_sao_append_only(client, engineer_headers, db_session, seeded_catalog):
    """Cada avaliação cria uma análise nova; nenhuma é apagada (§3.5)."""
    projeto = _criar_projeto(client, engineer_headers, "Histórico", front_setback=3.00)
    client.post(
        f"/api/v1/projects/{projeto['id']}/versions",
        headers=engineer_headers,
        json={"front_setback": 4.50},
    )

    runs = client.get(
        f"/api/v1/projects/{projeto['id']}/analysis-runs", headers=engineer_headers
    ).json()
    assert len(runs) == 2

    # O veredicto antigo continua registrado.
    antigo = runs[-1]
    registros = (
        db_session.query(ValidationRecord)
        .filter(
            ValidationRecord.analysis_run_id == antigo["id"],
            ValidationRecord.rule_id == "lajeado_recuo_frontal_z2",
        )
        .one()
    )
    assert registros.status == CheckOutcome.NAO_CONFORME

    # E a consulta corrente devolve apenas o mais recente.
    assert _status_map(client, engineer_headers, projeto["id"])[
        "lajeado_recuo_frontal_z2"
    ] == CheckOutcome.CONFORME


def test_outro_municipio_aplica_regra_nacional_mas_nao_regras_de_lajeado(
    client, engineer_headers, seeded_catalog
):
    projeto = _criar_projeto(
        client, engineer_headers, "Fora de Lajeado",
        city_ibge="BR-SP-3550308", city_name="São Paulo", state="SP",
        front_setback=1.0, parking_spaces=0,
    )
    report = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()

    statuses = _status_map(client, engineer_headers, projeto["id"])
    assert set(statuses) == {"brasil_acessibilidade_edificacoes"}
    assert report["total_checks"] == 1
    assert report["is_publishable"] is False


def test_arroio_do_meio_nao_recebe_regras_municipais_de_lajeado(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(
        client, engineer_headers, "Projeto em Arroio do Meio",
        city_ibge="BR-RS-4301008", city_name="Arroio do Meio", state="RS",
        front_setback=1.0,
    )
    statuses = _status_map(client, engineer_headers, projeto["id"])
    assert set(statuses) == {"brasil_acessibilidade_edificacoes"}


def test_get_do_laudo_nao_cria_analise(client, engineer_headers, db_session, seeded_catalog):
    """Regressão: no protótipo, o GET do PDF reavaliava e apagava o histórico."""
    projeto = _criar_projeto(client, engineer_headers, "Laudo")
    antes = db_session.query(AnalysisRun).filter_by(project_id=projeto["id"]).count()

    for _ in range(3):
        assert client.get(
            f"/api/v1/projects/{projeto['id']}/report/pdf", headers=engineer_headers
        ).status_code == 200

    assert db_session.query(AnalysisRun).filter_by(project_id=projeto["id"]).count() == antes


def test_laudo_sem_analise_previa_retorna_409(client, engineer_headers, db_session, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Sem análise")
    db_session.query(AnalysisRun).filter_by(project_id=projeto["id"]).delete()
    db_session.commit()

    response = client.get(
        f"/api/v1/projects/{projeto['id']}/report/pdf", headers=engineer_headers
    )
    assert response.status_code == 409
    assert "evaluate" in response.json()["detail"]


def test_laudo_sinaliza_uso_interno(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Uso interno")
    response = client.get(
        f"/api/v1/projects/{projeto['id']}/report/pdf", headers=engineer_headers
    )

    assert response.headers["X-Atlas-Publishable"] == "false"
    assert "USO_INTERNO_" in response.headers["content-disposition"]
    assert len(response.headers["X-Atlas-Content-Hash"]) == 64
    assert len(response.headers["X-Atlas-Pdf-Sha256"]) == 64
    assert response.content.startswith(b"%PDF")


def test_selo_muda_com_os_parametros(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Selo")
    primeiro = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()

    client.post(
        f"/api/v1/projects/{projeto['id']}/versions",
        headers=engineer_headers,
        json={"front_setback": 2.0},
    )
    segundo = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()

    assert len(primeiro["content_hash"]) == 64
    assert primeiro["content_hash"] != segundo["content_hash"]


def test_selo_e_estavel_para_a_mesma_analise(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Selo estável")
    primeiro = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()
    segundo = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()

    assert primeiro["content_hash"] == segundo["content_hash"]
    assert primeiro["analysis_run_id"] != segundo["analysis_run_id"]


def test_ressalvas_do_laudo_estao_completas():
    """§12 — as limitações são obrigatórias em todo laudo."""
    from app.services.pdf_report_generator import DISCLAIMERS

    texto = " ".join(DISCLAIMERS).lower()
    assert len(DISCLAIMERS) >= 5
    assert "não substitui o responsável técnico" in texto
    assert "não constitui aprovação" in texto
    assert "não verificável" in texto
    assert "não possui validade perante a administração municipal" in texto
    # Regressão: o protótipo afirmava validade para protocolo municipal.
    assert "possui validade técnica para protocolo" not in texto

def test_evaluate_nonexistent_project_returns_404(client, engineer_headers):
    """Garante que a avaliação de um projeto inexistente retorna erro 404."""
    non_existent_id = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/projects/{non_existent_id}/evaluate",
        headers=engineer_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Empreendimento não encontrado."


def test_generate_regulatory_pdf_report_headers_and_content(client, engineer_headers, seeded_catalog):
    projeto = _criar_projeto(client, engineer_headers, "Selo e Headers PDF")
    report = client.post(
        f"/api/v1/projects/{projeto['id']}/evaluate", headers=engineer_headers
    ).json()

    response = client.get(
        f"/api/v1/projects/{projeto['id']}/report/pdf", headers=engineer_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline; filename=" in response.headers["content-disposition"]
    assert response.headers["X-Atlas-Analysis-Run"] == report["analysis_run_id"]
    assert response.headers["X-Atlas-Content-Hash"] == report["content_hash"]
    assert len(response.headers["X-Atlas-Pdf-Sha256"]) == 64
    assert response.headers["X-Atlas-Publishable"] == ("true" if report["is_publishable"] else "false")
    assert response.content.startswith(b"%PDF")

def test_generate_regulatory_pdf_report_project_not_found(client, engineer_headers):
    response = client.get(
        "/api/v1/projects/nonexistent-project-id/report/pdf", headers=engineer_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Empreendimento não encontrado."
