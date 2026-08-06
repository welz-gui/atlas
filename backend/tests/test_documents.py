"""Gestão documental: upload seguro, versionamento e QR Code (§8.3, §6.6)."""

import hashlib
import io
import os

import pytest

from app.api.v1.endpoints import documents as documents_module


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    directory = tmp_path / "uploads"
    directory.mkdir()
    monkeypatch.setattr(documents_module, "UPLOAD_DIR", str(directory))
    return directory


def _upload(client, headers, project_id, filename, content=b"%PDF-1.4 conteudo", **extra):
    data = {"title": "Prancha", "category": "projeto_arquitetonico", "version": "v1.0"}
    data.update(extra)
    return client.post(
        f"/api/v1/projects/{project_id}/documents/upload",
        headers=headers,
        data=data,
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
    )


# --- Segurança do upload -----------------------------------------------------

def test_path_traversal_nao_escapa_do_diretorio(
    client, engineer_headers, project, upload_dir
):
    """Regressão: o protótipo montava o caminho com file.filename cru."""
    response = _upload(
        client, engineer_headers, project["id"], "../../../../tmp/atlas_escape.pdf"
    )
    assert response.status_code == 201, response.text

    stored = response.json()["file_path"]
    assert "/" not in stored and "\\" not in stored and ".." not in stored
    assert os.path.exists(os.path.join(upload_dir, stored))
    assert not os.path.exists("/tmp/atlas_escape.pdf")

    # O nome original é preservado como metadado, sem tocar o disco.
    assert response.json()["original_filename"] == "atlas_escape.pdf"


def test_extensao_fora_da_allowlist_e_recusada(
    client, engineer_headers, project, upload_dir
):
    response = _upload(
        client, engineer_headers, project["id"], "payload.sh", b"#!/bin/sh\nrm -rf /"
    )
    assert response.status_code == 415


def test_arquivo_sem_extensao_e_recusado(client, engineer_headers, project, upload_dir):
    assert _upload(client, engineer_headers, project["id"], "arquivo").status_code == 415


def test_arquivo_vazio_e_recusado(client, engineer_headers, project, upload_dir):
    assert _upload(
        client, engineer_headers, project["id"], "vazio.pdf", b""
    ).status_code == 400


def test_upload_acima_do_limite_e_recusado(
    client, engineer_headers, project, upload_dir, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    response = _upload(
        client, engineer_headers, project["id"], "grande.pdf", b"x" * (2 * 1024 * 1024)
    )

    assert response.status_code == 413
    # O arquivo parcial não pode ficar para trás.
    assert list(upload_dir.iterdir()) == []


def test_hash_e_tamanho_sao_registrados(client, engineer_headers, project, upload_dir):
    content = b"%PDF-1.4 conteudo para auditoria"
    body = _upload(client, engineer_headers, project["id"], "prancha.pdf", content).json()

    assert body["hash_sha256"] == hashlib.sha256(content).hexdigest()
    assert body["size_bytes"] == len(content)
    assert body["uploaded_by_id"] is not None


def test_cliente_nao_faz_upload(client, db_session, org, project, upload_dir):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_user

    cliente = make_user(db_session, org, UserRole.CLIENT, "cliente-doc@atlas-qa.com")
    headers = auth_headers(client, cliente.email)

    assert _upload(client, headers, project["id"], "prancha.pdf").status_code == 403


# --- Versionamento (§8.3) ----------------------------------------------------

def test_nova_versao_torna_a_anterior_obsoleta(
    client, engineer_headers, project, upload_dir
):
    """Duas versões vigentes do mesmo documento seriam ambíguas em obra."""
    v1 = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    assert v1["status"] == "vigente"
    assert v1["is_current"] is True

    v2 = _upload(
        client, engineer_headers, project["id"], "planta.pdf",
        version="v2.0", supersedes_id=v1["id"],
    ).json()

    assert v2["status"] == "vigente"
    assert v2["supersedes_id"] == v1["id"]

    documentos = client.get(
        f"/api/v1/projects/{project['id']}/documents", headers=engineer_headers
    ).json()
    anterior = next(d for d in documentos if d["id"] == v1["id"])
    assert anterior["status"] == "obsoleto"
    assert anterior["is_current"] is False
    assert anterior["superseded_at"] is not None


def test_listagem_pode_ocultar_obsoletos(client, engineer_headers, project, upload_dir):
    v1 = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    _upload(
        client, engineer_headers, project["id"], "planta.pdf",
        version="v2.0", supersedes_id=v1["id"],
    )

    vigentes = client.get(
        f"/api/v1/projects/{project['id']}/documents?include_obsolete=false",
        headers=engineer_headers,
    ).json()
    assert len(vigentes) == 1
    assert vigentes[0]["version"] == "v2.0"


def test_documento_obsoleto_nao_alimenta_analise(
    client, engineer_headers, project, upload_dir
):
    """§8.3 — bloqueio de versão obsoleta."""
    v1 = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    _upload(
        client, engineer_headers, project["id"], "planta.pdf",
        version="v2.0", supersedes_id=v1["id"],
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/documents/{v1['id']}/extract",
        headers=engineer_headers,
    )
    assert response.status_code == 409
    assert "obsoleto" in response.json()["detail"]


def test_documento_vincula_a_versao_do_projeto(
    client, engineer_headers, project, upload_dir
):
    body = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    assert body["project_version_id"] == project["current_version"]["id"]


def test_marcar_obsoleto_manualmente(client, engineer_headers, project, upload_dir):
    documento = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    response = client.post(
        f"/api/v1/documents/{documento['id']}/obsolete", headers=engineer_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "obsoleto"


# --- QR Code (§8.3) ----------------------------------------------------------

def test_qrcode_do_documento(client, engineer_headers, project, upload_dir):
    documento = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    response = client.get(
        f"/api/v1/documents/{documento['id']}/qrcode", headers=engineer_headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["X-Atlas-Document-Status"] == "vigente"
    assert b"<svg" in response.content


def test_qrcode_de_outro_tenant_responde_404(
    client, db_session, engineer_headers, project, upload_dir
):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user

    documento = _upload(client, engineer_headers, project["id"], "planta.pdf").json()

    outra_org = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra_org, UserRole.OWNER, "intruso-qr@atlas-qa.com")

    response = client.get(
        f"/api/v1/documents/{documento['id']}/qrcode",
        headers=auth_headers(client, intruso.email),
    )
    assert response.status_code == 404


# --- Extração ----------------------------------------------------------------

def test_extracao_de_documento_sem_texto_nao_inventa_valores(
    client, engineer_headers, project, upload_dir
):
    documento = _upload(
        client, engineer_headers, project["id"], "prancha.pdf", b"%PDF-1.4 sem texto"
    ).json()

    body = client.post(
        f"/api/v1/projects/{project['id']}/documents/{documento['id']}/extract",
        headers=engineer_headers,
    ).json()

    assert body["status"] == "nao_verificavel"
    assert all(value is None for value in body["extracted_parameters"].values())
    assert body["warnings"]
