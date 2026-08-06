import os
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    PROJECT_NAME: str = "Atlas API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Banco de dados
    # Fallback SQLite para desenvolvimento local. Em produção, aponte para o
    # Postgres (ver docker-compose.yml e .env.example).
    DATABASE_URL: str = f"sqlite:///{os.path.join(BACKEND_DIR, 'atlas_dev.db')}"

    # Armazenamento de documentos
    UPLOAD_DIR: str = os.path.join(BACKEND_DIR, "uploads")
    MAX_UPLOAD_MB: int = 50

    # Segurança
    # Sem SECRET_KEY no ambiente, gera-se uma chave efêmera por processo em vez
    # de carregar um valor previsível versionado no repositório.
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 dias

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if not self.SECRET_KEY:
            if self.ENVIRONMENT == "production":
                raise RuntimeError(
                    "SECRET_KEY é obrigatória quando ENVIRONMENT=production."
                )
            object.__setattr__(self, "SECRET_KEY", secrets.token_urlsafe(48))


settings = Settings()
