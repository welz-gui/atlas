"""Portal do cliente (§8.22).

O portal é onde um vazamento seria mais caro: o que sai daqui vai para quem
contratou a obra e pode virar decisão comercial ou protocolo. Por isso a
linha de corte é testada, não apenas comentada.
"""

from datetime import datetime

import pytest

from app.models.domain import (
    AnalysisRun,
    Document,
    DocumentState,
    EAPItem,
    RegulatoryRule,
    UserRole,
    ValidationRecord,
)
from app.regulatory.catalog import RuleState
from tests.conftest import auth_headers, make_org, make_user


@pytest.fixture
def client_user(db_session, org):
    return make_user(db_session, org, UserRole.CLIENT, "cliente-portal@atlas-qa.com")


@pytest.fixture
def client_headers(client, client_user):
    return auth_headers(client, client_user.email)


def _portal(client, headers, project_id):
    response = client.get(f"/api/v1/portal/projects/{project_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# =============================================================================
# A regra de publicabilidade vale no portal (§7.5)
# =============================================================================

def test_analise_nao_publicavel_nao_expoe_numeros(client, client_headers, project):
    """O catálogo semeado está todo em validação: nada de resultado."""
    body = _portal(client, client_headers, project["id"])

    conformidade = body["compliance"]
    assert conformidade["available"] is False
    assert "conferência técnica" in conformidade["reason"]
    # A existência da análise é reconhecida; os números, não.
    assert conformidade["analysed_at"] is not None
    assert conformidade["total_checks"] is None
    assert conformidade["blocking_count"] is None


def test_analise_publicavel_libera_o_resumo(
    client, client_headers, engineer_headers, db_session, project, validator
):
    """Publicada a regra, o resumo é liberado — e só então."""
    for regra in db_session.query(RegulatoryRule).all():
        regra.state = RuleState.VIGENTE
        regra.validated_by_name = validator.name
        regra.validated_by_id = validator.id
        regra.validated_at = datetime.utcnow()
        regra.source_article = "Art. 45"
    db_session.commit()

    client.post(f"/api/v1/projects/{project['id']}/evaluate", headers=engineer_headers)

    conformidade = _portal(client, client_headers, project["id"])["compliance"]
    assert conformidade["available"] is True
    assert conformidade["total_checks"] > 0
    assert conformidade["blocking_count"] is not None


def test_portal_nao_devolve_verificacao_individual(client, client_headers, project):
    """Só o agregado. Regra a regra é conversa entre técnicos."""
    body = _portal(client, client_headers, project["id"])
    texto = str(body)

    assert "lajeado_recuo_frontal_z2" not in texto
    assert "source_article" not in texto
    assert "rule_state" not in texto


# =============================================================================
# Documentos
# =============================================================================

def test_portal_mostra_apenas_documento_vigente(
    client, client_headers, engineer_headers, project, upload_dir
):
    from tests.test_documents import _upload

    v1 = _upload(client, engineer_headers, project["id"], "planta.pdf").json()
    _upload(
        client, engineer_headers, project["id"], "planta.pdf",
        version="v2.0", supersedes_id=v1["id"],
    )

    documentos = _portal(client, client_headers, project["id"])["current_documents"]
    assert len(documentos) == 1
    assert documentos[0]["version"] == "v2.0"


def test_portal_nao_expoe_caminho_nem_antivirus(
    client, client_headers, engineer_headers, project, upload_dir
):
    """Chave de armazenamento e situação de varredura são assunto interno."""
    from tests.test_documents import _upload

    _upload(client, engineer_headers, project["id"], "planta.pdf")
    documento = _portal(client, client_headers, project["id"])["current_documents"][0]

    assert "file_path" not in documento
    assert "antivirus_status" not in documento
    assert "hash_sha256" not in documento


# =============================================================================
# Tramitação e andamento
# =============================================================================

def test_portal_mostra_exigencias_abertas(
    client, client_headers, engineer_headers, project
):
    """O cliente precisa saber o que trava o processo dele."""
    protocolo = client.post(
        f"/api/v1/projects/{project['id']}/protocols",
        headers=engineer_headers,
        json={"protocol_number": "2026/00123", "agency": "Prefeitura de Lajeado"},
    ).json()

    client.post(
        f"/api/v1/protocols/{protocolo['id']}/requirements",
        headers=engineer_headers,
        json={"description": "Apresentar memorial de cálculo estrutural."},
    )

    protocolos = _portal(client, client_headers, project["id"])["protocols"]
    assert len(protocolos) == 1
    assert protocolos[0]["protocol_number"] == "2026/00123"
    assert len(protocolos[0]["open_requirements"]) == 1
    assert "memorial" in protocolos[0]["open_requirements"][0]["description"]


def test_exigencia_atendida_sai_da_lista(client, client_headers, engineer_headers, project):
    protocolo = client.post(
        f"/api/v1/projects/{project['id']}/protocols",
        headers=engineer_headers,
        json={"protocol_number": "2026/00124"},
    ).json()
    exigencia = client.post(
        f"/api/v1/protocols/{protocolo['id']}/requirements",
        headers=engineer_headers,
        json={"description": "Corrigir cota de soleira."},
    ).json()

    client.patch(
        f"/api/v1/requirements/{exigencia['id']}",
        headers=engineer_headers,
        json={"status": "atendida"},
    )

    protocolos = _portal(client, client_headers, project["id"])["protocols"]
    assert protocolos[0]["open_requirements"] == []


def test_progresso_fisico_vem_da_eap(client, client_headers, db_session, org, project):
    for code, name, pct in (("1", "Fundações", 100.0), ("2", "Estrutura", 40.0)):
        db_session.add(
            EAPItem(
                organization_id=org.id,
                project_id=project["id"],
                code=code,
                name=name,
                progress_percent=pct,
            )
        )
    db_session.commit()

    body = _portal(client, client_headers, project["id"])
    assert body["physical_progress_percent"] == 70.0
    assert len(body["milestones"]) == 2


def test_sem_eap_o_progresso_e_zero(client, client_headers, project):
    """Zero significa 'nada medido' — a interface é quem diz isso ao cliente."""
    body = _portal(client, client_headers, project["id"])
    assert body["physical_progress_percent"] == 0.0
    assert body["milestones"] == []


# =============================================================================
# Isolamento e papel
# =============================================================================

def test_cliente_nao_ve_empreendimento_de_outra_organizacao(
    client, db_session, project
):
    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.CLIENT, "cliente-intruso@atlas-qa.com")

    response = client.get(
        f"/api/v1/portal/projects/{project['id']}",
        headers=auth_headers(client, intruso.email),
    )
    assert response.status_code == 404

    listagem = client.get(
        "/api/v1/portal/projects", headers=auth_headers(client, intruso.email)
    ).json()
    assert listagem == []


def test_cliente_continua_sem_poder_escrever(client, client_headers, project):
    """O portal é leitura; o papel `client` não ganha nada com ele."""
    assert (
        client.post(
            f"/api/v1/projects/{project['id']}/evaluate", headers=client_headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/projects",
            headers=client_headers,
            json={"name": "Obra do cliente"},
        ).status_code
        == 403
    )


def test_equipe_tambem_acessa_o_portal(client, engineer_headers, project):
    """Útil para conferir o que o cliente está vendo antes de uma reunião."""
    body = _portal(client, engineer_headers, project["id"])
    assert body["name"] == "Residencial de Teste"


def test_portal_traz_a_ressalva(client, client_headers, project):
    body = _portal(client, client_headers, project["id"])
    assert "não substitui o projeto aprovado" in body["notice"]
