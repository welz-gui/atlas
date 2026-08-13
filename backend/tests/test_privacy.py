"""Retenção de conteúdo e atendimento a titular (LGPD).

Duas propriedades atravessam este arquivo, e são a razão de ele existir:

1. **o que sai é o conteúdo, nunca o registro.** Interação expurgada continua
   respondendo "de onde veio esta resposta"; empreendimento anonimizado
   continua tendo análises íntegras;
2. **nada some por padrão.** Retenção desligada não expurga, e as operações
   simulam a menos que se peça o contrário.
"""

from datetime import datetime, timedelta

import pytest

from app.models.domain import AIInteraction, JobRecord, JobStatus, Project
from app.services import privacy
from app.services.retention import (
    purge_expired_ai_interactions,
    purge_expired_job_records,
)


def _interacao(db, org_id, dias_atras=0, **extras):
    interaction = AIInteraction(
        organization_id=org_id,
        purpose="consulta_normativa",
        provider="none",
        model="determinístico",
        prompt="Qual o recuo frontal para a Zona Z2 na obra do Sr. Fulano?",
        request_hash="a" * 64,
        retrieved_rule_keys=["lajeado_recuo_frontal_z2"],
        cited_rule_keys=["lajeado_recuo_frontal_z2"],
        response_text="O recuo mínimo é de 4,00 m.",
        input_tokens=120,
        output_tokens=45,
        created_at=datetime.utcnow() - timedelta(days=dias_atras),
        **extras,
    )
    db.add(interaction)
    db.commit()
    return interaction


def _trabalho(db, org_id, status=JobStatus.CONCLUIDO, dias_atras=0):
    record = JobRecord(
        organization_id=org_id,
        job_type="extracao_documento",
        status=status,
        payload={"documento": "memorial.pdf", "solicitante": "Fulano de Tal"},
        result={"campos": 7},
        queued_at=datetime.utcnow() - timedelta(days=dias_atras),
    )
    db.add(record)
    db.commit()
    return record


# --- Retenção desligada ------------------------------------------------------


def test_retencao_desligada_nao_expurga_nada(db_session, org):
    """Zero é o padrão, e desliga. Nada some por inércia."""
    interacao = _interacao(db_session, org.id, dias_atras=3650)

    relatorio = purge_expired_ai_interactions(db_session, organization_id=org.id)

    assert relatorio.retention_enabled is False
    assert relatorio.purged == 0
    db_session.refresh(interacao)
    assert interacao.prompt


# --- Expurgo de interações de IA ---------------------------------------------


def test_expurgo_remove_conteudo_e_preserva_proveniencia(db_session, org):
    interacao = _interacao(db_session, org.id, dias_atras=100)

    relatorio = purge_expired_ai_interactions(
        db_session, organization_id=org.id, retention_days=90
    )

    assert relatorio.purged == 1
    db_session.refresh(interacao)

    # O conteúdo saiu.
    assert interacao.prompt == ""
    assert interacao.response_text is None
    assert interacao.content_purged_at is not None

    # A proveniência ficou — é o que responde "de onde veio esta resposta".
    assert interacao.model == "determinístico"
    assert interacao.input_tokens == 120
    assert interacao.retrieved_rule_keys == ["lajeado_recuo_frontal_z2"]
    assert interacao.request_hash == "a" * 64


def test_interacao_recente_nao_e_expurgada(db_session, org):
    interacao = _interacao(db_session, org.id, dias_atras=10)

    relatorio = purge_expired_ai_interactions(
        db_session, organization_id=org.id, retention_days=90
    )

    assert relatorio.purged == 0
    db_session.refresh(interacao)
    assert interacao.prompt


def test_simulacao_nao_altera_nada(db_session, org):
    interacao = _interacao(db_session, org.id, dias_atras=100)

    relatorio = purge_expired_ai_interactions(
        db_session, organization_id=org.id, retention_days=90, dry_run=True
    )

    assert relatorio.examined == 1
    assert relatorio.purged == 0
    db_session.refresh(interacao)
    assert interacao.prompt
    assert interacao.content_purged_at is None


# --- Expurgo de trabalhos ----------------------------------------------------


def test_trabalho_encerrado_perde_payload(db_session, org):
    trabalho = _trabalho(db_session, org.id, dias_atras=100)

    relatorio = purge_expired_job_records(
        db_session, organization_id=org.id, retention_days=30
    )

    assert relatorio.purged == 1
    db_session.refresh(trabalho)
    assert trabalho.payload == {}
    assert trabalho.result is None
    assert trabalho.content_purged_at is not None
    # O registro do trabalho permanece.
    assert trabalho.job_type == "extracao_documento"
    assert trabalho.status == JobStatus.CONCLUIDO


def test_trabalho_ainda_enfileirado_nao_e_tocado(db_session, org):
    """Expurgar o payload de um trabalho pendente o tornaria inexecutável."""
    trabalho = _trabalho(
        db_session, org.id, status=JobStatus.ENFILEIRADO, dias_atras=100
    )

    relatorio = purge_expired_job_records(
        db_session, organization_id=org.id, retention_days=30
    )

    assert relatorio.purged == 0
    db_session.refresh(trabalho)
    assert trabalho.payload["documento"] == "memorial.pdf"


# --- Anonimização ------------------------------------------------------------


@pytest.fixture
def projeto_com_titular(db_session, org):
    project = Project(
        organization_id=org.id,
        name="Residencial do Fulano",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS",
        owner_name="Fulano de Tal",
        owner_document="123.456.789-00",
        contractor_name="Construtora Beltrano Ltda.",
        technical_responsible_name="Eng. Sicrano",
        technical_responsible_registry="CREA-RS 12345",
    )
    db_session.add(project)
    db_session.commit()
    return project


def test_anonimizacao_redige_dado_pessoal_e_preserva_o_resto(
    db_session, projeto_com_titular
):
    relatorio = privacy.anonymize_project(
        db_session,
        projeto_com_titular,
        reason="Pedido de eliminação recebido do titular em 2026-08-12.",
        dry_run=False,
    )

    assert set(relatorio.fields_cleared) == {
        "owner_name",
        "owner_document",
        "contractor_name",
        "technical_responsible_name",
        "technical_responsible_registry",
    }

    db_session.refresh(projeto_com_titular)
    assert projeto_com_titular.owner_document == privacy.REDACTED
    assert "Fulano" not in (projeto_com_titular.owner_name or "")

    # O empreendimento continua existindo e localizável.
    assert projeto_com_titular.city_name == "Lajeado"
    assert projeto_com_titular.name == "Residencial do Fulano"
    assert projeto_com_titular.anonymized_at is not None
    assert "titular" in projeto_com_titular.anonymization_reason


def test_anonimizacao_e_idempotente(db_session, projeto_com_titular):
    """Pedir duas vezes não sobrescreve quando o titular foi atendido."""
    primeiro = privacy.anonymize_project(
        db_session, projeto_com_titular, reason="Primeiro pedido do titular.",
        dry_run=False,
    )
    segundo = privacy.anonymize_project(
        db_session, projeto_com_titular, reason="Pedido repetido do titular.",
        dry_run=False,
    )

    assert segundo.already_anonymized is True
    assert segundo.anonymized_at == primeiro.anonymized_at
    assert segundo.fields_cleared == []


def test_simulacao_de_anonimizacao_nao_altera(db_session, projeto_com_titular):
    relatorio = privacy.anonymize_project(
        db_session, projeto_com_titular, reason="Avaliando o pedido do titular.",
        dry_run=True,
    )

    assert len(relatorio.fields_cleared) == 5
    db_session.refresh(projeto_com_titular)
    assert projeto_com_titular.owner_name == "Fulano de Tal"
    assert projeto_com_titular.anonymized_at is None


# --- Permissão ---------------------------------------------------------------


def test_engenheiro_nao_anonimiza(client, engineer_headers, project):
    """Eliminar dado de terceiro é ato de gestão, não de operação."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/anonymize",
        headers=engineer_headers,
        json={"reason": "Pedido do titular recebido hoje."},
    )
    assert response.status_code == 403


def test_expurgo_exige_gestao(client, engineer_headers):
    response = client.post(
        "/api/v1/privacy/purge-ai-interactions", headers=engineer_headers
    )
    assert response.status_code == 403
