"""Observabilidade: correlação, log sem vazamento e sondas honestas (§12).

O que estes testes protegem:

1. **`/health` não afirma o que não apurou.** Ele devolvia `"healthy"` sem
   verificar nada — respondia saudável com o banco fora do ar;
2. **componente não verificado não vira `ok`** — é o I10 aplicado às sondas;
3. **o log não carrega segredo nem dado pessoal**, porque `docs/LGPD.md`
   registra que a pergunta ao assistente pode conter dado de terceiro;
4. **o identificador volta ao cliente**, senão "deu erro ontem" é tudo o que o
   relato traz.
"""

import json
import logging

import pytest

from app.core.logging import (
    JsonFormatter,
    REDACTED,
    current_request_id,
    redact,
    set_request_id,
)


# --- Correlação --------------------------------------------------------------


def test_resposta_traz_o_identificador(client):
    resposta = client.get("/api/v1/health")

    assert resposta.headers.get("X-Request-Id")


def test_identificador_do_cliente_e_preservado(client):
    """Uma chamada que atravessa serviços mantém o mesmo fio."""
    resposta = client.get(
        "/api/v1/health", headers={"X-Request-Id": "fio-do-cliente-123"}
    )

    assert resposta.headers["X-Request-Id"] == "fio-do-cliente-123"


def test_identificadores_diferem_entre_requisicoes(client):
    primeiro = client.get("/api/v1/health").headers["X-Request-Id"]
    segundo = client.get("/api/v1/health").headers["X-Request-Id"]

    assert primeiro != segundo


def test_identificador_nao_sobrevive_a_requisicao(client):
    client.get("/api/v1/health")

    assert current_request_id() is None


# --- O log não vaza ----------------------------------------------------------


@pytest.mark.parametrize(
    "campo",
    [
        "password",
        "senha",
        "SECRET_KEY",
        "authorization",
        "api_key",
        "mfa_code",
        "recovery_code",
        "prompt",
        "owner_document",
        "user_password",  # o erro comum é o nome composto
    ],
)
def test_campo_sensivel_e_redigido(campo):
    assert redact({campo: "valor-real"})[campo] == REDACTED


def test_redacao_alcanca_campo_aninhado():
    """O campo perigoso costuma estar dentro do payload de um trabalho."""
    limpo = redact({"payload": {"senha": "abc", "documento": "memorial.pdf"}})

    assert limpo["payload"]["senha"] == REDACTED
    assert limpo["payload"]["documento"] == "memorial.pdf"


def test_campo_inocente_sobrevive():
    """Redigir demais cega a depuração tanto quanto redigir de menos."""
    limpo = redact({"status": 200, "duration_ms": 12.3, "path": "/api/v1/health"})

    assert limpo == {"status": 200, "duration_ms": 12.3, "path": "/api/v1/health"}


# --- O formato ---------------------------------------------------------------


def _formatar(**extras) -> dict:
    registro = logging.LogRecord(
        name="atlas.teste",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="mensagem",
        args=(),
        exc_info=None,
    )
    for chave, valor in extras.items():
        setattr(registro, chave, valor)
    return json.loads(JsonFormatter().format(registro))


def test_cada_linha_e_um_objeto_json():
    saida = _formatar(status=200)

    assert saida["level"] == "info"
    assert saida["logger"] == "atlas.teste"
    assert saida["message"] == "mensagem"
    assert saida["status"] == 200
    assert "ts" in saida


def test_o_identificador_entra_na_linha():
    token = set_request_id("abc-123")
    try:
        assert _formatar()["request_id"] == "abc-123"
    finally:
        from app.core.logging import reset_request_id

        reset_request_id(token)


def test_extra_sensivel_e_redigido_no_formatador():
    """Mesmo que alguém passe o campo perigoso direto em `extra`."""
    assert _formatar(senha="nao-deve-aparecer")["senha"] == REDACTED


# --- As sondas ---------------------------------------------------------------


def test_liveness_nao_toca_em_dependencia(client):
    """Sonda de vida que consulta o banco derruba tudo quando o banco oscila."""
    corpo = client.get("/api/v1/health").json()

    assert corpo["status"] == "vivo"
    assert "components" not in corpo


def test_readiness_verifica_cada_componente(client):
    corpo = client.get("/api/v1/health/ready").json()

    assert corpo["status"] == "pronto"
    assert set(corpo["components"]) == {"database", "storage", "queue", "antivirus"}
    assert corpo["components"]["database"]["status"] == "ok"


def test_antivirus_desligado_e_nao_verificado_e_nao_ok(client):
    """I10: ausência de verificação não é aprovação, também na sonda."""
    componente = client.get("/api/v1/health/ready").json()["components"]["antivirus"]

    assert componente["status"] == "nao_verificado"
    assert componente["status"] != "ok"


def test_fila_inline_e_declarada_como_tal(client):
    """Não é falha, é modo — mas quem lê precisa saber que não há worker."""
    componente = client.get("/api/v1/health/ready").json()["components"]["queue"]

    assert componente["status"] == "inline"


def test_banco_fora_do_ar_derruba_a_prontidao(client, monkeypatch):
    """O defeito original: responder saudável com a dependência essencial fora."""
    from app.api.v1.endpoints import health

    monkeypatch.setattr(
        health,
        "_check_database",
        lambda: {"status": "falhou", "detail": "banco de dados indisponível"},
    )

    resposta = client.get("/api/v1/health/ready")

    assert resposta.status_code == 503
    assert resposta.json()["status"] == "indisponivel"
    # E a sonda de vida continua respondendo: o processo está de pé.
    assert client.get("/api/v1/health").status_code == 200


def test_check_database_captura_excecao(monkeypatch):
    """O detalhe da exceção não escapa para a resposta (§12) — só o rótulo genérico."""
    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.health import _check_database

    def falha(*args, **kwargs):
        raise Exception("erro forçado, com detalhe que não deve aparecer")

    monkeypatch.setattr(Session, "execute", falha)

    assert _check_database() == {"status": "falhou", "detail": "banco de dados indisponível"}


def test_check_storage_captura_excecao(monkeypatch):
    import app.services.storage
    from app.api.v1.endpoints.health import _check_storage

    def falha():
        raise RuntimeError("erro forçado")

    monkeypatch.setattr(app.services.storage, "get_storage", falha)

    assert _check_storage() == {"status": "falhou", "detail": "armazenamento indisponível"}


def test_fila_fora_do_ar_e_reportada_sem_derrubar_a_prontidao(client, monkeypatch):
    """A fila não é essencial (`ESSENTIAL = ("database",)`): falha aparece, mas não derruba 200."""
    from app.workers import queue

    def falha():
        raise RuntimeError("erro forçado")

    monkeypatch.setattr(queue, "get_queue", falha)

    resposta = client.get("/api/v1/health/ready")

    assert resposta.status_code == 200
    componente = resposta.json()["components"]["queue"]
    assert componente["status"] == "falhou"
    assert componente["detail"] == "fila indisponível"


def test_antivirus_indisponivel_por_excecao(client, monkeypatch):
    """Exceção ao consultar o clamd — distinto de 'desligado por configuração'."""
    from app.core.config import settings
    from app.services.antivirus import ClamAVScanner

    monkeypatch.setattr(settings, "ANTIVIRUS_BACKEND", "clamav")
    monkeypatch.setattr(
        ClamAVScanner, "_version", lambda self: (_ for _ in ()).throw(RuntimeError("simulado"))
    )

    componente = client.get("/api/v1/health/ready").json()["components"]["antivirus"]

    assert componente["status"] == "falhou"
    assert componente["detail"] == "antivírus indisponível"


def test_antivirus_daemon_nao_responde_ao_version(client, monkeypatch):
    """Sem exceção, mas sem versão — o clamd está de pé mas não respondeu."""
    from app.core.config import settings
    from app.services.antivirus import ClamAVScanner

    monkeypatch.setattr(settings, "ANTIVIRUS_BACKEND", "clamav")
    monkeypatch.setattr(ClamAVScanner, "_version", lambda self: None)

    componente = client.get("/api/v1/health/ready").json()["components"]["antivirus"]

    assert componente["status"] == "falhou"
    assert componente["detail"] == "clamd não respondeu ao VERSION."
