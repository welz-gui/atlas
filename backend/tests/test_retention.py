from datetime import datetime, timedelta
from app.services.retention import retention_deadline
from app.core.config import settings


def test_retention_deadline_explicit_days():
    now = datetime(2025, 1, 1)
    result = retention_deadline(now, retention_days=10)
    assert result == now + timedelta(days=10)


def test_retention_deadline_zero_days():
    now = datetime(2025, 1, 1)
    result = retention_deadline(now, retention_days=0)
    assert result is None


def test_retention_deadline_negative_days():
    now = datetime(2025, 1, 1)
    result = retention_deadline(now, retention_days=-5)
    assert result is None


def test_retention_deadline_uses_settings_when_none(monkeypatch):
    monkeypatch.setattr(settings, "OBSOLETE_RETENTION_DAYS", 15)
    now = datetime(2025, 1, 1)
    result = retention_deadline(now)
    assert result == now + timedelta(days=15)
