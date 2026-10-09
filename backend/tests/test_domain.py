import uuid
from app.models.domain import _uuid

def test_uuid_returns_string():
    """Test that _uuid returns a string."""
    result = _uuid()
    assert isinstance(result, str)

def test_uuid_returns_valid_uuid4():
    """Test that _uuid returns a valid UUID version 4."""
    result = _uuid()
    parsed_uuid = uuid.UUID(result)
    assert parsed_uuid.version == 4
    assert str(parsed_uuid) == result

def test_uuid_returns_unique_values():
    """Test that consecutive calls to _uuid return unique values."""
    uuid1 = _uuid()
    uuid2 = _uuid()
    assert uuid1 != uuid2
