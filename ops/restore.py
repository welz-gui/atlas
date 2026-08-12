"""Restauração de um backup do Atlas (§12, item D9).

Confere o SHA-256 do manifesto **antes** de tocar no destino. Restaurar um
arquivo corrompido por cima de um banco vazio é pior que não restaurar: o
sistema sobe, parece íntegro, e a perda só aparece quando alguém procura o
registro que sumiu.

Uso:
    python ops/restore.py ./backups/atlas-20260812T120000Z --database-url postgresql://...
    python ops/restore.py ./backups/atlas-... --verify-only

Requer `pg_restore` no PATH para bancos Postgres.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.parse import urlparse

from backup import MANIFEST_NAME, sha256_of, to_libpq_url  # type: ignore


def load_manifest(directory: Path) -> dict:
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.exists():
        raise SystemExit(f"Manifesto ausente em {directory} — isto não é um backup.")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify(directory: Path, manifest: dict) -> None:
    """Confere cada peça contra o hash gravado no momento do backup."""
    for label in ("database", "storage"):
        entry = manifest.get(label)
        if not entry:
            continue
        path = directory / entry["file"]
        if not path.exists():
            raise SystemExit(f"{label}: arquivo ausente — {path}")
        actual = sha256_of(path)
        if actual != entry["sha256"]:
            raise SystemExit(
                f"{label}: hash não confere.\n"
                f"  esperado {entry['sha256']}\n"
                f"  obtido   {actual}\n"
                "Backup corrompido. A restauração foi interrompida antes de "
                "tocar no destino."
            )
        print(f"  {label}: íntegro ({entry['bytes']} bytes)")


def restore_database(directory: Path, manifest: dict, database_url: str) -> None:
    entry = manifest["database"]
    source = directory / entry["file"]

    if entry["engine"] == "sqlite":
        target = Path(database_url.split("///")[-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return

    if shutil.which("pg_restore") is None:
        raise SystemExit("pg_restore não está no PATH (instale postgresql-client).")

    # `--clean --if-exists` derruba os objetos antes de recriar, de modo que a
    # restauração seja idempotente sobre um banco já povoado.
    result = subprocess.run(
        ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges",
         "--dbname", to_libpq_url(database_url), str(source)],
        capture_output=True,
        text=True,
    )
    # pg_restore devolve 1 com avisos benignos (objeto inexistente ao limpar).
    if result.returncode not in (0, 1):
        raise SystemExit(f"pg_restore falhou:\n{result.stderr}")
    if result.returncode == 1:
        print("  pg_restore terminou com avisos (esperado em banco vazio)")


def restore_storage(directory: Path, manifest: dict, upload_dir: Path) -> None:
    entry = manifest.get("storage")
    if not entry:
        print("  storage: nada no backup")
        return

    source = directory / entry["file"]
    upload_dir.parent.mkdir(parents=True, exist_ok=True)
    if upload_dir.exists():
        shutil.rmtree(upload_dir)

    with tarfile.open(source, "r:gz") as archive:
        archive.extractall(upload_dir.parent)

    extracted = upload_dir.parent / "uploads"
    if extracted != upload_dir and extracted.exists():
        extracted.rename(upload_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura um backup do Atlas.")
    parser.add_argument("directory", help="diretório do backup")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--upload-dir", default=os.environ.get("UPLOAD_DIR", "./uploads"))
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="confere os hashes e sai, sem tocar no destino",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    manifest = load_manifest(directory)

    print(f"Backup de {manifest['created_at']}")
    verify(directory, manifest)

    if args.verify_only:
        print("Íntegro. Nada foi restaurado (--verify-only).")
        return

    if not args.database_url:
        raise SystemExit("Informe --database-url ou defina DATABASE_URL.")

    print("Restaurando...")
    restore_database(directory, manifest, args.database_url)
    restore_storage(directory, manifest, Path(args.upload_dir))
    print("Pronto.")


if __name__ == "__main__":
    sys.exit(main())
