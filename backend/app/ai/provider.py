"""Provedores de modelo de linguagem (§6.8).

A camada é abstrata por uma razão prática, não por gosto por interfaces: o
Atlas precisa funcionar — e dizer a verdade sobre si — em três situações
diferentes.

1. **Sem provedor configurado.** É o padrão. `NullProvider` não chama modelo
   algum e responde com uma recusa explícita. O assistente continua útil
   porque o serviço cai para a busca determinística sobre o catálogo, e diz ao
   usuário que foi isso que aconteceu.
2. **Com a API da Anthropic.** `AnthropicProvider` usa `claude-opus-5` com
   raciocínio adaptativo e saída estruturada validada por Pydantic.
3. **Em teste.** Um provedor de mentira entra pela mesma porta, sem
   monkeypatch em cliente HTTP.

Nenhum provedor decide nada sozinho: quem confere as citações contra o catálogo
e grava a proveniência é `app.ai.service`.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("atlas.ai")


class AIUnavailable(RuntimeError):
    """Nenhum modelo respondeu. Nunca deve ser confundido com 'não há resposta'."""


@dataclass
class AIResult:
    """O que voltou do provedor, antes de qualquer conferência."""

    parsed: Optional[BaseModel] = None
    text: Optional[str] = None
    model: Optional[str] = None
    provider: str = "none"
    stop_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    refused: bool = False
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.parsed is not None and not self.refused and self.error is None


class AIProvider(ABC):
    name: str
    #: Falso quando não há modelo por trás — o serviço usa isso para escolher
    #: entre chamar o modelo e cair na busca determinística.
    available: bool = False

    @abstractmethod
    def complete(
        self,
        system: str,
        prompt: str,
        output_model: Type[BaseModel],
        max_tokens: int = 2048,
        cacheable_prefix: Optional[str] = None,
    ) -> AIResult:
        ...

    def describe(self) -> str:
        return self.name


class NullProvider(AIProvider):
    """Ausência de modelo, declarada."""

    name = "none"
    available = False

    def complete(self, system, prompt, output_model, max_tokens=2048, cacheable_prefix=None):
        return AIResult(
            provider=self.name,
            error=(
                "Nenhum provedor de modelo configurado (AI_PROVIDER=none). "
                "As respostas vêm da busca determinística sobre o catálogo."
            ),
        )

    def describe(self) -> str:
        return "nenhum modelo configurado — busca determinística no catálogo"


class AnthropicProvider(AIProvider):
    """API da Anthropic com saída estruturada.

    Escolhas que valem registro:

    - **raciocínio adaptativo** (`thinking={"type": "adaptive"}`): a extração de
      regra a partir de texto legal é justamente o tipo de tarefa em que vale
      pensar antes de responder;
    - **sem `temperature`**: além de o parâmetro ser rejeitado pelos modelos
      atuais, variar amostragem numa tarefa cuja saída vai para conferência
      humana só produziria diferença entre execuções idênticas;
    - **`messages.parse`** com o modelo Pydantic: o que não couber no contrato
      não vira resposta;
    - **cache de prompt** no prefixo do sistema, que é longo e se repete a cada
      consulta.
    """

    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, client=None):
        self.api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self.model = model or settings.AI_MODEL
        self._client = client
        self.available = bool(self.api_key) or client is not None

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise AIUnavailable(
                    "AI_PROVIDER=anthropic exige ANTHROPIC_API_KEY configurada."
                )
            try:
                import anthropic  # noqa: PLC0415 — dependência opcional
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise AIUnavailable(
                    "AI_PROVIDER=anthropic exige o pacote anthropic instalado."
                ) from exc
            self._client = anthropic.Anthropic(
                api_key=self.api_key, timeout=settings.AI_TIMEOUT_SECONDS
            )
        return self._client

    def complete(
        self,
        system: str,
        prompt: str,
        output_model: Type[BaseModel],
        max_tokens: int = 2048,
        cacheable_prefix: Optional[str] = None,
    ) -> AIResult:
        import anthropic

        # O prefixo estável (instruções e política) vai num bloco marcado para
        # cache; o que muda a cada consulta fica fora dele.
        system_blocks = []
        if cacheable_prefix:
            system_blocks.append(
                {
                    "type": "text",
                    "text": cacheable_prefix,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        system_blocks.append({"type": "text", "text": system})

        started = time.monotonic()
        try:
            message = self.client.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system_blocks,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "adaptive"},
                output_format=output_model,
            )
        except anthropic.RateLimitError as exc:
            return self._failure("Limite de requisições do provedor atingido.", exc, started)
        except anthropic.APIConnectionError as exc:
            return self._failure("Não foi possível alcançar o provedor.", exc, started)
        except anthropic.APIStatusError as exc:
            return self._failure(
                f"O provedor respondeu com erro {exc.status_code}.", exc, started
            )
        except Exception as exc:  # noqa: BLE001 — falha de IA nunca derruba o request
            return self._failure("Falha inesperada ao consultar o provedor.", exc, started)

        latency = int((time.monotonic() - started) * 1000)
        usage = getattr(message, "usage", None)

        # Recusa do modelo é resposta legítima e precisa chegar como tal: sem
        # ela, uma recusa viraria "erro" e o usuário nunca saberia o motivo.
        if getattr(message, "stop_reason", None) == "refusal":
            return AIResult(
                provider=self.name,
                model=self.model,
                stop_reason="refusal",
                refused=True,
                latency_ms=latency,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                error="O modelo recusou-se a responder a esta solicitação.",
            )

        return AIResult(
            parsed=getattr(message, "parsed_output", None),
            model=self.model,
            provider=self.name,
            stop_reason=getattr(message, "stop_reason", None),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            latency_ms=latency,
        )

    def _failure(self, message: str, exc: Exception, started: float) -> AIResult:
        logger.warning("%s (%s: %s)", message, type(exc).__name__, exc)
        return AIResult(
            provider=self.name,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            error=f"{message} ({type(exc).__name__})",
        )

    def describe(self) -> str:
        return f"anthropic ({self.model})"


_PROVIDERS = {"none": NullProvider, "anthropic": AnthropicProvider}


@lru_cache(maxsize=1)
def get_provider() -> AIProvider:
    choice = (settings.AI_PROVIDER or "none").strip().lower()
    factory = _PROVIDERS.get(choice)
    if factory is None:
        raise RuntimeError(
            f"AI_PROVIDER='{choice}' desconhecido. "
            f"Valores aceitos: {', '.join(sorted(_PROVIDERS))}."
        )
    return factory()


def reset_provider_cache() -> None:
    get_provider.cache_clear()
