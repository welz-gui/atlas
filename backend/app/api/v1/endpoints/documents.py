import hashlib
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.domain import Document, Project
from app.schemas.domain import DocumentResponse, ExtractionResponse
from app.services.pdf_parser import PDFPlanParser

router = APIRouter()

UPLOAD_DIR = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)

#: Extensões aceitas. O nome enviado pelo cliente nunca é usado no disco; a
#: extensão serve apenas para triagem e para nomear o arquivo interno.
ALLOWED_EXTENSIONS = {
    ".pdf", ".dxf", ".ifc", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".webp",
    ".xlsx", ".xls", ".docx", ".doc",
}

CHUNK_SIZE = 1024 * 1024


@router.post(
    "/projects/{project_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: str,
    title: str = Form(...),
    category: str = Form("projeto_arquitetonico"),
    version: str = Form("v1.0"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # O nome enviado pelo cliente é tratado como dado hostil: dele só se
    # aproveita a extensão, e ainda assim contra uma allowlist. O arquivo em
    # disco recebe um nome opaco gerado pelo servidor, de modo que sequências
    # como "../" não têm efeito algum sobre o caminho final.
    original_filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(original_filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Extensão '{extension or 'desconhecida'}' não permitida. "
                f"Aceitas: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    stored_name = f"{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(UPLOAD_DIR, stored_name)

    # Grava em streaming, abortando ao ultrapassar o limite — evita carregar
    # um arquivo arbitrariamente grande na memória.
    digest = hashlib.sha256()
    size = 0
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    try:
        with open(file_path, "wb") as handle:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Arquivo excede o limite de {settings.MAX_UPLOAD_MB} MB.",
                    )
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    if size == 0:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    db_doc = Document(
        project_id=project_id,
        title=title,
        category=category,
        version=version,
        file_path=stored_name,
        original_filename=original_filename or None,
        content_type=file.content_type,
        size_bytes=size,
        hash_sha256=digest.hexdigest(),
        status="vigente",
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return db_doc


@router.get("/projects/{project_id}/documents", response_model=List[DocumentResponse])
def list_project_documents(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(Document).filter(Document.project_id == project_id).all()


@router.post(
    "/projects/{project_id}/documents/{document_id}/extract",
    response_model=ExtractionResponse,
)
def extract_document_parameters(
    project_id: str, document_id: str, db: Session = Depends(get_db)
):
    """Extração assistida — nunca devolve um valor que não estava no documento."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.project_id == project_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # `file_path` guarda apenas o nome interno; o diretório vem da configuração.
    stored_path = os.path.join(UPLOAD_DIR, os.path.basename(doc.file_path))
    if not os.path.exists(stored_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo do documento não está mais disponível no armazenamento.",
        )

    with open(stored_path, "rb") as handle:
        content_bytes = handle.read()

    result = PDFPlanParser.parse_file(content_bytes, doc.original_filename or doc.title)

    parameters = {
        key: result.get(key)
        for key in (
            "lot_area", "built_area", "front_setback",
            "rear_setback", "permeability_rate", "floors",
        )
    }

    return ExtractionResponse(
        document_id=doc.id,
        document_title=doc.title,
        status=result["status"],
        fields_found=result["fields_found"],
        fields_expected=result["fields_expected"],
        extracted_parameters=parameters,
        evidence=result.get("evidence") or [],
        warnings=result.get("warnings") or [],
    )
