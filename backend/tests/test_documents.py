import hashlib
import io
from app.models.domain import Organization, Project, Document

def test_document_hash_sha256_generation(db_session):
    org = Organization(name="Org Test Document")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Projeto Teste Documento",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar"
    )
    db_session.add(project)
    db_session.commit()

    file_bytes = b"PDF Conteudo de Teste para Auditoria SHA-256"
    expected_hash = hashlib.sha256(file_bytes).hexdigest()

    doc = Document(
        project_id=project.id,
        title="Memorial Descritivo",
        category="memorial",
        version="v1.0",
        file_path="uploads/test.pdf",
        hash_sha256=expected_hash,
        status="vigente"
    )
    db_session.add(doc)
    db_session.commit()

    fetched_doc = db_session.query(Document).filter(Document.id == doc.id).first()
    assert fetched_doc is not None
    assert fetched_doc.hash_sha256 == expected_hash
    assert len(fetched_doc.hash_sha256) == 64 # SHA-256 length in hex
