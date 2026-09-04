"""Filas e workers assíncronos (§6.7).

O que precisa ficar provado:

1. o registro do trabalho existe **sempre**, e diz se houve worker ou não;
2. falha vira registro, nunca silêncio — e um trabalho não some da fila;
3. tirar o trabalho do request não afrouxa nenhuma garantia: o isolamento
   entre organizações (§3.1) e a regra de publicabilidade (§7.5) valem igual.
"""

from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.models.domain import JobRecord, JobStatus, JobType
from app.workers import queue as queue_module
from app.workers.queue import (
    HANDLERS,
    InlineQueue,
    QueueBackend,
    enqueue,
    get_queue,
    register,
    run_job,
)


class FakeBroker(QueueBackend):
    """Broker de mentira que só guarda o que foi publicado."""

    name = "fake"

    def __init__(self):
        self.published = []

    def publish(self, job_id, queue="default"):
        self.published.append((job_id, queue))

    def consume(self, queue="default", timeout=5):
        for index, (job_id, fila) in enumerate(self.published):
            if fila == queue:
                self.published.pop(index)
                return job_id
        return None


@pytest.fixture
def broker():
    return FakeBroker()


@pytest.fixture(autouse=True)
def _handlers_limpos():
    """Devolve o registro de handlers ao estado original após cada teste."""
    original = dict(HANDLERS)
    yield
    HANDLERS.clear()
    HANDLERS.update(original)


# =============================================================================
# Registro e execução
# =============================================================================

def test_sem_broker_o_trabalho_roda_no_request_e_diz_isso(db_session, org, engineer):
    @register("teste_ok")
    def _handler(db, record):
        return {"eco": record.payload.get("valor")}

    trabalho = enqueue(
        db_session, "teste_ok", {"valor": 42}, user=engineer, backend=InlineQueue()
    )

    assert trabalho.status == JobStatus.CONCLUIDO
    assert trabalho.executed_inline is True
    assert trabalho.result == {"eco": 42}
    assert trabalho.duration_seconds is not None


def test_com_broker_o_trabalho_fica_enfileirado(db_session, org, engineer, broker):
    @register("teste_ok")
    def _handler(db, record):
        return {"ok": True}

    trabalho = enqueue(db_session, "teste_ok", user=engineer, backend=broker)

    assert trabalho.status == JobStatus.ENFILEIRADO
    assert trabalho.executed_inline is False
    assert broker.published == [(trabalho.id, "default")]
    # Nada foi executado ainda: o resultado só existe depois do worker.
    assert trabalho.result is None


def test_registro_existe_antes_da_publicacao(db_session, org, engineer, broker):
    """O worker não pode receber um id que ainda não está no banco."""
    visto = {}

    class Espiao(FakeBroker):
        def publish(self, job_id, queue="default"):
            visto["existe"] = (
                db_session.query(JobRecord).filter(JobRecord.id == job_id).count() == 1
            )
            super().publish(job_id, queue)

    @register("teste_ok")
    def _handler(db, record):
        return {}

    enqueue(db_session, "teste_ok", user=engineer, backend=Espiao())
    assert visto["existe"] is True


def test_tipo_sem_executor_e_recusado_no_enfileiramento(db_session, engineer):
    with pytest.raises(ValueError, match="não tem executor"):
        enqueue(db_session, "tipo_inexistente", user=engineer)


def test_trabalho_sem_organizacao_e_recusado(db_session):
    @register("teste_ok")
    def _handler(db, record):
        return {}

    with pytest.raises(ValueError, match="organização"):
        enqueue(db_session, "teste_ok")


def test_falha_vira_registro_e_volta_para_a_fila(db_session, org, engineer, broker):
    @register("teste_falha")
    def _handler(db, record):
        raise RuntimeError("o PDF está corrompido")

    trabalho = enqueue(db_session, "teste_falha", user=engineer, backend=broker)
    resultado = run_job(db_session, trabalho.id)

    # Primeira tentativa de três: volta para a fila, com o erro registrado.
    assert resultado.status == JobStatus.ENFILEIRADO
    assert resultado.attempts == 1
    assert "o PDF está corrompido" in resultado.error
    assert resultado.finished_at is not None


def test_tentativas_esgotadas_encerram_em_falha(db_session, org, engineer, broker):
    @register("teste_falha")
    def _handler(db, record):
        raise RuntimeError("falha permanente")

    trabalho = enqueue(db_session, "teste_falha", user=engineer, backend=broker)
    for _ in range(3):
        run_job(db_session, trabalho.id)

    db_session.refresh(trabalho)
    assert trabalho.status == JobStatus.FALHOU
    assert trabalho.attempts == 3
    assert trabalho.is_terminal is True


def test_trabalho_concluido_nao_executa_de_novo(db_session, org, engineer, broker):
    execucoes = []

    @register("teste_contagem")
    def _handler(db, record):
        execucoes.append(1)
        return {"n": len(execucoes)}

    trabalho = enqueue(db_session, "teste_contagem", user=engineer, backend=broker)
    run_job(db_session, trabalho.id)
    run_job(db_session, trabalho.id)

    assert len(execucoes) == 1


def test_backend_desconhecido_falha_alto(monkeypatch):
    monkeypatch.setattr(settings, "QUEUE_BACKEND", "rabbitmq")
    queue_module.reset_queue_cache()
    with pytest.raises(RuntimeError, match="rabbitmq"):
        get_queue()
    queue_module.reset_queue_cache()


# =============================================================================
# Recuperação de órfãos
# =============================================================================

def test_worker_republica_trabalho_parado_na_fila(
    db_session, org, engineer, broker, monkeypatch
):
    """Redis reiniciado não perde trabalho: o estado vive no banco."""
    from app.workers import worker as worker_module

    @register("teste_ok")
    def _handler(db, record):
        return {}

    trabalho = enqueue(db_session, "teste_ok", user=engineer, backend=broker)
    broker.published.clear()  # o broker "perdeu" a mensagem

    trabalho.queued_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    monkeypatch.setattr(worker_module, "get_queue", lambda: broker)
    monkeypatch.setattr(worker_module, "SessionLocal", lambda: db_session)

    assert worker_module.requeue_orphans("default") == 1
    assert broker.published == [(trabalho.id, "default")]


def test_trabalho_recem_publicado_nao_e_republicado(
    db_session, org, engineer, broker, monkeypatch
):
    from app.workers import worker as worker_module

    @register("teste_ok")
    def _handler(db, record):
        return {}

    enqueue(db_session, "teste_ok", user=engineer, backend=broker)
    broker.published.clear()

    monkeypatch.setattr(worker_module, "get_queue", lambda: broker)
    monkeypatch.setattr(worker_module, "SessionLocal", lambda: db_session)

    assert worker_module.requeue_orphans("default") == 0


# =============================================================================
# Executores reais
# =============================================================================

def test_analise_assincrona_produz_a_mesma_analise(
    client, engineer_headers, project, db_session
):
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs/analysis", headers=engineer_headers
    )
    assert response.status_code == 200, response.text  # inline: já concluído

    body = response.json()
    assert body["job"]["status"] == "concluido"
    assert body["job"]["executed_inline"] is True

    resultado = body["job"]["result"]
    assert resultado["total_checks"] > 0
    # O catálogo semeado está inteiro em validação, então nada é publicável.
    assert resultado["is_publishable"] is False
    assert resultado["content_hash"]


def test_laudo_assincrono_vai_para_o_storage(
    client, engineer_headers, project, upload_dir
):
    client.post(
        f"/api/v1/projects/{project['id']}/evaluate", headers=engineer_headers
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs/report", headers=engineer_headers
    )

    assert response.status_code == 200, response.text
    resultado = response.json()["job"]["result"]

    assert resultado["storage_key"].endswith(".pdf")
    assert resultado["size_bytes"] > 0
    # §7.5 — sair do request não torna publicável o que não era.
    assert resultado["is_publishable"] is False
    assert resultado["filename"].startswith("USO_INTERNO_")

    from app.services.storage import get_storage

    assert get_storage().read(resultado["storage_key"]).startswith(b"%PDF")


def test_laudo_sem_analise_falha_com_mensagem(client, engineer_headers, project, db_session):
    """Sem análise não há laudo — e o motivo fica escrito no trabalho.

    O cadastro do empreendimento já dispara uma avaliação, então o cenário
    'nenhuma análise' precisa ser montado removendo-as.
    """
    from app.models.domain import AnalysisRun

    db_session.query(AnalysisRun).filter(
        AnalysisRun.project_id == project["id"]
    ).delete()
    db_session.commit()

    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs/report", headers=engineer_headers
    )
    assert response.status_code == 200
    trabalho = response.json()["job"]
    # Execução inline esgota as tentativas na hora: não há worker que fosse
    # retomar o trabalho depois.
    assert trabalho["status"] == "falhou"
    assert trabalho["attempts"] == trabalho["max_attempts"]
    assert "Nenhuma análise registrada" in trabalho["error"]


def test_extracao_assincrona(client, engineer_headers, project, upload_dir):
    from tests.test_documents import _upload

    documento = _upload(
        client, engineer_headers, project["id"], "prancha.pdf", b"%PDF-1.4 sem texto"
    ).json()

    response = client.post(
        f"/api/v1/documents/{documento['id']}/jobs/extract", headers=engineer_headers
    )
    assert response.status_code == 200

    resultado = response.json()["job"]["result"]
    assert resultado["status"] == "nao_verificavel"
    assert all(v is None for v in resultado["extracted_parameters"].values())


def test_extracao_de_documento_expurgado_falha(
    client, engineer_headers, project, upload_dir, db_session
):
    from app.models.domain import Document
    from tests.test_documents import _upload

    documento = _upload(client, engineer_headers, project["id"], "prancha.pdf").json()
    registro = db_session.query(Document).filter(Document.id == documento["id"]).one()
    registro.purged_at = datetime.utcnow()
    db_session.commit()

    response = client.post(
        f"/api/v1/documents/{documento['id']}/jobs/extract", headers=engineer_headers
    )
    trabalho = response.json()["job"]
    assert trabalho["status"] == "falhou"
    assert "expurgado" in trabalho["error"]


# =============================================================================
# Isolamento entre organizações (§3.1)
# =============================================================================

def test_worker_nao_alcanca_projeto_de_outra_organizacao(db_session, org, project):
    """O worker roda sem `get_current_user`; o isolamento é refeito à mão."""
    from tests.conftest import make_org, make_user
    from app.models.domain import UserRole

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-job@atlas-qa.com")

    trabalho = enqueue(
        db_session,
        JobType.ANALISE_REGULATORIA,
        payload={"project_id": project["id"]},
        user=intruso,
        backend=FakeBroker(),
    )
    resultado = run_job(db_session, trabalho.id)

    assert resultado.result is None
    assert "não encontrado na organização" in resultado.error


def test_trabalho_de_outra_organizacao_responde_404(
    client, db_session, engineer_headers, project
):
    from tests.conftest import auth_headers, make_org, make_user
    from app.models.domain import UserRole

    trabalho = client.post(
        f"/api/v1/projects/{project['id']}/jobs/analysis", headers=engineer_headers
    ).json()["job"]

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-get@atlas-qa.com")

    response = client.get(
        f"/api/v1/jobs/{trabalho['id']}", headers=auth_headers(client, intruso.email)
    )
    assert response.status_code == 404


def test_listagem_de_trabalhos_filtra_por_projeto_e_situacao(
    client, engineer_headers, project
):
    client.post(
        f"/api/v1/projects/{project['id']}/jobs/analysis", headers=engineer_headers
    )

    todos = client.get("/api/v1/jobs", headers=engineer_headers).json()
    assert len(todos) == 1

    concluidos = client.get(
        f"/api/v1/jobs?project_id={project['id']}&job_status=concluido",
        headers=engineer_headers,
    ).json()
    assert len(concluidos) == 1

    falhados = client.get(
        "/api/v1/jobs?job_status=falhou", headers=engineer_headers
    ).json()
    assert falhados == []


def test_situacao_desconhecida_na_listagem_e_recusada(client, engineer_headers):
    response = client.get("/api/v1/jobs?job_status=voando", headers=engineer_headers)
    assert response.status_code == 422


def test_expurgo_como_trabalho_exige_gestao(client, engineer_headers):
    response = client.post("/api/v1/jobs/retention-purge", headers=engineer_headers)
    assert response.status_code == 403


# =============================================================================
# Idempotência da fila de campo (§3.7)
# =============================================================================

def test_reenvio_do_diario_nao_duplica(client, engineer_headers, project):
    """A fila offline reenvia; uma resposta perdida não pode virar dois diários."""
    payload = {
        "date": "2026-08-06",
        "weather_condition": "ensolarado",
        "manpower_own": 4,
        "manpower_subcontracted": 2,
        "activities_done": "Concretagem da laje do 2º pavimento.",
        "client_token": "token-de-campo-1",
    }
    rota = f"/api/v1/projects/{project['id']}/daily-logs"

    primeiro = client.post(rota, headers=engineer_headers, json=payload).json()
    segundo = client.post(rota, headers=engineer_headers, json=payload).json()

    assert primeiro["id"] == segundo["id"]
    assert len(client.get(rota, headers=engineer_headers).json()) == 1


def test_diarios_diferentes_no_mesmo_dia_sao_permitidos(
    client, engineer_headers, project
):
    """A idempotência é por token, não por data: dois turnos, dois registros."""
    rota = f"/api/v1/projects/{project['id']}/daily-logs"
    base = {
        "date": "2026-08-06",
        "weather_condition": "ensolarado",
        "activities_done": "Turno da manhã.",
    }

    client.post(rota, headers=engineer_headers, json={**base, "client_token": "t1"})
    client.post(
        rota,
        headers=engineer_headers,
        json={**base, "activities_done": "Turno da tarde.", "client_token": "t2"},
    )

    assert len(client.get(rota, headers=engineer_headers).json()) == 2


def test_reenvio_de_tarefa_nao_duplica(client, engineer_headers, project):
    payload = {
        "title": "Conferir prumo da alvenaria",
        "status": "a_fazer",
        "priority": "media",
        "client_token": "token-de-campo-2",
    }
    rota = f"/api/v1/projects/{project['id']}/tasks"

    primeiro = client.post(rota, headers=engineer_headers, json=payload).json()
    segundo = client.post(rota, headers=engineer_headers, json=payload).json()

    assert primeiro["id"] == segundo["id"]
    assert len(client.get(rota, headers=engineer_headers).json()) == 1


def test_token_de_outra_organizacao_nao_colide(
    client, db_session, engineer_headers, project
):
    """Token é escopo de tenant: dois clientes podem gerar o mesmo por azar."""
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user

    payload = {
        "date": "2026-08-06",
        "activities_done": "Registro da organização A.",
        "client_token": "colisao",
    }
    client.post(
        f"/api/v1/projects/{project['id']}/daily-logs",
        headers=engineer_headers,
        json=payload,
    )

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-token@atlas-qa.com")
    outro_projeto = client.post(
        "/api/v1/projects",
        headers=auth_headers(client, intruso.email),
        json={"name": "Obra da outra org", "lot_area": 300.0},
    ).json()

    resposta = client.post(
        f"/api/v1/projects/{outro_projeto['id']}/daily-logs",
        headers=auth_headers(client, intruso.email),
        json={**payload, "activities_done": "Registro da organização B."},
    )
    assert resposta.status_code == 201
    assert resposta.json()["activities_done"] == "Registro da organização B."

def test_purge_retention_task_execution(db_session, org, monkeypatch):
    from app.workers.tasks import purge_retention
    from app.models.domain import JobRecord

    # Mock return value class
    class MockPurgeReport:
        dry_run = True
        examined = 5
        purged = 2
        already_missing = 1
        failed = 0
        document_ids = ["doc1", "doc2"]
        errors = []

    # Function to mock the target
    def mock_purge_expired_documents(db, organization_id, dry_run):
        assert organization_id == org.id
        assert dry_run is True
        return MockPurgeReport()

    monkeypatch.setattr(
        "app.workers.tasks.purge_expired_documents",
        mock_purge_expired_documents
    )

    record = JobRecord(organization_id=org.id, payload={"dry_run": True})

    result = purge_retention(db_session, record)

    assert result == {
        "dry_run": True,
        "examined": 5,
        "purged": 2,
        "already_missing": 1,
        "failed": 0,
        "document_ids": ["doc1", "doc2"],
        "errors": [],
    }
