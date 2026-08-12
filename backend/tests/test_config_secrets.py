"""Segredos não escapam por acidente (§12, item D9).

O padrão do Pydantic imprime todos os campos no `repr`. Basta um traceback que
inclua as configurações, um `print` de depuração ou um relator de erro para a
chave de assinatura ir parar no log — onde ela fica, indexada, para sempre.
"""

import pytest

from app.core.config import Settings, settings


def _producao(monkeypatch, **extras):
    monkeypatch.setenv("ENVIRONMENT", "production")
    for chave, valor in extras.items():
        monkeypatch.setenv(chave, valor)
    return Settings


# --- Redação -----------------------------------------------------------------


def test_repr_nao_expoe_a_chave_de_assinatura():
    texto = repr(settings)
    assert settings.SECRET_KEY not in texto
    assert "SECRET_KEY='***'" in texto


def test_str_tambem_redige():
    """`f"{settings}"` é o caminho mais fácil de vazar sem perceber."""
    assert settings.SECRET_KEY not in f"{settings}"


def test_repr_continua_util():
    """Redigir segredo não pode cegar a depuração do resto."""
    texto = repr(settings)
    assert "ENVIRONMENT=" in texto
    assert "STORAGE_BACKEND=" in texto


def test_url_do_banco_e_redigida():
    """A URL carrega usuário e senha do Postgres."""
    assert "DATABASE_URL='***'" in repr(settings)


# --- Guardas de produção -----------------------------------------------------


def test_producao_sem_chave_recusa_subir(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    Config = _producao(monkeypatch)
    with pytest.raises(RuntimeError, match="SECRET_KEY é obrigatória"):
        Config(_env_file=None)


def test_producao_com_sqlite_recusa_subir(monkeypatch):
    """SQLite em produção não tem concorrência, RLS nem caminho de backup."""
    Config = _producao(
        monkeypatch, SECRET_KEY="chave-de-teste", DATABASE_URL="sqlite:///./atlas.db"
    )
    with pytest.raises(RuntimeError, match="SQLite não é suportado"):
        Config(_env_file=None)


def test_producao_com_postgres_sobe(monkeypatch):
    Config = _producao(
        monkeypatch,
        SECRET_KEY="chave-de-teste",
        DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/atlas",
    )
    configuracao = Config(_env_file=None)
    assert configuracao.ENVIRONMENT == "production"
    assert configuracao.SECRET_KEY == "chave-de-teste"


def test_desenvolvimento_gera_chave_efemera(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    configuracao = Settings(_env_file=None)
    assert configuracao.SECRET_KEY
    # Efêmera: dois processos não compartilham chave, e nenhuma está versionada.
    assert configuracao.SECRET_KEY != Settings(_env_file=None).SECRET_KEY
