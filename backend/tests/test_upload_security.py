"""Upload de documentos: o nome enviado pelo cliente é dado hostil."""

import io
import os

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import documents as documents_module
from app.core.database import Base, get_db
from app.main import app
from app.models.domain import Organization, Project


@pytest.fixture
def client(db_session, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(documents_module, "UPLOAD_DIR", str(upload_dir))

    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app), upload_dir
    app.dependency_overrides.clear()


@pytest.fixture
def project(db_session):
    org = Organization(name="Org Upload")
    db_session.add(org)
    db_session.commit()
    project = Project(organization_id=org.id, name="Projeto Upload")
    db_session.add(project)
    db_session.commit()
    return project


def _upload(client, project_id, filename, content=b"%PDF-1.4 conteudo"):
    return client.post(
        f"/api/v1/projects/{project_id}/documents/upload",
        data={"title": "Prancha", "category": "projeto_arquitetonico", "version": "v1.0"},
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
    )


def test_path_traversal_nao_escapa_do_diretorio(client, project, tmp_path):
    """Regressão: o protótipo montava o caminho com file.filename cru."""
    test_client, upload_dir = client
    response = _upload(test_client, project.id, "../../../../tmp/atlas_escape.pdf")

    assert response.status_code == 201
    stored = response.json()["file_path"]

    # O nome gravado é opaco e não carrega nenhum componente de caminho.
    assert "/" not in stored and "\\" not in stored and ".." not in stored
    assert os.path.dirname(os.path.abspath(os.path.join(upload_dir, stored))) == str(upload_dir)
    assert os.path.exists(os.path.join(upload_dir, stored))
    assert not os.path.exists("/tmp/atlas_escape.pdf")

    # O nome original é preservado como metadado, sem tocar o disco.
    assert response.json()["original_filename"] == "atlas_escape.pdf"


def test_extensao_fora_da_allowlist_e_recusada(client, project):
    test_client, _ = client
    response = _upload(test_client, project.id, "payload.sh", b"#!/bin/sh\nrm -rf /")
    assert response.status_code == 415


def test_arquivo_sem_extensao_e_recusado(client, project):
    test_client, _ = client
    assert _upload(test_client, project.id, "arquivo").status_code == 415


def test_arquivo_vazio_e_recusado(client, project):
    test_client, _ = client
    assert _upload(test_client, project.id, "vazio.pdf", b"").status_code == 400


def test_upload_acima_do_limite_e_recusado(client, project, monkeypatch):
    from app.core.config import settings

    test_client, upload_dir = client
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    response = _upload(test_client, project.id, "grande.pdf", b"x" * (2 * 1024 * 1024))

    assert response.status_code == 413
    # O arquivo parcial não pode ficar para trás.
    assert list(upload_dir.iterdir()) == []


def test_hash_e_tamanho_sao_registrados(client, project):
    import hashlib

    test_client, _ = client
    content = b"%PDF-1.4 conteudo para auditoria"
    response = _upload(test_client, project.id, "prancha.pdf", content)

    body = response.json()
    assert body["hash_sha256"] == hashlib.sha256(content).hexdigest()
    assert body["size_bytes"] == len(content)
