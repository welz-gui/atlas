import os
import hashlib
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import Project, Document
from app.schemas.domain import DocumentResponse
from app.services.pdf_parser import PDFPlanParser

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/projects/{project_id}/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: str,
    title: str = Form(...),
    category: str = Form("projeto_arquitetonico"),
    version: str = Form("v1.0"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    
    # Calculate SHA-256 Hash of document for auditability & baseline integrity
    sha256_hash = hashlib.sha256(content).hexdigest()

    # Save file safely to uploads directory
    safe_filename = f"{project_id}_{version}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    db_doc = Document(
        project_id=project_id,
        title=title,
        category=category,
        version=version,
        file_path=file_path,
        hash_sha256=sha256_hash,
        status="vigente"
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

@router.post("/projects/{project_id}/documents/{document_id}/extract")
def extract_document_parameters(project_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.project_id == project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content_bytes = b""
    if os.path.exists(doc.file_path):
        with open(doc.file_path, "rb") as f:
            content_bytes = f.read()

    extracted = PDFPlanParser.parse_file(content_bytes, doc.title)
    return {
        "document_id": doc.id,
        "document_title": doc.title,
        "extracted_parameters": extracted
    }
