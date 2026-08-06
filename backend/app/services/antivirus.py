"""Varredura antivírus de arquivos enviados (§6.6, §12).

A regra que orienta este módulo é a mesma do extrator de parâmetros: **ausência
de verificação não é aprovação**. Quando não há antivírus configurado — o caso
de qualquer instalação de desenvolvimento — o documento fica gravado como
`nao_verificado`, e é isso que a interface mostra. Em nenhum caminho o arquivo
é dado por limpo sem que um motor tenha efetivamente respondido.

Configuração::

    ANTIVIRUS_BACKEND=none      # nenhuma varredura (padrão)
    ANTIVIRUS_BACKEND=clamav    # clamd via TCP (ANTIVIRUS_HOST/PORT)
                                # ou socket unix (ANTIVIRUS_SOCKET)
    ANTIVIRUS_REQUIRED=true     # recusa upload que não tenha sido varrido

`ANTIVIRUS_REQUIRED` é a chave para produção: com ela, um clamd fora do ar
derruba o upload em vez de deixar entrar arquivo não conferido.
"""

from __future__ import annotations

import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Optional

from app.core.config import settings


class ScanStatus:
    """Resultado possível de uma varredura."""

    LIMPO = "limpo"
    INFECTADO = "infectado"
    #: Nenhum motor respondeu — sem antivírus configurado, ou fora do ar.
    NAO_VERIFICADO = "nao_verificado"
    #: O motor respondeu, mas com erro (arquivo grande demais, timeout).
    ERRO = "erro"

    ALL = {LIMPO, INFECTADO, NAO_VERIFICADO, ERRO}
    #: Situações em que o arquivo não pode ser aceito quando a varredura é
    #: obrigatória.
    NOT_CLEAN = {INFECTADO, NAO_VERIFICADO, ERRO}


@dataclass(frozen=True)
class ScanResult:
    status: str
    engine: Optional[str] = None
    engine_version: Optional[str] = None
    signature: Optional[str] = None
    scanned_at: Optional[datetime] = None
    detail: Optional[str] = None

    @property
    def is_clean(self) -> bool:
        return self.status == ScanStatus.LIMPO

    @property
    def is_infected(self) -> bool:
        return self.status == ScanStatus.INFECTADO


class AntivirusScanner(ABC):
    name: str

    @abstractmethod
    def scan_file(self, path: str) -> ScanResult:
        ...

    def describe(self) -> str:
        return self.name


class NullScanner(AntivirusScanner):
    """Nenhum antivírus. Registra a ausência em vez de fingir aprovação."""

    name = "none"

    def scan_file(self, path: str) -> ScanResult:
        return ScanResult(
            status=ScanStatus.NAO_VERIFICADO,
            engine=None,
            detail="Nenhum antivírus configurado (ANTIVIRUS_BACKEND=none).",
        )

    def describe(self) -> str:
        return "nenhum antivírus configurado"


class ClamAVScanner(AntivirusScanner):
    """clamd, falado no protocolo nativo — sem dependência extra.

    Usa-se `INSTREAM` em vez de `SCAN <caminho>` de propósito: com `SCAN` o
    daemon precisa enxergar o mesmo sistema de arquivos que a aplicação, o que
    deixa de valer assim que o clamd roda em outro container. `INSTREAM`
    empurra os bytes pela conexão e funciona nos dois cenários.
    """

    name = "clamav"
    CHUNK = 64 * 1024

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        unix_socket: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.host = host or settings.ANTIVIRUS_HOST
        self.port = port or settings.ANTIVIRUS_PORT
        self.unix_socket = unix_socket if unix_socket is not None else settings.ANTIVIRUS_SOCKET
        self.timeout = timeout or settings.ANTIVIRUS_TIMEOUT_SECONDS

    def _connect(self) -> socket.socket:
        if self.unix_socket:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(self.unix_socket)
            return sock
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        return sock

    def _version(self) -> Optional[str]:
        try:
            with self._connect() as sock:
                sock.sendall(b"zVERSION\0")
                return sock.recv(256).decode("utf-8", "replace").strip("\0 \n") or None
        except OSError:
            return None

    def scan_file(self, path: str) -> ScanResult:
        now = datetime.utcnow()
        try:
            with self._connect() as sock:
                sock.sendall(b"zINSTREAM\0")
                with open(path, "rb") as handle:
                    while chunk := handle.read(self.CHUNK):
                        sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
                sock.sendall((0).to_bytes(4, "big"))
                raw = sock.recv(4096).decode("utf-8", "replace").strip("\0 \n")
        except OSError as exc:
            # Daemon fora do ar, socket errado, timeout. Não é limpo nem
            # infectado: é "não sabemos" — e quem decide o que fazer com isso é
            # o chamador, conforme ANTIVIRUS_REQUIRED.
            return ScanResult(
                status=ScanStatus.NAO_VERIFICADO,
                engine=self.name,
                scanned_at=now,
                detail=f"Falha ao falar com o clamd: {exc}",
            )

        version = self._version()

        if raw.endswith("OK"):
            return ScanResult(
                status=ScanStatus.LIMPO,
                engine=self.name,
                engine_version=version,
                scanned_at=now,
            )
        if raw.endswith("FOUND"):
            # Formato: "stream: Eicar-Test-Signature FOUND"
            signature = raw.rsplit(" ", 1)[0].split(":", 1)[-1].strip()
            return ScanResult(
                status=ScanStatus.INFECTADO,
                engine=self.name,
                engine_version=version,
                signature=signature or None,
                scanned_at=now,
                detail=raw,
            )
        return ScanResult(
            status=ScanStatus.ERRO,
            engine=self.name,
            engine_version=version,
            scanned_at=now,
            detail=raw or "Resposta vazia do clamd.",
        )

    def describe(self) -> str:
        target = self.unix_socket or f"{self.host}:{self.port}"
        return f"clamav ({target})"


_SCANNERS = {"none": NullScanner, "clamav": ClamAVScanner}


@lru_cache(maxsize=1)
def get_scanner() -> AntivirusScanner:
    choice = (settings.ANTIVIRUS_BACKEND or "none").strip().lower()
    factory = _SCANNERS.get(choice)
    if factory is None:
        raise RuntimeError(
            f"ANTIVIRUS_BACKEND='{choice}' desconhecido. "
            f"Valores aceitos: {', '.join(sorted(_SCANNERS))}."
        )
    return factory()


def reset_scanner_cache() -> None:
    get_scanner.cache_clear()
