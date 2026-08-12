# Imagem de produção da API (§12, item D9).
#
# Nenhum segredo entra aqui. A imagem carrega código e dependências; chave de
# assinatura, URL de banco e credencial de storage chegam por variável de
# ambiente, injetadas pela plataforma em tempo de execução. Ver `.dockerignore`,
# que mantém `.env` fora do contexto de build, e `docs/OPERACAO.md`.

FROM python:3.12-slim AS base

# `postgresql-client` entra por causa do backup: `pg_dump` e `pg_restore` rodam
# a partir do mesmo ambiente da aplicação (ops/backup.py, ops/restore.py).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências antes do código: alterar uma linha da aplicação não reinstala
# tudo de novo.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY ops ./ops

# Usuário sem privilégio. O diretório de upload é ponto de montagem: em
# produção ele é volume ou bucket, nunca camada de imagem.
RUN useradd --create-home --uid 10001 atlas \
    && mkdir -p /app/backend/uploads \
    && chown -R atlas:atlas /app
USER atlas

WORKDIR /app/backend

EXPOSE 8000

# Sem `--reload`, sem `create_all`. O esquema é responsabilidade do passo de
# migração, que roda antes e separado (ver docker-compose.prod.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
