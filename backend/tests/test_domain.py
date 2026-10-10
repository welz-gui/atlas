import uuid

from app.models.domain import _uuid


def test_uuid_gera_uuid4_em_texto_e_nunca_repete():
    """`_uuid` é o default de toda chave primária: texto, versão 4, único."""
    a, b = _uuid(), _uuid()

    assert isinstance(a, str)
    assert uuid.UUID(a).version == 4
    assert str(uuid.UUID(a)) == a
    assert a != b
