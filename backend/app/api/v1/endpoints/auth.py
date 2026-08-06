"""Autenticação, cadastro inicial e gestão de usuários (§8.1)."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission, tenant_query
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.domain import Organization, User, UserRole
from app.schemas.domain import (
    LoginRequest,
    OrganizationResponse,
    SignupRequest,
    Token,
    UserCreate,
    UserResponse,
)

router = APIRouter()


def _issue_token(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id, user.organization_id, user.role),
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post("/auth/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Cria uma organização e seu primeiro usuário, com papel `owner`."""
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com este e-mail.",
        )

    organization = Organization(
        name=payload.organization_name, document_number=payload.organization_document
    )
    db.add(organization)
    db.flush()

    user = User(
        organization_id=organization.id,
        name=payload.name,
        email=email,
        role=UserRole.OWNER,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_token(user)


@router.post("/auth/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()

    # Mesma resposta para e-mail inexistente e senha errada: distinguir os dois
    # entrega ao atacante a lista de e-mails cadastrados.
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Usuário desativado."
        )

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.get("/auth/me", response_model=UserResponse)
def read_current_user(user: User = Depends(get_current_user)):
    return user


@router.get("/auth/organization", response_model=OrganizationResponse)
def read_current_organization(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.query(Organization).filter(Organization.id == user.organization_id).one()


@router.get("/users", response_model=List[UserResponse])
def list_users(
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    return tenant_query(db, User, user).all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    if payload.role not in UserRole.ALL:
        raise HTTPException(
            status_code=422,
            detail=f"Papel inválido. Válidos: {', '.join(sorted(UserRole.ALL))}",
        )

    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com este e-mail.",
        )

    new_user = User(
        organization_id=user.organization_id,
        name=payload.name,
        email=email,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: str,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    target = tenant_query(db, User, user).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if target.id == user.id:
        raise HTTPException(
            status_code=400, detail="Não é possível desativar o próprio usuário."
        )

    target.is_active = False
    db.commit()
    db.refresh(target)
    return target
