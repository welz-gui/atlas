"""Hash de senha, emissão de token e matriz de permissões (§8.1, §12)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.models.domain import UserRole

# argon2id como algoritmo primário; pbkdf2 permanece para verificar hashes
# antigos sem forçar redefinição de senha.
pwd_context = CryptContext(schemes=["argon2", "pbkdf2_sha256"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        # Hash malformado não deve derrubar a autenticação — apenas falhar.
        return False


def create_access_token(
    subject: str, organization_id: str, role: str, expires_minutes: Optional[int] = None
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: Dict[str, Any] = {
        "sub": subject,
        "org": organization_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Aceita a chave atual e, durante a janela, a anterior (§12).

    A assinatura de token novo usa **sempre** a chave atual; a anterior serve
    só para não derrubar quem já estava autenticado no instante da rotação.

    Quando `SECRET_KEY_PREVIOUS` for removida da configuração, os tokens
    remanescentes deixam de valer — que é o fim pretendido da janela.
    """
    for chave in (settings.SECRET_KEY, settings.SECRET_KEY_PREVIOUS):
        if not chave:
            continue
        try:
            return jwt.decode(token, chave, algorithms=[ALGORITHM])
        except jwt.PyJWTError:
            continue
    return None


# --- Permissões --------------------------------------------------------------

_ALL_ROLES = UserRole.ALL
_OPERATORS = {UserRole.OWNER, UserRole.ADMIN, UserRole.ENGINEER}

#: Quem pode fazer o quê. `client` é leitura apenas, por definição (§8.22).
PERMISSIONS: Dict[str, Set[str]] = {
    "org:manage": {UserRole.OWNER, UserRole.ADMIN},
    "project:read": _ALL_ROLES,
    "project:write": _OPERATORS,
    "project:baseline": _OPERATORS,
    "document:read": _ALL_ROLES,
    "document:write": _OPERATORS | {UserRole.INSPECTOR},
    "catalog:read": _ALL_ROLES,
    # §7.5 — publicar regra é ato técnico com responsável identificado.
    "catalog:validate": {UserRole.OWNER, UserRole.ADMIN, UserRole.VALIDATOR},
    "protocol:read": _ALL_ROLES,
    "protocol:write": _OPERATORS,
    "field:read": _ALL_ROLES,
    "field:write": _OPERATORS | {UserRole.INSPECTOR},
    # §11 — quem lê a métrica é quem responde pelo número. Fora daqui, de
    # propósito: `engineer`, `inspector` e `client`. Métrica de acerto do motor
    # é instrumento de decisão do negócio, não painel de obra.
    "metrics:read": {UserRole.OWNER, UserRole.ADMIN, UserRole.VALIDATOR},
}


#: Permissões que exigem segundo fator ativo (§8.1, §12 — D2).
#:
#: A exigência recai sobre a **ação**, não sobre o login. Bloquear a entrada de
#: quem ainda não cadastrou o MFA trancaria para fora todo `owner` e
#: `validator` existente no instante do deploy; exigir na ação deixa a pessoa
#: entrar, cadastrar e seguir.
#:
#: São as duas do §8.1: publicar regra e gerir a organização. `inspector` fica
#: de fora de propósito — telefone de canteiro com MFA é atrito que empurra
#: para senha compartilhada, que é pior que a ausência do fator.
MFA_REQUIRED_PERMISSIONS = {"org:manage", "catalog:validate"}


def permission_requires_mfa(permission: str) -> bool:
    return permission in MFA_REQUIRED_PERMISSIONS


def role_has_permission(role: str, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, set())
