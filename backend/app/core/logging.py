"""Log estruturado, com correlação e sem vazamento (§12 — observabilidade).

Até aqui a API não tinha logging configurado: só o worker chamava
`basicConfig`. Falha em produção chegaria por relato de cliente, sem nada do
lado do servidor para cruzar com o relato.

Três decisões, e todas vêm de invariantes que este projeto já sustenta:

**1. JSON, não texto.** Um log de linha livre serve para ler no terminal e não
serve para procurar. Em JSON, "todas as requisições da organização X que
falharam" é uma consulta, não uma leitura.

**2. Identificador por requisição, devolvido ao cliente.** O `X-Request-Id`
volta no cabeçalho, de modo que o relato de quem viu o erro carregue a chave
que encontra a linha do servidor. Sem isso, "deu erro ontem à tarde" é tudo o
que se tem.

**3. O log não é lugar de segredo nem de dado pessoal.** `docs/LGPD.md`
registra que a pergunta feita ao assistente pode conter dado pessoal, e
`core/config.py` já redige segredos no `repr`. Aqui a redação é ativa: campos
com nome suspeito saem como `***`, e o corpo das requisições nunca é
registrado.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

#: Identificador da requisição corrente. `ContextVar` pelo mesmo motivo do
#: tenant: o FastAPI atende requisições concorrentes na mesma thread, e uma
#: global misturaria as linhas de duas delas.
_request_id: ContextVar[Optional[str]] = ContextVar("atlas_request_id", default=None)

#: Trechos de nome de campo que nunca aparecem em log, mesmo que alguém os
#: passe em `extra`. A lista é de prefixos/substrings porque o erro comum é
#: `user_password`, não `password`.
SENSITIVE_HINTS = (
    "password",
    "senha",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "mfa",
    "recovery",
    "prompt",
    "cpf",
    "document_number",
    "owner_document",
)

REDACTED = "***"


def current_request_id() -> Optional[str]:
    return _request_id.get()


def set_request_id(request_id: Optional[str]):
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def _is_sensitive(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in SENSITIVE_HINTS)


def redact(payload: dict) -> dict:
    """Substitui por `***` o que não deve chegar ao log.

    Recursivo, porque o campo perigoso costuma estar aninhado — o `payload` de
    um trabalho, por exemplo.
    """
    limpo: dict[str, Any] = {}
    for chave, valor in payload.items():
        if _is_sensitive(str(chave)):
            limpo[chave] = REDACTED
        elif isinstance(valor, dict):
            limpo[chave] = redact(valor)
        else:
            limpo[chave] = valor
    return limpo


#: Atributos que o `logging` põe em todo registro e que não interessam no JSON.
_STANDARD = {
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message", "msg",
    "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Uma linha, um objeto JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = current_request_id()
        if request_id:
            payload["request_id"] = request_id

        extras = {
            chave: valor
            for chave, valor in record.__dict__.items()
            if chave not in _STANDARD and not chave.startswith("_")
        }
        payload.update(redact(extras))

        if record.exc_info:
            # O traceback ajuda a diagnosticar; a mensagem da exceção pode
            # carregar dado, então vai junto do resto pela mesma redação.
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Instala o formatador JSON na raiz, uma única vez.

    Idempotente: chamar duas vezes não duplica handler, o que aconteceria em
    recarga do servidor de desenvolvimento e produziria cada linha em dobro.
    """
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(level.upper())

    # O uvicorn instala os próprios handlers; sem isto, cada requisição sairia
    # duas vezes — uma em JSON e outra no formato dele.
    for nome in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(nome)
        logger.handlers = []
        logger.propagate = True
