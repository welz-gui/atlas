"""Exercita o ciclo completo de backup e restauração (§12, item D9).

**Backup não restaurado é hipótese, não cópia.** Este script transforma essa
frase em verificação: povoa um banco, tira o backup, **destrói o banco**,
restaura e compara. Se a contagem de qualquer tabela divergir, ele falha.

Roda na CI a cada push, de modo que a restauração seja exercitada sem depender
de alguém lembrar — que é exatamente o modo como backups deixam de funcionar.

Uso:
    DATABASE_URL=postgresql+psycopg2://... python ops/verify_restore.py

O banco apontado por `DATABASE_URL` é **destruído** no processo. Use um banco
descartável.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))


def run_command(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Falhou: {' '.join(command)}")


def fingerprint() -> dict[str, int]:
    """Contagem por tabela — o que precisa sobreviver ao ciclo."""
    from app.core.database import SessionLocal
    from app.models import domain

    session = SessionLocal()
    try:
        counts: dict[str, int] = {}
        for name in dir(domain):
            candidate = getattr(domain, name)
            if isinstance(candidate, type) and hasattr(candidate, "__tablename__"):
                counts[candidate.__tablename__] = session.query(candidate).count()
        return counts
    finally:
        session.close()


def drop_everything(database_url: str) -> None:
    """Apaga o esquema inteiro, para que a restauração parta do zero real."""
    from sqlalchemy import create_engine, text

    # O engine da aplicação mantém conexões no pool. No Windows isso segura o
    # arquivo do SQLite e impede apagá-lo; em qualquer sistema, deixa conexão
    # aberta para um banco que está prestes a deixar de existir.
    from app.core.database import engine as app_engine

    app_engine.dispose()

    if database_url.startswith("sqlite"):
        # Apagar o arquivo, e não `drop_all`: este deixaria `alembic_version`
        # de pé, e um banco que ainda sabe em qual migration está não foi
        # destruído de verdade.
        target = Path(database_url.split("///")[-1])
        if target.exists():
            target.unlink()
        return

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def table_count(database_url: str) -> int:
    """Quantas tabelas existem. Depois do drop precisa ser zero.

    Conta pelo inspector, e não por consulta: com o esquema destruído, qualquer
    `SELECT` levanta exceção — o que prova que funcionou, mas atrapalha medir.
    """
    from sqlalchemy import create_engine, inspect

    engine = create_engine(database_url)
    try:
        return len(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Defina DATABASE_URL apontando para um banco descartável.")

    python = sys.executable

    print("1. Construindo o esquema e povoando...")
    run_command([python, "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    run_command([python, "seed.py"], cwd=BACKEND)

    before = fingerprint()
    total = sum(before.values())
    print(f"   {len(before)} tabelas, {total} linhas")
    if total == 0:
        raise SystemExit("O seed não gravou nada — o teste não provaria coisa alguma.")

    with tempfile.TemporaryDirectory() as workspace:
        print("2. Backup...")
        result = subprocess.run(
            [python, "ops/backup.py", "--output", workspace, "--database-url", database_url],
            cwd=BACKEND.parent,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit("Backup falhou.")
        backup_dir = result.stdout.strip().splitlines()[-1]

        print("3. Destruindo o banco...")
        drop_everything(database_url)
        remaining = table_count(database_url)
        if remaining:
            raise SystemExit(
                f"O banco não foi destruído — {remaining} tabelas de pé. "
                "A restauração seguinte não provaria nada."
            )
        print("   0 tabelas de pé")

        print("4. Restaurando...")
        run_command(
            [python, "ops/restore.py", backup_dir, "--database-url", database_url],
            cwd=BACKEND.parent,
        )

    print("5. Conferindo...")
    after = fingerprint()

    divergences = [
        (table, before[table], after.get(table))
        for table in sorted(before)
        if before[table] != after.get(table)
    ]
    if divergences:
        for table, expected, got in divergences:
            print(f"   {table}: esperado {expected}, obtido {got}", file=sys.stderr)
        raise SystemExit("A restauração não devolveu o mesmo conteúdo.")

    print(f"   {len(after)} tabelas conferem, {sum(after.values())} linhas restauradas")
    print("\nCiclo completo: backup, destruição e restauração verificados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
