import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base
import app.models.domain  # noqa: F401  — registra as tabelas em Base.metadata


@pytest.fixture
def db_session():
    # StaticPool mantém uma única conexão para o banco em memória, de modo que
    # o TestClient — que atende as requisições em outra thread — enxergue as
    # mesmas tabelas.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
