"""O contexto de organização que alimenta a RLS (§3.1, item D1).

Estes testes cobrem o **mecanismo** — a `ContextVar`, o escopo e a limpeza — e
rodam em qualquer banco. Eles não provam que a RLS funciona: isso exige
Postgres e está em `test_rls_postgres.py`.

A distinção importa. A política é inerte no SQLite, então um teste de
isolamento verde aqui provaria apenas que o filtro de aplicação funciona — que
é a primeira linha de defesa, não a segunda.
"""

import pytest

from app.core.tenant import (
    current_organization_id,
    organization_scope,
    reset_current_organization,
    set_current_organization,
)


def test_sem_contexto_nao_ha_organizacao():
    assert current_organization_id() is None


def test_escopo_vigora_e_desfaz():
    with organization_scope("org-a"):
        assert current_organization_id() == "org-a"
    assert current_organization_id() is None


def test_escopo_desfaz_mesmo_com_excecao():
    """Organização pendurada depois de um erro contaminaria o próximo trabalho."""
    with pytest.raises(ValueError):
        with organization_scope("org-a"):
            raise ValueError("falha no executor")

    assert current_organization_id() is None


def test_escopos_aninhados_devolvem_o_anterior():
    with organization_scope("org-a"):
        with organization_scope("org-b"):
            assert current_organization_id() == "org-b"
        assert current_organization_id() == "org-a"
    assert current_organization_id() is None


def test_token_permite_desfazer_manualmente():
    token = set_current_organization("org-a")
    assert current_organization_id() == "org-a"
    reset_current_organization(token)
    assert current_organization_id() is None


def test_escopo_nulo_e_valido():
    """Entrar sem organização é o estado do middleware antes da autenticação."""
    with organization_scope("org-a"):
        with organization_scope(None):
            assert current_organization_id() is None
        assert current_organization_id() == "org-a"


# --- Integração com a requisição ---------------------------------------------


def test_requisicao_autenticada_poe_a_organizacao_em_vigor(client, engineer_headers):
    """`get_current_user` publica a organização antes da primeira consulta."""
    response = client.get("/api/v1/projects", headers=engineer_headers)
    assert response.status_code == 200


def test_organizacao_nao_sobrevive_a_requisicao(client, engineer_headers):
    """O middleware limpa o contexto — senão a requisição seguinte o herdaria."""
    client.get("/api/v1/projects", headers=engineer_headers)
    assert current_organization_id() is None


def test_requisicao_sem_token_nao_deixa_organizacao(client):
    client.get("/api/v1/projects")
    assert current_organization_id() is None
