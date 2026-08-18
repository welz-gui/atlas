"""Autenticação, cadastro inicial e gestão de usuários (§8.1)."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission, tenant_query
from app.core.config import settings
from app.core import mfa
from app.core.database import get_db
from app.core.security import (
    MFA_REQUIRED_PERMISSIONS,
    create_access_token,
    hash_password,
    role_has_permission,
    verify_password,
)
from app.models.domain import MFARecoveryCode, Organization, User, UserRole
from app.schemas.domain import (
    MFAActivateRequest,
    MFAActivateResponse,
    MFADisableRequest,
    MFAEnrollResponse,
    MFAStatusResponse,
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

    # Segundo fator, para quem o tem ativo (§8.1, D2). Quem não cadastrou entra
    # normalmente — e esbarra na exigência ao tentar publicar regra ou gerir a
    # organização, que é onde ela recai.
    if user.mfa_active:
        if not payload.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código do segundo fator é obrigatório para esta conta.",
                headers={"X-Atlas-MFA-Required": "true"},
            )
        if not consume_second_factor(db, user, payload.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código do segundo fator inválido ou já utilizado.",
                headers={"X-Atlas-MFA-Required": "true"},
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


# =============================================================================
# Segundo fator (§8.1, §12 — D2)
# =============================================================================


def consume_second_factor(db: Session, user: User, code: str) -> bool:
    """Confere um código TOTP ou de recuperação, consumindo o segundo.

    A ordem importa: tenta o TOTP primeiro, porque é o caminho comum e não
    gasta nada. Só depois procura entre os códigos de recuperação, e o que
    casar é marcado como usado na mesma transação — código de recuperação
    reutilizável é uma senha permanente com nome bonito.
    """
    secret = mfa.decrypt_secret(user.mfa_secret) if user.mfa_secret else None
    if secret and mfa.verify_code(secret, code):
        # Migra o segredo para a chave atual quando ele ainda estava na
        # anterior. É assim que a janela de rotação se fecha sozinha: cada
        # pessoa que entra leva o próprio segredo adiante, e `SECRET_KEY_PREVIOUS`
        # pode ser removida quando não restar quem dependa dela.
        recifrado = mfa.rotate_secret(user.mfa_secret)
        if recifrado and recifrado != user.mfa_secret:
            user.mfa_secret = recifrado
            db.commit()
        return True

    for recovery in user.recovery_codes:
        if recovery.used_at is None and mfa.verify_recovery_code(
            code, recovery.code_hash
        ):
            recovery.used_at = datetime.utcnow()
            db.commit()
            return True
    return False


@router.post("/auth/mfa/enroll", response_model=MFAEnrollResponse)
def enroll_mfa(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Gera um segredo TOTP. **Ainda não** ativa o segundo fator.

    Recadastrar sobrescreve o segredo anterior e só passa a valer após a
    confirmação — de modo que um cadastro interrompido não derrube o fator que
    já funcionava.
    """
    if user.mfa_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Segundo fator já está ativo. Remova-o em "
                "POST /auth/mfa/disable antes de cadastrar outro."
            ),
        )

    secret = mfa.generate_secret()
    user.mfa_secret = mfa.encrypt_secret(secret)
    user.mfa_activated_at = None
    db.commit()

    return MFAEnrollResponse(
        secret=secret,
        provisioning_uri=mfa.provisioning_uri(secret, user.email),
    )


@router.post("/auth/mfa/activate", response_model=MFAActivateResponse)
def activate_mfa(
    payload: MFAActivateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirma o cadastro com um código e entrega os códigos de recuperação.

    Os códigos aparecem **uma única vez**: o banco guarda apenas o hash.
    """
    if user.mfa_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Segundo fator já ativo."
        )
    if not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum cadastro em andamento. Comece por POST /auth/mfa/enroll.",
        )

    secret = mfa.decrypt_secret(user.mfa_secret)
    if secret is None or not mfa.verify_code(secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Código inválido."
        )

    user.mfa_activated_at = datetime.utcnow()

    # Cadastro novo zera os códigos anteriores: deixá-los válidos manteria de pé
    # a recuperação de um fator que já não existe.
    for antigo in list(user.recovery_codes):
        db.delete(antigo)

    codigos = mfa.generate_recovery_codes()
    for codigo in codigos:
        db.add(MFARecoveryCode(user_id=user.id, code_hash=mfa.hash_recovery_code(codigo)))
    db.commit()

    return MFAActivateResponse(
        activated_at=user.mfa_activated_at, recovery_codes=codigos
    )


@router.get("/auth/mfa/status", response_model=MFAStatusResponse)
def mfa_status(user: User = Depends(get_current_user)):
    restantes = (
        sum(1 for c in user.recovery_codes if c.used_at is None)
        if user.mfa_active
        else None
    )
    return MFAStatusResponse(
        active=user.mfa_active,
        activated_at=user.mfa_activated_at,
        required_for_role=any(
            role_has_permission(user.role, p) for p in MFA_REQUIRED_PERMISSIONS
        ),
        recovery_codes_remaining=restantes,
    )


@router.post("/auth/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_mfa(
    payload: MFADisableRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove o segundo fator, exigindo prova de posse.

    Sem essa prova, uma sessão roubada bastaria para desligar o fator — o que
    tornaria o fator decorativo.
    """
    if not user.mfa_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Segundo fator não está ativo."
        )
    if not consume_second_factor(db, user, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Código inválido."
        )

    user.mfa_secret = None
    user.mfa_activated_at = None
    for codigo in list(user.recovery_codes):
        db.delete(codigo)
    db.commit()
