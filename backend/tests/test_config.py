import os
import pytest
from app.core.config import Settings

def test_settings_secret_key_development_fallback():
    os.environ["ENVIRONMENT"] = "development"
    if "SECRET_KEY" in os.environ:
        del os.environ["SECRET_KEY"]

    settings = Settings()
    # In development it should generate a random secret key if none provided
    assert settings.SECRET_KEY is not None
    assert len(settings.SECRET_KEY) > 0

def test_settings_secret_key_production_missing():
    os.environ["ENVIRONMENT"] = "production"
    if "SECRET_KEY" in os.environ:
        del os.environ["SECRET_KEY"]

    with pytest.raises(RuntimeError) as exc_info:
        Settings()

    assert "SECRET_KEY é obrigatória quando ENVIRONMENT=production" in str(exc_info.value)

def test_settings_secret_key_provided():
    os.environ["ENVIRONMENT"] = "production"
    os.environ["SECRET_KEY"] = "my_super_secret_key"

    settings = Settings()
    assert settings.SECRET_KEY == "my_super_secret_key"

    del os.environ["SECRET_KEY"]
