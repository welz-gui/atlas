from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings
from app.core.tenant import current_organization_id

# Check if SQLite to adjust connect_args
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#: A RLS só existe no Postgres. Em SQLite o listener abaixo é inerte, e o
#: isolamento continua dependendo apenas do filtro de aplicação — que é o
#: motivo de os testes de RLS exigirem Postgres real: verde no SQLite não
#: prova nada.
IS_POSTGRES = engine.dialect.name == "postgresql"


@event.listens_for(SessionLocal, "after_begin")
def _apply_tenant(session, transaction, connection) -> None:
    """Publica a organização corrente para a política de RLS (§3.1, D1).

    `SET LOCAL` vale até o fim da transação, e não da conexão: quando a
    transação termina, o ajuste desaparece sozinho. É o que torna seguro
    reaproveitar a conexão do pool para outra organização.

    Sem organização em contexto **nada é definido**, e
    `current_setting('atlas.organization_id', true)` devolve `NULL`. A política
    então nega tudo. Falhar fechado é deliberado: preferir o erro visível ao
    vazamento silencioso.
    """
    if not IS_POSTGRES:
        return

    organization_id = current_organization_id()
    if organization_id is None:
        return

    # `set_config` em vez de `SET LOCAL ... = :valor`: o `SET` do Postgres não
    # aceita parâmetro vinculado, e interpolar UUID em SQL é como se abre
    # injeção.
    connection.execute(
        text("SELECT set_config('atlas.organization_id', :org, true)"),
        {"org": organization_id},
    )


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
