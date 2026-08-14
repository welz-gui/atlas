"""Organização corrente da requisição, para a RLS (§3.1, §12 — item D1).

A política de RLS compara `organization_id` com `current_setting(
'atlas.organization_id')`. Alguém precisa preencher esse ajuste por transação, e
esse alguém é este módulo: uma `ContextVar` que a camada de API preenche a
partir do token e o worker preenche a partir do registro do trabalho.

**Por que `ContextVar` e não uma variável global.** O FastAPI atende requisições
concorrentes na mesma thread, alternando entre elas nos pontos de espera. Uma
global vazaria a organização de uma requisição para outra — que é exatamente o
vazamento que a RLS existe para impedir. `ContextVar` isola por contexto de
execução.

**Limpar é obrigatório.** Um contexto que termina sem `reset` deixa a
organização pendurada para o próximo trabalho que reaproveitar aquele contexto.
Use `organization_scope`, que garante o `reset` mesmo em caso de exceção.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_current_organization: ContextVar[Optional[str]] = ContextVar(
    "atlas_current_organization", default=None
)


def current_organization_id() -> Optional[str]:
    """Organização em vigor, ou `None` quando não há contexto de tenant."""
    return _current_organization.get()


def set_current_organization(organization_id: Optional[str]):
    """Define a organização e devolve o token para desfazer."""
    return _current_organization.set(organization_id)


def reset_current_organization(token) -> None:
    _current_organization.reset(token)


@contextmanager
def organization_scope(organization_id: Optional[str]) -> Iterator[None]:
    """Vigora a organização no bloco e a desfaz ao sair, inclusive em exceção."""
    token = set_current_organization(organization_id)
    try:
        yield
    finally:
        reset_current_organization(token)
