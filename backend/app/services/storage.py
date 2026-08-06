"""Abstração de armazenamento de arquivos (§6.6).

O protótipo gravava direto em `open(os.path.join(UPLOAD_DIR, ...))`, espalhando
conhecimento do disco local por endpoints e serviços. Isso amarra a aplicação a
um servidor único: nenhum processo de fora daquela máquina — worker, réplica,
container efêmero — consegue ler o que foi enviado.

Aqui existe um único contrato. Quem grava ou lê um documento fala com um
`StorageBackend`; onde os bytes moram é decisão de configuração:

    STORAGE_BACKEND=local   # disco do servidor (padrão de desenvolvimento)
    STORAGE_BACKEND=s3      # bucket S3 ou compatível (MinIO)

Três decisões que valem explicação:

1. **A chave é opaca e gerada pelo servidor.** O nome enviado pelo cliente
   nunca compõe o caminho — ele é dado hostil. `../` não tem efeito porque o
   nome do cliente não é usado.
2. **A escrita é atômica.** Os bytes vão para um arquivo temporário; só depois
   de fechados, verificados e — quando for o caso — varridos por antivírus é
   que o objeto entra no lugar definitivo. Uma requisição interrompida no meio
   não deixa arquivo parcial visível.
3. **Apagar é explícito e raro.** `delete()` existe para o expurgo por retenção
   (ver `app.services.retention`), que descarta o binário e preserva o registro
   de metadados. Nada em fluxo normal apaga arquivo.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import BinaryIO, Iterator, Optional

from app.core.config import settings


class StorageError(RuntimeError):
    """Falha de armazenamento — nunca deve ser confundida com 'arquivo vazio'."""


class ObjectNotFound(StorageError):
    """A chave não existe no backend (expurgada, ou nunca gravada)."""


@dataclass(frozen=True)
class StoredObject:
    """Resultado de uma gravação bem-sucedida."""

    key: str
    backend: str
    size_bytes: int
    sha256: str


def build_key(extension: str = "") -> str:
    """Chave opaca para um objeto novo.

    Só a extensão sobrevive do nome enviado pelo cliente, e ainda assim depois
    de passar por allowlist no endpoint. O nome em si nunca toca o storage.
    """
    return f"{uuid.uuid4().hex}{extension.lower()}"


# =============================================================================
# Escrita
# =============================================================================

class StorageWriter:
    """Gravação em duas fases, com hash e tamanho apurados no caminho.

    Uso::

        with storage.writer(key) as w:
            while chunk := await upload.read(CHUNK):
                w.write(chunk)
        stored = w.result

    Sair do bloco com exceção descarta tudo: o objeto não chega a existir.
    O `commit` explícito só ocorre na saída limpa — e pode ser adiado com
    `defer_commit=True` para que uma varredura antivírus rode sobre o
    temporário antes de o arquivo virar definitivo.
    """

    def __init__(self, backend: "StorageBackend", key: str, defer_commit: bool = False):
        self._backend = backend
        self._key = key
        self._defer = defer_commit
        self._digest = hashlib.sha256()
        self._size = 0
        self._committed = False
        self._closed = False
        fd, self._temp_path = tempfile.mkstemp(prefix="atlas-upload-", suffix=".part")
        self._handle: Optional[BinaryIO] = os.fdopen(fd, "wb")

    # -- interface de escrita ---------------------------------------------
    def write(self, chunk: bytes) -> int:
        if self._handle is None:
            raise StorageError("Escrita após o fechamento do writer.")
        self._handle.write(chunk)
        self._digest.update(chunk)
        self._size += len(chunk)
        return self._size

    @property
    def size_bytes(self) -> int:
        return self._size

    @property
    def temp_path(self) -> str:
        """Caminho local do temporário — para antivírus antes do commit."""
        return self._temp_path

    @property
    def result(self) -> StoredObject:
        if not self._committed:
            raise StorageError("O objeto ainda não foi gravado.")
        return StoredObject(
            key=self._key,
            backend=self._backend.name,
            size_bytes=self._size,
            sha256=self._digest.hexdigest(),
        )

    # -- ciclo de vida -----------------------------------------------------
    def _flush(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def commit(self) -> StoredObject:
        """Promove o temporário a objeto definitivo."""
        if self._committed:
            return self.result
        self._flush()
        if self._size == 0:
            raise StorageError("Nada foi escrito; nenhum objeto será criado.")
        self._backend._persist(self._key, self._temp_path)
        self._committed = True
        self._cleanup_temp()
        return self.result

    def abort(self) -> None:
        """Descarta o temporário. Idempotente."""
        self._flush()
        self._cleanup_temp()

    def _cleanup_temp(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            os.unlink(self._temp_path)
        except FileNotFoundError:
            pass

    def __enter__(self) -> "StorageWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.abort()
            return False
        if not self._defer:
            self.commit()
        else:
            self._flush()
        return False


# =============================================================================
# Backends
# =============================================================================

class StorageBackend(ABC):
    name: str

    def writer(self, key: str, defer_commit: bool = False) -> StorageWriter:
        return StorageWriter(self, key, defer_commit=defer_commit)

    @abstractmethod
    def _persist(self, key: str, source_path: str) -> None:
        """Move o conteúdo de um arquivo local para a chave definitiva."""

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Abre o objeto para leitura. Levanta `ObjectNotFound` se não existir."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove o objeto. Devolve falso se já não existia."""

    def read(self, key: str) -> bytes:
        with self.open(key) as handle:
            return handle.read()

    def stream(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        with self.open(key) as handle:
            while chunk := handle.read(chunk_size):
                yield chunk

    def describe(self) -> str:
        return self.name


class LocalStorage(StorageBackend):
    """Disco do servidor. Padrão de desenvolvimento."""

    name = "local"

    def __init__(self, root: Optional[str] = None):
        self.root = os.path.abspath(root or settings.UPLOAD_DIR)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        # `basename` é cinto e suspensório: as chaves são geradas pelo servidor,
        # mas uma chave vinda do banco não deve poder escapar do diretório caso
        # alguém a tenha adulterado.
        return os.path.join(self.root, os.path.basename(key))

    def _persist(self, key: str, source_path: str) -> None:
        destination = self._path(key)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        # `move` cobre o caso de o temporário estar em outro sistema de
        # arquivos, onde `os.replace` falharia com EXDEV.
        shutil.move(source_path, destination)

    def open(self, key: str) -> BinaryIO:
        try:
            return open(self._path(key), "rb")
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc

    def exists(self, key: str) -> bool:
        return os.path.isfile(self._path(key))

    def delete(self, key: str) -> bool:
        try:
            os.unlink(self._path(key))
            return True
        except FileNotFoundError:
            return False

    def describe(self) -> str:
        return f"local:{self.root}"


class S3Storage(StorageBackend):
    """Bucket S3 ou compatível (MinIO).

    O `boto3` é importado sob demanda: quem roda com storage local não precisa
    tê-lo instalado.
    """

    name = "s3"

    def __init__(
        self,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
        client=None,
    ):
        self.bucket = bucket or settings.S3_BUCKET
        if not self.bucket:
            raise StorageError(
                "STORAGE_BACKEND=s3 exige S3_BUCKET configurado."
            )
        self.prefix = (prefix if prefix is not None else settings.S3_PREFIX) or ""
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3  # noqa: PLC0415 — dependência opcional
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise StorageError(
                    "STORAGE_BACKEND=s3 exige o pacote boto3 instalado."
                ) from exc
            kwargs = {}
            if settings.S3_REGION:
                kwargs["region_name"] = settings.S3_REGION
            if settings.S3_ENDPOINT_URL:
                kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def _object_key(self, key: str) -> str:
        return f"{self.prefix}{os.path.basename(key)}"

    def _persist(self, key: str, source_path: str) -> None:
        self.client.upload_file(source_path, self.bucket, self._object_key(key))
        try:
            os.unlink(source_path)
        except FileNotFoundError:
            pass

    def open(self, key: str) -> BinaryIO:
        try:
            response = self.client.get_object(
                Bucket=self.bucket, Key=self._object_key(key)
            )
        except Exception as exc:  # botocore.ClientError e variantes
            raise ObjectNotFound(key) from exc
        return response["Body"]

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._object_key(key))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self.exists(key):
            return False
        self.client.delete_object(Bucket=self.bucket, Key=self._object_key(key))
        return True

    def describe(self) -> str:
        return f"s3:{self.bucket}/{self.prefix}"


# =============================================================================
# Seleção
# =============================================================================

_BACKENDS = {"local": LocalStorage, "s3": S3Storage}


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """Backend configurado. Cacheado: a escolha não muda em tempo de execução."""
    choice = (settings.STORAGE_BACKEND or "local").strip().lower()
    factory = _BACKENDS.get(choice)
    if factory is None:
        raise StorageError(
            f"STORAGE_BACKEND='{choice}' desconhecido. "
            f"Valores aceitos: {', '.join(sorted(_BACKENDS))}."
        )
    return factory()


def reset_storage_cache() -> None:
    """Descarta o backend memorizado — usado por teste ao trocar de configuração."""
    get_storage.cache_clear()
