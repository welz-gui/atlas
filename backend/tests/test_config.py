import pytest
from app.core.config import Settings

def test_settings_secret_key_development_fallback(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    settings = Settings()
    assert settings.SECRET_KEY is not None
    assert len(settings.SECRET_KEY) > 0

def test_settings_secret_key_production_missing(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        Settings()

    assert "SECRET_KEY é obrigatória quando ENVIRONMENT=production" in str(exc_info.value)

def test_settings_secret_key_provided(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "my_super_secret_key")

    settings = Settings()
    assert settings.SECRET_KEY == "my_super_secret_key"
