"""Storage, antivírus e retenção (§6.6).

Três garantias sob teste:

1. o binário nunca é escrito fora do diretório do backend, e uma gravação
   interrompida não deixa arquivo parcial;
2. a ausência de antivírus é registrada como ausência — não como aprovação;
3. o expurgo por retenção apaga o **arquivo**, nunca o registro.
"""

from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.models.domain import Document, DocumentState
from app.services import antivirus as antivirus_module
from app.services import storage as storage_module
from app.services.antivirus import NullScanner, ScanResult, ScanStatus
from app.services.retention import (
    eligible_documents,
    mark_obsolete,
    purge_expired_documents,
    retention_deadline,
)
from app.services.storage import (
    LocalStorage,
    ObjectNotFound,
    StorageError,
    build_key,
    get_storage,
)


@pytest.fixture
def local_storage(tmp_path):
    return LocalStorage(root=str(tmp_path / "blobs"))


# =============================================================================
# Storage
# =============================================================================

def test_chave_gerada_e_opaca():
    key = build_key(".pdf")
    assert key.endswith(".pdf")
    assert "/" not in key and ".." not in key
    assert build_key(".pdf") != key


def test_gravacao_e_leitura(local_storage):
    key = build_key(".pdf")
    with local_storage.writer(key) as writer:
        writer.write(b"%PDF-1.4 ")
        writer.write(b"conteudo")

    stored = writer.result
    assert stored.size_bytes == len(b"%PDF-1.4 conteudo")
    assert stored.backend == "local"
    assert local_storage.read(key) == b"%PDF-1.4 conteudo"
    assert local_storage.exists(key)


def test_gravacao_interrompida_nao_deixa_objeto(local_storage, tmp_path):
    key = build_key(".pdf")
    with pytest.raises(RuntimeError):
        with local_storage.writer(key) as writer:
            writer.write(b"metade do arquivo")
            raise RuntimeError("conexão caiu")

    assert not local_storage.exists(key)
    # E nem sobra o temporário.
    assert list((tmp_path / "blobs").iterdir()) == []


def test_resultado_indisponivel_antes_do_commit(local_storage):
    writer = local_storage.writer(build_key(".pdf"), defer_commit=True)
    writer.write(b"conteudo")
    with pytest.raises(StorageError):
        _ = writer.result
    writer.abort()


def test_chave_adulterada_nao_escapa_do_diretorio(local_storage):
    """Cinto e suspensório: chave vinda do banco tratada como não confiável."""
    with local_storage.writer("../../etc/atlas_escape.pdf") as writer:
        writer.write(b"x")

    import os

    assert os.path.isfile(os.path.join(local_storage.root, "atlas_escape.pdf"))
    assert not os.path.exists("/etc/atlas_escape.pdf")


def test_leitura_de_chave_inexistente(local_storage):
    with pytest.raises(ObjectNotFound):
        local_storage.read("nao-existe.pdf")


def test_backend_desconhecido_falha_alto(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "dropbox")
    storage_module.reset_storage_cache()
    with pytest.raises(StorageError, match="dropbox"):
        get_storage()
    storage_module.reset_storage_cache()


def test_s3_sem_bucket_falha_na_construcao(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "")
    storage_module.reset_storage_cache()
    with pytest.raises(StorageError, match="S3_BUCKET"):
        get_storage()
    storage_module.reset_storage_cache()


# =============================================================================
# Antivírus
# =============================================================================

def test_sem_antivirus_o_arquivo_nao_e_dado_por_limpo(tmp_path):
    alvo = tmp_path / "arquivo.pdf"
    alvo.write_bytes(b"conteudo")

    resultado = NullScanner().scan_file(str(alvo))
    assert resultado.status == ScanStatus.NAO_VERIFICADO
    assert resultado.is_clean is False
    assert "Nenhum antivírus configurado" in resultado.detail


def test_upload_registra_ausencia_de_varredura(
    client, engineer_headers, project, upload_dir
):
    from tests.test_documents import _upload

    body = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    assert body["antivirus_status"] == "nao_verificado"
    assert body["antivirus_engine"] is None


def test_arquivo_infectado_e_recusado_e_nao_chega_ao_storage(
    client, engineer_headers, project, upload_dir, monkeypatch
):
    class Infectado(NullScanner):
        def scan_file(self, path):
            return ScanResult(
                status=ScanStatus.INFECTADO,
                engine="fake",
                signature="Eicar-Test-Signature",
                scanned_at=datetime.utcnow(),
            )

    monkeypatch.setattr(antivirus_module, "get_scanner", lambda: Infectado())
    from app.api.v1.endpoints import documents as documents_module

    monkeypatch.setattr(documents_module, "get_scanner", lambda: Infectado())

    from tests.test_documents import _upload

    response = _upload(client, engineer_headers, project["id"], "virus.pdf")
    assert response.status_code == 422
    assert "Eicar-Test-Signature" in response.json()["detail"]
    # O arquivo não pode ter sido gravado nem por um instante.
    assert list(upload_dir.iterdir()) == []


def test_varredura_obrigatoria_recusa_o_que_nao_foi_verificado(
    client, engineer_headers, project, upload_dir, monkeypatch
):
    """Falhar fechado: com antivírus obrigatório, 'não sabemos' é recusa."""
    monkeypatch.setattr(settings, "ANTIVIRUS_REQUIRED", True)

    from tests.test_documents import _upload

    response = _upload(client, engineer_headers, project["id"], "planta.pdf")
    assert response.status_code == 503
    assert list(upload_dir.iterdir()) == []


def test_clamav_interpreta_resposta_do_daemon(monkeypatch, tmp_path):
    """A leitura de 'stream: X FOUND' precisa extrair a assinatura correta."""
    from app.services.antivirus import ClamAVScanner

    alvo = tmp_path / "arquivo.pdf"
    alvo.write_bytes(b"conteudo")

    class FakeSocket:
        def __init__(self, resposta):
            self.resposta = resposta

        def sendall(self, _data):
            pass

        def recv(self, _n):
            return self.resposta

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    scanner = ClamAVScanner(host="127.0.0.1", port=3310)
    monkeypatch.setattr(
        scanner, "_connect", lambda: FakeSocket(b"stream: Eicar-Test-Signature FOUND\0")
    )
    monkeypatch.setattr(scanner, "_version", lambda: "ClamAV 1.0.0")

    resultado = scanner.scan_file(str(alvo))
    assert resultado.status == ScanStatus.INFECTADO
    assert resultado.signature == "Eicar-Test-Signature"
    assert resultado.engine_version == "ClamAV 1.0.0"

    monkeypatch.setattr(scanner, "_connect", lambda: FakeSocket(b"stream: OK\0"))
    assert scanner.scan_file(str(alvo)).status == ScanStatus.LIMPO


def test_clamd_fora_do_ar_nao_vira_arquivo_limpo(monkeypatch, tmp_path):
    from app.services.antivirus import ClamAVScanner

    alvo = tmp_path / "arquivo.pdf"
    alvo.write_bytes(b"conteudo")

    scanner = ClamAVScanner(host="127.0.0.1", port=1)

    def recusa():
        raise OSError("connection refused")

    monkeypatch.setattr(scanner, "_connect", recusa)
    resultado = scanner.scan_file(str(alvo))
    assert resultado.status == ScanStatus.NAO_VERIFICADO
    assert resultado.is_clean is False


# =============================================================================
# Retenção
# =============================================================================

def test_retencao_desligada_nao_agenda_expurgo(monkeypatch):
    monkeypatch.setattr(settings, "OBSOLETE_RETENTION_DAYS", 0)
    assert retention_deadline(datetime.utcnow()) is None


def test_marcar_obsoleto_agenda_a_retencao(monkeypatch, db_session, org):
    monkeypatch.setattr(settings, "OBSOLETE_RETENTION_DAYS", 30)
    documento = Document(
        organization_id=org.id, project_id="p", title="t", file_path="k.pdf"
    )
    momento = datetime(2026, 1, 1)
    mark_obsolete(documento, when=momento)

    assert documento.status == DocumentState.OBSOLETO
    assert documento.retention_until == momento + timedelta(days=30)


def _documento_obsoleto(db_session, org, project_id, key, vencido_em):
    documento = Document(
        organization_id=org.id,
        project_id=project_id,
        title="Prancha antiga",
        file_path=key,
        status=DocumentState.OBSOLETO,
        superseded_at=vencido_em,
        retention_until=vencido_em,
    )
    db_session.add(documento)
    db_session.commit()
    db_session.refresh(documento)
    return documento


def test_expurgo_apaga_o_arquivo_e_preserva_o_registro(
    db_session, org, project, local_storage
):
    key = build_key(".pdf")
    with local_storage.writer(key) as writer:
        writer.write(b"%PDF-1.4 antigo")

    documento = _documento_obsoleto(
        db_session, org, project["id"], key, datetime.utcnow() - timedelta(days=1)
    )

    relatorio = purge_expired_documents(db_session, org.id, storage=local_storage)

    assert relatorio.purged == 1
    assert not local_storage.exists(key)

    db_session.refresh(documento)
    assert documento.purged_at is not None
    assert documento.is_purged is True
    # O registro continua completo: título, versão e hash seguem consultáveis.
    assert documento.title == "Prancha antiga"
    assert db_session.query(Document).filter(Document.id == documento.id).count() == 1


def test_documento_vigente_nunca_e_expurgado(db_session, org, project, local_storage):
    documento = Document(
        organization_id=org.id,
        project_id=project["id"],
        title="Prancha vigente",
        file_path=build_key(".pdf"),
        status=DocumentState.VIGENTE,
        retention_until=datetime.utcnow() - timedelta(days=365),
    )
    db_session.add(documento)
    db_session.commit()

    assert eligible_documents(db_session, org.id) == []


def test_sem_prazo_significa_guardar(db_session, org, project, local_storage):
    _documento_obsoleto(db_session, org, project["id"], build_key(".pdf"), None)
    assert eligible_documents(db_session, org.id) == []


def test_simulacao_nao_apaga_nada(db_session, org, project, local_storage):
    key = build_key(".pdf")
    with local_storage.writer(key) as writer:
        writer.write(b"conteudo")

    _documento_obsoleto(
        db_session, org, project["id"], key, datetime.utcnow() - timedelta(days=1)
    )

    relatorio = purge_expired_documents(
        db_session, org.id, dry_run=True, storage=local_storage
    )
    assert relatorio.examined == 1
    assert relatorio.purged == 0
    assert local_storage.exists(key)


def test_expurgo_nao_alcanca_outra_organizacao(
    db_session, org, project, local_storage
):
    from tests.conftest import make_org

    outra = make_org(db_session, "Concorrente S.A.")
    key = build_key(".pdf")
    with local_storage.writer(key) as writer:
        writer.write(b"conteudo")

    _documento_obsoleto(
        db_session, org, project["id"], key, datetime.utcnow() - timedelta(days=1)
    )

    relatorio = purge_expired_documents(db_session, outra.id, storage=local_storage)
    assert relatorio.purged == 0
    assert local_storage.exists(key)


# =============================================================================
# Endpoints
# =============================================================================

def test_download_devolve_o_binario(client, engineer_headers, project, upload_dir):
    from tests.test_documents import _upload

    conteudo = b"%PDF-1.4 conteudo para download"
    documento = _upload(
        client, engineer_headers, project["id"], "planta.pdf", conteudo
    ).json()

    response = client.get(
        f"/api/v1/documents/{documento['id']}/download", headers=engineer_headers
    )
    assert response.status_code == 200
    assert response.content == conteudo
    assert response.headers["X-Atlas-Antivirus-Status"] == "nao_verificado"


def test_download_de_documento_expurgado_responde_410(
    client, engineer_headers, project, upload_dir, db_session
):
    from tests.test_documents import _upload

    documento = _upload(client, engineer_headers, project["id"], "planta.pdf").json()

    registro = db_session.query(Document).filter(Document.id == documento["id"]).one()
    registro.purged_at = datetime.utcnow()
    registro.purge_reason = "Retenção de 30 dia(s) (§6.6)."
    db_session.commit()

    response = client.get(
        f"/api/v1/documents/{documento['id']}/download", headers=engineer_headers
    )
    assert response.status_code == 410
    assert "expurgado" in response.json()["detail"]


def test_download_de_outro_tenant_responde_404(
    client, db_session, engineer_headers, project, upload_dir
):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user
    from tests.test_documents import _upload

    documento = _upload(client, engineer_headers, project["id"], "planta.pdf").json()

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-dl@atlas-qa.com")

    response = client.get(
        f"/api/v1/documents/{documento['id']}/download",
        headers=auth_headers(client, intruso.email),
    )
    assert response.status_code == 404


def test_expurgo_pela_api_exige_gestao_da_organizacao(
    client, engineer_headers, upload_dir
):
    response = client.post("/api/v1/storage/purge-expired", headers=engineer_headers)
    assert response.status_code == 403


def test_expurgo_pela_api_e_simulacao_por_padrao(client, db_session, org, upload_dir):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_user

    dono = make_user(db_session, org, UserRole.OWNER, "dono-purge@atlas-qa.com")
    response = client.post(
        "/api/v1/storage/purge-expired", headers=auth_headers(client, dono.email)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["retention_enabled"] is False
