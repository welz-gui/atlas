"""Gestão documental (§8.3): versionamento, documento vigente e QR Code."""

import hashlib
import io
import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_project_or_404,
    get_scoped_or_404,
    require_permission,
    tenant_query,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.domain import Document, DocumentState, User
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
    supersedes_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(require_permission("document:write")),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id, user)

    superseded: Optional[Document] = None
    if supersedes_id:
        superseded = (
            tenant_query(db, Document, user)
            .filter(Document.id == supersedes_id, Document.project_id == project_id)
            .first()
        )
        if not superseded:
            raise HTTPException(
                status_code=404, detail="Documento a ser substituído não encontrado."
            )

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

    document = Document(
        organization_id=user.organization_id,
        project_id=project_id,
        project_version_id=project.current_version.id if project.current_version else None,
        title=title,
        category=category,
        version=version,
        file_path=stored_name,
        original_filename=original_filename or None,
        content_type=file.content_type,
        size_bytes=size,
        hash_sha256=digest.hexdigest(),
        status=DocumentState.VIGENTE,
        supersedes_id=superseded.id if superseded else None,
        uploaded_by_id=user.id,
    )
    db.add(document)

    # A versão anterior sai de circulação no mesmo ato (§8.3 — bloqueio de
    # versão obsoleta). Duas versões vigentes do mesmo documento seriam uma
    # ambiguidade perigosa em obra.
    if superseded:
        superseded.status = DocumentState.OBSOLETO
        superseded.superseded_at = datetime.utcnow()

    db.commit()
    db.refresh(document)
    return document


@router.get("/projects/{project_id}/documents", response_model=List[DocumentResponse])
def list_project_documents(
    project_id: str,
    include_obsolete: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id, user)
    query = tenant_query(db, Document, user).filter(Document.project_id == project_id)
    if not include_obsolete:
        query = query.filter(Document.status != DocumentState.OBSOLETO)
    return query.order_by(Document.created_at.desc()).all()


@router.post("/documents/{document_id}/obsolete", response_model=DocumentResponse)
def mark_document_obsolete(
    document_id: str,
    user: User = Depends(require_permission("document:write")),
    db: Session = Depends(get_db),
):
    document = get_scoped_or_404(db, Document, document_id, user, "Documento")
    document.status = DocumentState.OBSOLETO
    document.superseded_at = datetime.utcnow()
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents/{document_id}/qrcode")
def document_qrcode(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """QR Code de verificação do documento (§8.3).

    Codifica identificador, versão, situação e hash — de modo que quem estiver
    com a prancha impressa em obra possa conferir se ainda é a versão vigente.
    """
    import qrcode
    import qrcode.image.svg

    document = get_scoped_or_404(db, Document, document_id, user, "Documento")

    payload = (
        f"{settings.PUBLIC_BASE_URL}/verificar/documento/{document.id}"
        f"?v={document.version}&s={document.status}&h={(document.hash_sha256 or '')[:16]}"
    )
    image = qrcode.make(payload, image_factory=qrcode.image.svg.SvgImage)
    buffer = io.BytesIO()
    image.save(buffer)

    return Response(
        content=buffer.getvalue(),
        media_type="image/svg+xml",
        headers={
            "X-Atlas-Document-Status": document.status,
            "X-Atlas-Document-Version": document.version,
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/projects/{project_id}/documents/{document_id}/extract",
    response_model=ExtractionResponse,
)
def extract_document_parameters(
    project_id: str,
    document_id: str,
    user: User = Depends(require_permission("document:read")),
    db: Session = Depends(get_db),
):
    """Extração assistida — nunca devolve um valor que não estava no documento."""
    get_project_or_404(db, project_id, user)
    document = (
        tenant_query(db, Document, user)
        .filter(Document.id == document_id, Document.project_id == project_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    if document.status == DocumentState.OBSOLETO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este documento está marcado como obsoleto e não pode alimentar uma "
                "análise. Use a versão vigente."
            ),
        )

    # `file_path` guarda apenas o nome interno; o diretório vem da configuração.
    stored_path = os.path.join(UPLOAD_DIR, os.path.basename(document.file_path))
    if not os.path.exists(stored_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo do documento não está mais disponível no armazenamento.",
        )

    with open(stored_path, "rb") as handle:
        content_bytes = handle.read()

    result = PDFPlanParser.parse_file(
        content_bytes, document.original_filename or document.title
    )

    parameters = {
        key: result.get(key)
        for key in (
            "lot_area", "built_area", "front_setback",
            "rear_setback", "permeability_rate", "floors",
        )
    }

    return ExtractionResponse(
        document_id=document.id,
        document_title=document.title,
        status=result["status"],
        fields_found=result["fields_found"],
        fields_expected=result["fields_expected"],
        extracted_parameters=parameters,
        evidence=result.get("evidence") or [],
        warnings=result.get("warnings") or [],
    )
