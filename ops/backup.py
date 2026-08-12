"""Backup do Atlas: banco + documentos, com manifesto (§12, item D9).

Duas metades, e as duas precisam existir para o backup significar alguma coisa:

- o **banco** guarda o registro — quem analisou o quê, sob qual versão do
  catálogo, com qual hash;
- o **storage** guarda os bytes dos documentos (§6.6). Um sem o outro deixa
  registro apontando para arquivo que não existe, ou arquivo que ninguém sabe
  de qual projeto é.

O manifesto grava o SHA-256 de cada peça. Não é zelo: é o que permite ao
`restore.py` recusar um backup corrompido em vez de restaurar lixo por cima de
um banco vazio.

Uso:
    python ops/backup.py --output ./backups
    python ops/backup.py --output ./backups --database-url postgresql://...

Requer `pg_dump` no PATH para bancos Postgres.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

MANIFEST_NAME = "manifest.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_libpq_url(database_url: str) -> str:
    """SQLAlchemy usa `postgresql+psycopg2://`; o `pg_dump` não entende o driver."""
    return database_url.replace("+psycopg2", "").replace("+asyncpg", "")


def dump_database(database_url: str, destination: Path) -> Path:
    parsed = urlparse(to_libpq_url(database_url))

    if parsed.scheme.startswith("sqlite"):
        # Desenvolvimento. O arquivo é o banco; copiar basta.
        source = Path(database_url.split("///")[-1])
        if not source.exists():
            raise SystemExit(f"Banco SQLite não encontrado: {source}")
        target = destination / "database.sqlite"
        shutil.copy2(source, target)
        return target

    if shutil.which("pg_dump") is None:
        raise SystemExit(
            "pg_dump não está no PATH. Instale o cliente do Postgres "
            "(postgresql-client) para fazer backup de um banco Postgres."
        )

    target = destination / "database.dump"
    # Formato custom: comprimido e restaurável seletivamente pelo pg_restore.
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
         "--file", str(target), to_libpq_url(database_url)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"pg_dump falhou:\n{result.stderr}")
    return target


def archive_storage(upload_dir: Path, destination: Path) -> Path | None:
    """Empacota o storage local. Backend S3 tem versionamento próprio."""
    if not upload_dir.exists():
        print(f"  storage: {upload_dir} não existe — nada a arquivar")
        return None

    target = destination / "storage.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        archive.add(upload_dir, arcname="uploads")
    return target


def run(database_url: str, upload_dir: Path, output: Path, storage_backend: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output / f"atlas-{stamp}"
    destination.mkdir(parents=True, exist_ok=False)

    print(f"Backup em {destination}")

    print("  banco...")
    database_file = dump_database(database_url, destination)

    storage_file = None
    if storage_backend == "local":
        print("  documentos...")
        storage_file = archive_storage(upload_dir, destination)
    else:
        print(f"  storage: backend '{storage_backend}' — fora do escopo deste script")

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "storage_backend": storage_backend,
        "database": {
            "file": database_file.name,
            "sha256": sha256_of(database_file),
            "bytes": database_file.stat().st_size,
            "engine": "sqlite" if database_file.suffix == ".sqlite" else "postgres",
        },
        "storage": (
            {
                "file": storage_file.name,
                "sha256": sha256_of(storage_file),
                "bytes": storage_file.stat().st_size,
            }
            if storage_file
            else None
        ),
    }

    (destination / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"  pronto: {manifest['database']['bytes']} bytes de banco")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup do Atlas (banco + documentos).")
    parser.add_argument("--output", default="./backups", help="diretório de destino")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--upload-dir", default=os.environ.get("UPLOAD_DIR", "./uploads"))
    parser.add_argument(
        "--storage-backend", default=os.environ.get("STORAGE_BACKEND", "local")
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("Informe --database-url ou defina DATABASE_URL.")

    destination = run(
        args.database_url,
        Path(args.upload_dir),
        Path(args.output),
        args.storage_backend,
    )
    print(destination)


if __name__ == "__main__":
    sys.exit(main())
