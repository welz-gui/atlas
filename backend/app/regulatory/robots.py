"""Conformidade com `robots.txt` para a descoberta regulatória (§7.2).

O roadmap é explícito: *"respeite `robots.txt` e termos de uso dos portais
públicos. Dado público não é dado de coleta irrestrita; ritmo agressivo derruba
acesso e queima a fonte."* Este módulo é o que sustenta a primeira metade.

## Três decisões, e as evidências que as motivaram

**1. Só `text/plain` é `robots.txt`.** Verificado em 2026-08-13:

    GET https://www.lajeado.rs.gov.br/robots.txt
      → 200, Content-Type: text/html, corpo = shell do portal

O portal devolve **200 com HTML** para um caminho que não existe. Um parser
ingênuo recebe 200, tenta ler HTML como diretivas, não acha nenhuma válida e
conclui "tudo liberado" — conclusão certa, pelo motivo errado. Num site que de
fato tivesse regras, o mesmo código as ignoraria em silêncio. Daí a exigência de
tipo: sem `text/plain`, não há arquivo de regras, e isso fica registrado como
tal em vez de virar permissão silenciosa.

**2. Falha de servidor bloqueia; ausência libera.** Segue a RFC 9309: 4xx
significa "não existe arquivo de regras", e liberar é o comportamento correto;
5xx e 429 significam "não deu para perguntar", e aí a resposta é não buscar. É o
mesmo princípio do I10 — ausência de verificação não é aprovação.

**3. Intervalo mínimo entre buscas ao mesmo host.** `Crawl-delay`, quando
declarado, prevalece se for maior. Com dois índices isso é irrelevante; com
trinta municípios é a diferença entre coletar e ser bloqueado.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

#: Como o coletor se identifica. O mesmo token é usado para casar os grupos
#: `User-agent` do arquivo.
USER_AGENT = "Atlas-Regulatory-Discovery/1.0"

#: Piso de cortesia entre duas buscas ao mesmo host, em segundos. `Crawl-delay`
#: maior prevalece; menor não reduz o piso.
MIN_REQUEST_INTERVAL = 2.0

#: `robots.txt` acima disto não é `robots.txt`.
MAX_ROBOTS_BYTES = 512_000


class RobotsDenied(RuntimeError):
    """A busca foi recusada por `robots.txt` — ou por não ter sido possível lê-lo."""


@dataclass
class RobotsPolicy:
    """Regras em vigor para um host, com o porquê registrado.

    `reason` existe para que a decisão seja auditável: quem olhar o registro do
    trabalho precisa distinguir "não há arquivo" de "o arquivo proíbe".
    """

    origin: str
    #: `None` quando não há arquivo de regras aplicável.
    disallow: tuple[str, ...] = ()
    allow: tuple[str, ...] = ()
    crawl_delay: Optional[float] = None
    fetchable: bool = True
    reason: str = "sem arquivo de regras"
    fetched_at: float = field(default_factory=time.monotonic)

    def path_allowed(self, url: str) -> bool:
        """Regra mais específica vence, como manda a RFC 9309."""
        if not self.fetchable:
            return False

        path = urlparse(url).path or "/"
        melhor_allow = max(
            (len(rule) for rule in self.allow if path.startswith(rule)), default=-1
        )
        melhor_disallow = max(
            (len(rule) for rule in self.disallow if path.startswith(rule)), default=-1
        )
        if melhor_disallow < 0:
            return True
        return melhor_allow >= melhor_disallow

    @property
    def delay(self) -> float:
        if self.crawl_delay is None:
            return MIN_REQUEST_INTERVAL
        return max(self.crawl_delay, MIN_REQUEST_INTERVAL)


def parse_robots(texto: str, user_agent: str = USER_AGENT) -> dict:
    """Extrai as diretivas do grupo aplicável.

    Grupo nomeado para este agente prevalece sobre `*`, e só um dos dois é
    aplicado — acumular os dois inventaria uma regra que o arquivo não expressa.
    """
    grupos: dict[str, dict] = {}
    atuais: list[str] = []
    agente_esperando = False

    for linha_bruta in texto.splitlines():
        linha = linha_bruta.split("#", 1)[0].strip()
        if not linha or ":" not in linha:
            continue
        campo, _, valor = linha.partition(":")
        campo = campo.strip().lower()
        valor = valor.strip()

        if campo == "user-agent":
            if not agente_esperando:
                atuais = []
                agente_esperando = True
            atuais.append(valor.lower())
            grupos.setdefault(valor.lower(), {"allow": [], "disallow": [], "delay": None})
            continue

        agente_esperando = False
        if not atuais:
            continue

        for agente in atuais:
            grupo = grupos.setdefault(
                agente, {"allow": [], "disallow": [], "delay": None}
            )
            if campo == "disallow":
                # `Disallow:` vazio libera tudo — é permissão, não proibição.
                if valor:
                    grupo["disallow"].append(valor)
            elif campo == "allow" and valor:
                grupo["allow"].append(valor)
            elif campo == "crawl-delay":
                try:
                    grupo["delay"] = float(valor.replace(",", "."))
                except ValueError:
                    pass

    agente = user_agent.lower()
    escolhido = None
    for nome in grupos:
        if nome != "*" and nome in agente:
            escolhido = grupos[nome]
            break
    if escolhido is None:
        escolhido = grupos.get("*")

    if escolhido is None:
        return {"allow": (), "disallow": (), "delay": None}
    return {
        "allow": tuple(escolhido["allow"]),
        "disallow": tuple(escolhido["disallow"]),
        "delay": escolhido["delay"],
    }


def _abrir(url: str, timeout: int):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    return urlopen(request, timeout=timeout)  # noqa: S310 — origem vem do registro fixo


def load_policy(
    url: str,
    timeout: int = 15,
    opener: Callable[[str, int], object] = _abrir,
) -> RobotsPolicy:
    """Busca e interpreta o `robots.txt` da origem de `url`."""
    partes = urlparse(url)
    origem = f"{partes.scheme}://{partes.netloc}"
    robots_url = urljoin(origem, "/robots.txt")

    try:
        with opener(robots_url, timeout) as resposta:  # type: ignore[union-attr]
            status = getattr(resposta, "status", 200)
            content_type = resposta.headers.get("Content-Type", "") or ""

            # Ver decisão 1 no topo do módulo: 200 com HTML não é robots.txt.
            if "text/plain" not in content_type.lower():
                return RobotsPolicy(
                    origin=origem,
                    reason=(
                        f"resposta {status} sem `text/plain` "
                        f"({content_type or 'sem tipo declarado'}) — "
                        "a origem não publica robots.txt"
                    ),
                )

            corpo = resposta.read(MAX_ROBOTS_BYTES)
            charset = getattr(resposta.headers, "get_content_charset", lambda: None)()
            texto = corpo.decode(charset or "utf-8", errors="replace")
    except HTTPError as erro:
        if erro.code == 429 or 500 <= erro.code <= 599:
            # Não deu para perguntar. Não perguntar não é permissão (I10).
            return RobotsPolicy(
                origin=origem,
                fetchable=False,
                reason=f"robots.txt indisponível (HTTP {erro.code}) — busca suspensa",
            )
        return RobotsPolicy(
            origin=origem,
            reason=f"robots.txt ausente (HTTP {erro.code})",
        )
    except (URLError, TimeoutError, OSError) as erro:
        return RobotsPolicy(
            origin=origem,
            fetchable=False,
            reason=f"robots.txt inacessível ({type(erro).__name__}) — busca suspensa",
        )

    regras = parse_robots(texto)
    return RobotsPolicy(
        origin=origem,
        disallow=regras["disallow"],
        allow=regras["allow"],
        crawl_delay=regras["delay"],
        reason="robots.txt lido",
    )


class RobotsGate:
    """Guarda a política por origem e impõe o intervalo entre buscas.

    Instanciado por execução da descoberta: duas fontes do mesmo município
    compartilham a leitura do `robots.txt`, e o intervalo vale entre elas.
    """

    def __init__(
        self,
        loader: Callable[[str], RobotsPolicy] = load_policy,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._loader = loader
        self._sleep = sleeper
        self._clock = clock
        self._policies: dict[str, RobotsPolicy] = {}
        self._last_request: dict[str, float] = {}

    def policy_for(self, url: str) -> RobotsPolicy:
        partes = urlparse(url)
        origem = f"{partes.scheme}://{partes.netloc}"
        if origem not in self._policies:
            self._policies[origem] = self._loader(url)
        return self._policies[origem]

    def check(self, url: str) -> RobotsPolicy:
        """Levanta `RobotsDenied` se a busca não for permitida."""
        policy = self.policy_for(url)
        if not policy.fetchable:
            raise RobotsDenied(f"{policy.origin}: {policy.reason}")
        if not policy.path_allowed(url):
            raise RobotsDenied(
                f"{url} é proibido pelo robots.txt de {policy.origin} "
                f"(agente {USER_AGENT})"
            )
        return policy

    def wait(self, url: str, policy: RobotsPolicy) -> None:
        """Aguarda o que faltar do intervalo desde a última busca ao host."""
        origem = policy.origin
        anterior = self._last_request.get(origem)
        agora = self._clock()
        if anterior is not None:
            restante = policy.delay - (agora - anterior)
            if restante > 0:
                self._sleep(restante)
                agora = self._clock()
        self._last_request[origem] = agora
