"""Dependências de autenticação e isolamento por organização (§3.1).

Nenhum endpoint de negócio deve consultar o banco sem passar por aqui. As
funções `tenant_query` e `get_project_or_404` existem para que o filtro por
organização seja o caminho mais curto — e não algo que se possa esquecer.
"""

from __future__ import annotations

from typing import Optional, Type, TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Query, Session

from app.core.database import get_db
from app.core.security import decode_access_token, role_has_permission
from app.core.tenant import set_current_organization
from app.models.domain import Project, User

bearer_scheme = HTTPBearer(auto_error=False)

ModelT = TypeVar("ModelT")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais ausentes ou inválidas.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR

    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise CREDENTIALS_ERROR

    # A organização entra em vigor **antes** da primeira consulta, porque a
    # política de RLS já se aplica a ela (§3.1, D1). A fonte é o token
    # assinado; a conferência contra o registro vem logo abaixo, de modo que um
    # token com organização trocada não passa daqui.
    #
    # Não há `reset` neste ponto de propósito: o valor precisa continuar em
    # vigor durante todo o tratamento da requisição. Quem limpa é o middleware
    # `tenant_scope` em `app/main.py`.
    set_current_organization(payload.get("org"))

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR

    # O token carrega a organização, mas quem manda é o registro atual: se o
    # usuário mudou de organização, o token antigo não pode continuar valendo
    # para a anterior.
    if payload.get("org") != user.organization_id:
        raise CREDENTIALS_ERROR

    return user


def require_permission(permission: str):
    """Fábrica de dependência que exige uma permissão da matriz de papéis."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not role_has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"O papel '{user.role}' não tem permissão para '{permission}'."
                ),
            )
        return user

    return dependency


def tenant_query(db: Session, model: Type[ModelT], user: User) -> Query:
    """Consulta já restrita à organização do usuário.

    Toda entidade de negócio tem `organization_id` justamente para que esta
    função sirva a todas elas.
    """
    return db.query(model).filter(model.organization_id == user.organization_id)


def get_project_or_404(db: Session, project_id: str, user: User) -> Project:
    """Busca um projeto dentro do tenant.

    Projeto de outra organização responde 404, não 403: informar que o
    recurso existe já é vazamento entre tenants.
    """
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.organization_id == user.organization_id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Empreendimento não encontrado.")
    return project


def get_scoped_or_404(
    db: Session, model: Type[ModelT], object_id: str, user: User, label: str = "Recurso"
) -> ModelT:
    instance = (
        db.query(model)
        .filter(model.id == object_id, model.organization_id == user.organization_id)
        .first()
    )
    if not instance:
        raise HTTPException(status_code=404, detail=f"{label} não encontrado.")
    return instance
