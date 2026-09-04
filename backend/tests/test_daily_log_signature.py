"""Assinatura do diário de obra (§8.12 — item D4).

Antes desta frente, `status` nascia como `"assinado"` por `default` e o
frontend ainda mandava a string literal. Todo diário afirmava um ato humano que
nunca aconteceu — inclusive os que chegavam pela fila offline, quando ninguém
estava diante de tela alguma.

O que estes testes travam:

1. **diário nasce rascunho**, e o cliente não consegue declarar-se assinado;
2. **assinar registra quem, quando e sobre o quê** — sem o hash, "assinado" não
   distingue o texto lido do texto alterado depois;
3. **alteração posterior é detectável**;
4. **não assinado devolve `null`, não `false`** — ausência de assinatura não é
   adulteração (I1).
"""

from datetime import datetime


from app.models.domain import DailyLog, DailyLogState
from app.services import daily_log_signature as assinatura

CONTEUDO = {
    "date": "2026-08-14",
    "weather_condition": "ensolarado",
    "manpower_own": 12,
    "manpower_subcontracted": 3,
    "activities_done": "Concretagem da laje do 2º pavimento.",
    "occurrences": "Chuva a partir das 16h.",
}


def _criar(client, headers, project_id, **extras):
    corpo = {**CONTEUDO, **extras}
    response = client.post(
        f"/api/v1/projects/{project_id}/daily-logs", headers=headers, json=corpo
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- O diário nasce rascunho -------------------------------------------------


def test_diario_nasce_rascunho(client, engineer_headers, project):
    log = _criar(client, engineer_headers, project["id"])

    assert log["status"] == DailyLogState.RASCUNHO
    assert log["signed_at"] is None
    assert log["signed_by_name"] is None


def test_cliente_nao_consegue_declarar_se_assinado(
    client, engineer_headers, project
):
    """`status` não faz parte do corpo de criação — mandar não tem efeito."""
    log = _criar(client, engineer_headers, project["id"], status="assinado")

    assert log["status"] == DailyLogState.RASCUNHO


def test_rascunho_nao_tem_assinatura_para_conferir(client, engineer_headers, project):
    """`null`, não `false`: ausência de assinatura não é adulteração (I1)."""
    log = _criar(client, engineer_headers, project["id"])

    assert log["signature_valid"] is None
    assert log["content_hash"] is None


# --- Assinar -----------------------------------------------------------------


def test_assinar_registra_quem_quando_e_sobre_o_que(
    client, engineer_headers, project, engineer
):
    log = _criar(client, engineer_headers, project["id"])

    resposta = client.post(
        f"/api/v1/daily-logs/{log['id']}/sign", headers=engineer_headers
    )
    assert resposta.status_code == 200, resposta.text
    assinado = resposta.json()

    assert assinado["status"] == DailyLogState.ASSINADO
    assert assinado["signed_by_name"] == engineer.name
    assert assinado["signed_at"] is not None
    assert len(assinado["content_hash"]) == 64
    assert assinado["signature_valid"] is True


def test_reassinar_e_recusado(client, engineer_headers, project):
    """A assinatura vale para um conteúdo; duas tornariam ambíguo qual vale."""
    log = _criar(client, engineer_headers, project["id"])
    client.post(f"/api/v1/daily-logs/{log['id']}/sign", headers=engineer_headers)

    segunda = client.post(
        f"/api/v1/daily-logs/{log['id']}/sign", headers=engineer_headers
    )
    assert segunda.status_code == 409


def test_diario_de_outra_organizacao_nao_e_assinavel(
    client, engineer_headers, project, db_session
):
    from tests.conftest import auth_headers, make_org, make_user
    from app.models.domain import UserRole

    log = _criar(client, engineer_headers, project["id"])

    outra = make_org(db_session, name="Outra Construtora")
    intruso = make_user(
        db_session, outra, UserRole.ENGINEER, email="intruso@atlas-qa.com"
    )
    headers = auth_headers(client, intruso.email)

    resposta = client.post(f"/api/v1/daily-logs/{log['id']}/sign", headers=headers)
    assert resposta.status_code == 404


# --- A alteração posterior é detectável --------------------------------------


def test_alteracao_depois_de_assinado_quebra_a_conferencia(
    client, engineer_headers, project, db_session
):
    """É a razão do hash: sem ele, 'assinado' não diria sobre qual texto."""
    log = _criar(client, engineer_headers, project["id"])
    client.post(f"/api/v1/daily-logs/{log['id']}/sign", headers=engineer_headers)

    # Alteração direta no banco, como faria quem contornasse a API.
    registro = db_session.query(DailyLog).filter(DailyLog.id == log["id"]).one()
    registro.activities_done = "Texto trocado depois da assinatura."
    db_session.commit()

    listagem = client.get(
        f"/api/v1/projects/{project['id']}/daily-logs", headers=engineer_headers
    ).json()
    alterado = next(item for item in listagem if item["id"] == log["id"])

    assert alterado["signature_valid"] is False
    assert alterado["status"] == DailyLogState.ASSINADO  # o estado permanece
    assert alterado["signed_by_name"] is not None  # e quem assinou também


# --- O hash em si ------------------------------------------------------------


def test_hash_e_estavel_para_o_mesmo_conteudo():
    a = DailyLog(project_id="p1", **CONTEUDO)
    b = DailyLog(project_id="p1", **CONTEUDO)

    assert assinatura.content_hash(a) == assinatura.content_hash(b)


def test_hash_muda_com_qualquer_campo_de_conteudo():
    base = DailyLog(project_id="p1", **CONTEUDO)
    referencia = assinatura.content_hash(base)

    for campo, valor in (
        ("activities_done", "Outra coisa"),
        ("manpower_own", 99),
        ("occurrences", None),
        ("date", "2026-08-15"),
    ):
        outro = DailyLog(project_id="p1", **{**CONTEUDO, campo: valor})
        assert assinatura.content_hash(outro) != referencia, campo


def test_hash_ignora_campos_de_controle():
    """Assinatura é sobre o que foi relatado, não sobre metadados da linha."""
    base = DailyLog(project_id="p1", **CONTEUDO)
    referencia = assinatura.content_hash(base)

    base.created_at = datetime(2030, 1, 1)
    base.client_token = "token-qualquer"

    assert assinatura.content_hash(base) == referencia
