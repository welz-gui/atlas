import json
import logging

import pytest

from app.core.logging import (
    JsonFormatter,
    _is_sensitive,
    configure_logging,
    current_request_id,
    redact,
    reset_request_id,
    set_request_id,
)


def test_is_sensitive():
    assert _is_sensitive("password") is True
    assert _is_sensitive("user_password") is True
    assert _is_sensitive("SENHA") is True
    assert _is_sensitive("api_key") is True
    assert _is_sensitive("apikey") is True
    assert _is_sensitive("token_auth") is True
    assert _is_sensitive("cpf_user") is True
    assert _is_sensitive("document_number_id") is True
    assert _is_sensitive("owner_document_val") is True
    assert _is_sensitive("mfa_code") is True
    assert _is_sensitive("recovery_email") is True
    assert _is_sensitive("prompt_text") is True
    assert _is_sensitive("authorization_header") is True

    # Not sensitive
    assert _is_sensitive("email") is False
    assert _is_sensitive("username") is False
    assert _is_sensitive("user_id") is False
    assert _is_sensitive("name") is False
    assert _is_sensitive("payload") is False


def test_redact():
    payload = {
        "email": "test@example.com",
        "user_password": "my_secret_password",
        "nested": {
            "token": "123456",
            "info": "some public info",
            "deep": {
                "SENHA": "abc",
                "other": "val"
            }
        },
        "number": 42
    }
    redacted_payload = redact(payload)

    assert redacted_payload["email"] == "test@example.com"
    assert redacted_payload["user_password"] == "***"
    assert redacted_payload["nested"]["token"] == "***"
    assert redacted_payload["nested"]["info"] == "some public info"
    assert redacted_payload["nested"]["deep"]["SENHA"] == "***"
    assert redacted_payload["nested"]["deep"]["other"] == "val"
    assert redacted_payload["number"] == 42


def test_request_id_context():
    # Initial state
    assert current_request_id() is None

    # Set request id
    token = set_request_id("req-123")
    assert current_request_id() == "req-123"

    # Change it
    token2 = set_request_id("req-456")
    assert current_request_id() == "req-456"

    # Reset to previous
    reset_request_id(token2)
    assert current_request_id() == "req-123"

    # Reset to initial
    reset_request_id(token)
    assert current_request_id() is None


def test_json_formatter_basic():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert "ts" in data
    assert data["level"] == "info"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Test message"
    assert "request_id" not in data


def test_json_formatter_with_request_id():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    token = set_request_id("req-999")
    try:
        formatted = formatter.format(record)
        data = json.loads(formatted)
        assert data["request_id"] == "req-999"
    finally:
        reset_request_id(token)


def test_json_formatter_with_extras():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    # Simulate extra fields passed via `extra={...}`
    record.custom_field = "custom_value"
    record.password = "supersecret"

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["custom_field"] == "custom_value"
    assert data["password"] == "***"


def test_json_formatter_with_exception():
    formatter = JsonFormatter()

    try:
        1 / 0
    except ZeroDivisionError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
    )

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert "exception" in data
    assert "ZeroDivisionError" in data["exception"]


@pytest.fixture
def clean_logging():
    """Fixture para restaurar o estado do logging após o teste."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    uvicorn_access = logging.getLogger("uvicorn.access")
    uv_access_handlers = list(uvicorn_access.handlers)
    uv_access_propagate = uvicorn_access.propagate

    uvicorn_error = logging.getLogger("uvicorn.error")
    uv_error_handlers = list(uvicorn_error.handlers)
    uv_error_propagate = uvicorn_error.propagate

    yield

    root.handlers = original_handlers
    root.level = original_level

    uvicorn_access.handlers = uv_access_handlers
    uvicorn_access.propagate = uv_access_propagate

    uvicorn_error.handlers = uv_error_handlers
    uvicorn_error.propagate = uv_error_propagate


def test_configure_logging(clean_logging):
    root = logging.getLogger()
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_error = logging.getLogger("uvicorn.error")

    # Setup some initial handlers
    root.handlers = []

    configure_logging("DEBUG")

    # Check root logger
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0], logging.StreamHandler)
    assert isinstance(root.handlers[0].formatter, JsonFormatter)

    # Check idempotency
    configure_logging("INFO")
    assert len(root.handlers) == 1  # Still 1 handler
    # Level is not changed if it's already configured because of the early return
    # But wait, looking at the code, idempotency early returns.

    # Check uvicorn loggers
    assert len(uvicorn_access.handlers) == 0
    assert uvicorn_access.propagate is True
    assert len(uvicorn_error.handlers) == 0
    assert uvicorn_error.propagate is True

def test_configure_logging_with_caplog(caplog):
    """Testa a configuração de logging usando o caplog conforme solicitado."""
    # Instala nosso formatter no handler do caplog
    caplog.handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("test_caplog")
    # Força a emissão mesmo que o nível não seja INFO
    logger.setLevel(logging.INFO)

    token = set_request_id("req-caplog")
    try:
        logger.info("Test message for caplog", extra={"password": "supersecret", "custom_data": "visible"})
    finally:
        # Quando formatar, o record tentará pegar o request_id corrente,
        # que já estará None caso o token seja limpo antes. O record é formatado tarde.
        # Portanto, nós vamos extrair o texto de caplog aqui dentro.
        pass

    try:
        # Pega o texto formatado final de todas as entradas
        lines = caplog.text.strip().split("\n")
        # A última entrada deve ser nossa log msg
        data = json.loads(lines[-1])

        assert data["message"] == "Test message for caplog"
        assert data["logger"] == "test_caplog"
        assert data["level"] == "info"
        assert data["request_id"] == "req-caplog"
        assert data["password"] == "***"
        assert data["custom_data"] == "visible"
    finally:
        reset_request_id(token)
