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

    # Armazenamento de documentos (§6.6)
    # `local` grava no disco do servidor; `s3` grava em bucket compatível com
    # S3 (AWS, MinIO). A aplicação nunca monta caminho de arquivo diretamente:
    # tudo passa por `app.services.storage`.
    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = os.path.join(BACKEND_DIR, "uploads")
    MAX_UPLOAD_MB: int = 50

    S3_BUCKET: str = ""
    S3_PREFIX: str = "documents/"
    S3_REGION: str = ""
    S3_ENDPOINT_URL: str = ""  # preencher para MinIO ou outro compatível

    # Retenção (§6.6)
    # Dias após a obsolescência do documento em que o arquivo binário pode ser
    # descartado. Zero desliga o expurgo. O registro de metadados **nunca** é
    # apagado: o que sai é o blob, e a linha passa a constar como expurgada.
    OBSOLETE_RETENTION_DAYS: int = 0

    # Camada de IA (§3.3, §6.8)
    # `none` é o padrão: sem provedor, o assistente responde por busca
    # determinística no catálogo e diz que é isso que está fazendo.
    AI_PROVIDER: str = "none"  # none | anthropic
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-opus-5"
    AI_TIMEOUT_SECONDS: int = 60
    #: Horas que uma resposta idêntica (mesma pergunta, mesmo catálogo, mesmo
    #: modelo) pode ser reaproveitada. Zero desliga o cache.
    AI_CACHE_HOURS: int = 24

    # Filas e workers (§6.7)
    # `inline` executa no próprio processo da API — e o registro do trabalho
    # diz isso. `redis` entrega a um worker separado.
    QUEUE_BACKEND: str = "inline"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Antivírus (§6.6)
    # `none` significa "nenhuma verificação" — e é assim que fica registrado no
    # documento, em vez de dar o arquivo por limpo.
    ANTIVIRUS_BACKEND: str = "none"  # none | clamav
    ANTIVIRUS_HOST: str = "127.0.0.1"
    ANTIVIRUS_PORT: int = 3310
    ANTIVIRUS_SOCKET: str = ""  # socket unix do clamd, quando houver
    ANTIVIRUS_TIMEOUT_SECONDS: int = 30
    #: Quando verdadeiro, upload que não pôde ser verificado é recusado.
    #: Falhar fechado é a postura correta em produção; em desenvolvimento
    #: costuma não haver clamd, e recusar tudo inviabilizaria o uso.
    ANTIVIRUS_REQUIRED: bool = False

    # URL pública usada nos QR Codes de verificação de documento (§8.3)
    PUBLIC_BASE_URL: str = "http://localhost:3000"

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
