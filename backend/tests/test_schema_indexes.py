"""Os índices que sustentam as consultas quentes existem nos modelos.

`alembic check` na CI pega a deriva entre modelos e migrations, mas precisa de
Postgres e do ciclo completo. Estes testes falham na hora, e dizem **por que** o
índice existe — que é a informação que se perde quando alguém o remove por
parecer redundante.

A deriva que motivou o arquivo: os dois índices compostos existiam apenas nas
migrations. Como a suíte monta o banco com `create_all` a partir dos modelos,
ela rodava contra um esquema sem eles — isto é, testava algo que produção não
era.
"""

from app.models.domain import AIInteraction, JobRecord


def _index_columns(model, name):
    for index in model.__table__.indexes:
        if index.name == name:
            return [column.name for column in index.columns]
    return None


def test_cache_de_ia_tem_indice_composto():
    """`ai/service.py::_lookup_cache` filtra por (organização, hash).

    Sem o composto, a busca do cache varre todo o histórico de interações a
    cada consulta ao assistente.
    """
    assert _index_columns(AIInteraction, "ix_ai_interactions_org_hash") == [
        "organization_id",
        "request_hash",
    ]


def test_recuperacao_de_orfaos_tem_indice_composto():
    """`workers/worker.py::recover_orphans` filtra por (status, fila).

    Sem o composto, a varredura passa a tabela inteira a cada partida do worker.
    """
    assert _index_columns(JobRecord, "ix_job_records_status_queue") == [
        "status",
        "queue",
    ]


def test_colunas_de_lista_nao_aceitam_nulo():
    """Lista vazia diz "nada foi recuperado"; `NULL` não diz nada.

    Os dois seriam indistinguíveis em auditoria, e o código nunca escreve
    `NULL` — `ai/service.py` sempre passa lista, `workers/queue.py` faz
    `payload or {}`.
    """
    assert AIInteraction.__table__.c.retrieved_rule_keys.nullable is False
    assert AIInteraction.__table__.c.cited_rule_keys.nullable is False
    assert JobRecord.__table__.c.payload.nullable is False
