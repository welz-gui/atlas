"""Quantas consultas as telas de protocolo fazem (N+1).

Cada processo tem uma coleção de exigências (e de eventos). Lida sem
`selectinload`, a coleção dispara uma consulta por processo: o custo da tela
cresce com o histórico do empreendimento. O que se afirma aqui é o formato do
custo — **não cresce com o número de processos** —, não um número de consultas,
que mudaria a cada coluna nova.
"""

import pytest
from sqlalchemy import event


def _criar_projeto(client, headers):
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Residencial Sol Nascente", "zone": "Z2", "lot_area": 360.0},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _acrescentar_processos(client, headers, project_id, quantos, ja_existentes):
    for i in range(quantos):
        response = client.post(
            f"/api/v1/projects/{project_id}/protocols",
            headers=headers,
            json={
                "protocol_number": f"2026/PMU-{ja_existentes + i:06d}",
                "agency": "Secretaria de Planejamento — Lajeado/RS",
                "submitted_at": "2026-07-15",
            },
        )
        assert response.status_code == 201, response.text
        for descricao in ("Recuo frontal.", "ART assinada."):
            client.post(
                f"/api/v1/protocols/{response.json()['id']}/requirements",
                headers=headers,
                json={"description": descricao},
            )


def _consultas(client, db_session, headers, caminho):
    """SELECTs emitidos por uma chamada, a partir de uma sessão sem cache."""
    db_session.expire_all()
    emitidas = []

    def contar(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            emitidas.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", contar)
    try:
        response = client.get(caminho, headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", contar)
    assert response.status_code == 200, response.text
    return len(emitidas), response.json()


@pytest.mark.parametrize(
    "caminho",
    [
        "/api/v1/projects/{id}/protocols",
        "/api/v1/projects/{id}/prediction-accuracy",
        "/api/v1/portal/projects/{id}",
    ],
)
def test_consultas_nao_crescem_com_o_numero_de_processos(
    client, db_session, engineer_headers, seeded_catalog, caminho
):
    project_id = _criar_projeto(client, engineer_headers)
    caminho = caminho.format(id=project_id)

    _acrescentar_processos(client, engineer_headers, project_id, 2, 0)
    com_dois, _ = _consultas(client, db_session, engineer_headers, caminho)

    _acrescentar_processos(client, engineer_headers, project_id, 4, 2)
    com_seis, corpo = _consultas(client, db_session, engineer_headers, caminho)

    assert com_seis == com_dois, f"{com_dois} consultas com 2 processos, {com_seis} com 6"
    # E o resultado continua inteiro: a otimização não pode custar dado.
    if isinstance(corpo, list):
        assert len(corpo) == 6
        assert all(len(p["requirements"]) == 2 for p in corpo)
    elif "total_requirements" in corpo:
        assert corpo["total_requirements"] == 12
    else:
        assert len(corpo["protocols"]) == 6
        assert all(len(p["open_requirements"]) == 2 for p in corpo["protocols"])
