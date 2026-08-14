"""A RLS de verdade, contra Postgres (§3.1, §12 — item D1).

**Estes testes pulam quando `DATABASE_URL` não é Postgres**, e é de propósito:
a política é inerte no SQLite, então um teste verde lá provaria apenas o filtro
de aplicação. Verde no SQLite não prova nada — está escrito no roadmap e é a
razão de este arquivo existir separado.

Duas condições precisam valer juntas para a RLS ter efeito, e o arquivo verifica
as duas:

1. a política existe e as tabelas estão com `FORCE ROW LEVEL SECURITY`;
2. **a conexão não é de superusuário.** Superusuário e papel com `BYPASSRLS`
   ignoram a política sempre — inclusive com `FORCE`. Era assim que a CI
   conectava antes deste trabalho, e é o motivo de a política existir desde a
   Fase B sem nunca ter defendido nada.

Por isso a fixture cria um papel restrito e reconecta com ele. Testar com o
usuário do `docker-compose`, que é superusuário, daria verde e não significaria
nada.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.core.database import register_tenant_listener
from app.core.tenant import organization_scope
from app.models.domain import Organization, Project

DATABASE_URL = os.environ.get("DATABASE_URL", "")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES,
    reason="A RLS só existe no Postgres; no SQLite a política é inerte.",
)

APP_ROLE = "atlas_app_rls_test"
APP_PASSWORD = "rls-test"


@pytest.fixture(scope="module")
def restricted_url():
    """Cria um papel **sem** BYPASSRLS e devolve a URL para conectar com ele."""
    admin = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP OWNED BY {APP_ROLE} CASCADE") if False else text("SELECT 1"))
        conn.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                        CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}';
                    END IF;
                END
                $$
                """
            )
        )
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                f"IN SCHEMA public TO {APP_ROLE}"
            )
        )
    admin.dispose()

    # Reescreve credenciais mantendo host, porta e banco.
    resto = DATABASE_URL.split("@", 1)[1]
    prefixo = DATABASE_URL.split("://", 1)[0]
    yield f"{prefixo}://{APP_ROLE}:{APP_PASSWORD}@{resto}"


@pytest.fixture
def duas_organizacoes():
    """Duas organizações com um projeto cada, criadas como administrador."""
    admin = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=admin)
    session = Session()

    org_a = Organization(id=str(uuid.uuid4()), name="Construtora A")
    org_b = Organization(id=str(uuid.uuid4()), name="Construtora B")
    session.add_all([org_a, org_b])
    session.flush()

    for org, nome in ((org_a, "Obra da A"), (org_b, "Obra da B")):
        session.add(
            Project(
                id=str(uuid.uuid4()),
                organization_id=org.id,
                name=nome,
                city_ibge="BR-RS-4311403",
                city_name="Lajeado",
                state="RS",
            )
        )
    session.commit()
    ids = (org_a.id, org_b.id)
    session.close()
    admin.dispose()
    yield ids


def _sessao_restrita(url):
    """Sessão com o papel restrito **e** com o listener de tenant.

    O listener é o que emite `SET LOCAL`. Sem registrá-lo aqui, a sessão nunca
    publicaria a organização e todo teste concluiria que a política nega tudo —
    verde nos casos de negação, vermelho nos de permissão, e nenhuma conclusão
    válida sobre a RLS.
    """
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    register_tenant_listener(factory)
    return factory(), engine


# --- A política está mesmo ativa ---------------------------------------------


def test_tabelas_de_negocio_estao_com_force_rls():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        linhas = conn.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname IN "
                "('projects','documents','analysis_runs','daily_logs')"
            )
        ).all()
    engine.dispose()

    assert linhas, "as tabelas não existem — migration não aplicada?"
    for nome, habilitada, forcada in linhas:
        assert habilitada, f"{nome}: RLS desabilitada"
        assert forcada, f"{nome}: sem FORCE — o dono da tabela escaparia"


def test_users_ficou_fora_da_politica():
    """Decidido em `a4d7e91c5b20`: login e cadastro precedem o tenant."""
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        habilitada = conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = 'users'")
        ).scalar()
    engine.dispose()

    assert habilitada is False


# --- O isolamento, com papel restrito ----------------------------------------


def test_sem_organizacao_em_contexto_nada_e_visivel(restricted_url, duas_organizacoes):
    """Falhar fechado: sem `SET LOCAL`, a política nega tudo."""
    session, engine = _sessao_restrita(restricted_url)
    try:
        assert session.query(Project).count() == 0
    finally:
        session.close()
        engine.dispose()


def test_cada_organizacao_ve_apenas_o_proprio_projeto(
    restricted_url, duas_organizacoes
):
    org_a, org_b = duas_organizacoes
    session, engine = _sessao_restrita(restricted_url)
    try:
        with organization_scope(org_a):
            projetos = session.query(Project).all()
            assert [p.name for p in projetos] == ["Obra da A"]
        session.commit()

        with organization_scope(org_b):
            projetos = session.query(Project).all()
            assert [p.name for p in projetos] == ["Obra da B"]
    finally:
        session.close()
        engine.dispose()


def test_consulta_sem_filtro_de_aplicacao_nao_vaza(restricted_url, duas_organizacoes):
    """É a razão de a RLS existir: um `query()` sem filtro não vira vazamento.

    A consulta abaixo **não tem** `filter(organization_id=...)` — é exatamente o
    erro de programação que o §3.1 teme. A política corta assim mesmo.
    """
    org_a, _ = duas_organizacoes
    session, engine = _sessao_restrita(restricted_url)
    try:
        with organization_scope(org_a):
            todos = session.query(Project).all()
        assert len(todos) == 1
        assert todos[0].name == "Obra da A"
    finally:
        session.close()
        engine.dispose()


def test_escrita_para_outra_organizacao_e_recusada(restricted_url, duas_organizacoes):
    """`WITH CHECK` impede gravar linha de outro tenant."""
    org_a, org_b = duas_organizacoes
    session, engine = _sessao_restrita(restricted_url)
    try:
        with organization_scope(org_a):
            session.add(
                Project(
                    id=str(uuid.uuid4()),
                    organization_id=org_b,  # organização alheia
                    name="Invasão",
                    city_ibge="BR-RS-4311403",
                    city_name="Lajeado",
                    state="RS",
                )
            )
            with pytest.raises(ProgrammingError):
                session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()
