"""Descoberta automática encontra normas; pessoas continuam publicando regras."""

from app.models.domain import JobType, RegulatoryDocument, RegulatoryDocumentState
from app.regulatory.discovery import SOURCES, discover_applicable_regulations, discover_regulations, extract_candidates
from app.workers.queue import HANDLERS


HTML = """
<html><body>
  <a href="/leis/plano-diretor">Lei 11.052/2020 - Plano Diretor</a>
  <a href="https://leismunicipais.com.br/codigo-de-obras-lajeado-rs">
    Lei 5.848/1996 - Código de Obras
  </a>
  <a href="/arquivos/mapa-zoneamento.pdf">Anexo 01 - Mapa de Zoneamento</a>
  <a href="https://example.com/lei">Lei 999/2026 - Uso do Solo</a>
  <a href="/servicos/parcelamento">Parcelamento do Solo</a>
  <a href="/noticia/1">Notícia sobre uma obra pública</a>
</body></html>
"""


def test_extrai_apenas_normas_relevantes_em_dominios_permitidos():
    source = SOURCES["BR-RS-4311403"][0]
    found = extract_candidates(HTML, source)

    assert len(found) == 3
    assert {item.number for item in found} == {"11.052/2020", "5.848/1996", None}
    assert {item.doc_type for item in found} == {"lei", "anexo_regulatorio"}
    assert all("example.com" not in item.url for item in found)


def test_descoberta_e_idempotente_e_nao_cria_regras(db_session):
    result = discover_regulations(
        db_session, "BR-RS-4311403", fetcher=lambda _url: HTML
    )
    again = discover_regulations(
        db_session, "BR-RS-4311403", fetcher=lambda _url: HTML
    )

    assert result["created"] == 3
    assert result["requires_human_validation"] is True
    assert again["created"] == 0
    assert again["unchanged"] == 3
    assert db_session.query(RegulatoryDocument).count() == 3
    assert all(
        row.state == RegulatoryDocumentState.DESCOBERTO
        for row in db_session.query(RegulatoryDocument).all()
    )


def test_descoberta_nao_rebaixa_documento_validado(db_session):
    discover_regulations(db_session, "BR-RS-4311403", fetcher=lambda _url: HTML)
    document = db_session.query(RegulatoryDocument).first()
    document.state = RegulatoryDocumentState.VALIDADO
    original_title = document.title
    db_session.commit()

    changed_html = HTML.replace(original_title, f"{original_title} - consolidado")
    discover_regulations(
        db_session, "BR-RS-4311403", fetcher=lambda _url: changed_html
    )
    db_session.refresh(document)

    assert document.state == RegulatoryDocumentState.VALIDADO
    assert document.title == original_title


def test_endpoint_exige_validador_e_registra_trabalho(
    client, engineer_headers, validator_headers
):
    assert client.post(
        "/api/v1/catalog/jobs/discovery", headers=engineer_headers
    ).status_code == 403

    original = HANDLERS[JobType.DESCOBERTA_REGULATORIA]
    HANDLERS[JobType.DESCOBERTA_REGULATORIA] = lambda _db, record: {
        "jurisdiction": record.payload["jurisdiction"],
        "created": 2,
        "requires_human_validation": True,
    }
    try:
        response = client.post(
            "/api/v1/catalog/jobs/discovery", headers=validator_headers
        )
    finally:
        HANDLERS[JobType.DESCOBERTA_REGULATORIA] = original

    assert response.status_code == 200
    assert response.json()["job"]["job_type"] == JobType.DESCOBERTA_REGULATORIA
    assert response.json()["job"]["result"]["created"] == 2


def test_endpoint_recusa_jurisdicao_sem_fontes(client, validator_headers):
    response = client.post(
        "/api/v1/catalog/jobs/discovery?jurisdiction=BR-SP-3550308",
        headers=validator_headers,
    )
    assert response.status_code == 422
    assert "fontes oficiais" in response.json()["detail"]


def test_descoberta_de_arroio_inclui_fontes_nacionais_e_municipais(db_session):
    result = discover_applicable_regulations(
        db_session, "BR-RS-4301008", fetcher=lambda _url: "<html></html>"
    )
    assert result["jurisdictions_checked"] == ["BR", "BR-RS-4301008"]
    assert result["created"] == 6
    assert {row.jurisdiction for row in db_session.query(RegulatoryDocument).all()} == {
        "BR", "BR-RS-4301008"
    }


def test_endpoint_usa_municipio_do_projeto(client, engineer_headers, validator_headers):
    project = client.post(
        "/api/v1/projects", headers=engineer_headers,
        json={"name": "Projeto Arroio", "city_ibge": "BR-RS-4301008", "city_name": "Arroio do Meio", "state": "RS"},
    ).json()
    original = HANDLERS[JobType.DESCOBERTA_REGULATORIA]
    HANDLERS[JobType.DESCOBERTA_REGULATORIA] = lambda _db, record: {
        "jurisdiction": record.payload["jurisdiction"], "created": 0, "requires_human_validation": True,
    }
    try:
        response = client.post(
            f"/api/v1/catalog/jobs/discovery?project_id={project['id']}", headers=validator_headers,
        )
    finally:
        HANDLERS[JobType.DESCOBERTA_REGULATORIA] = original
    assert response.status_code == 200
    assert response.json()["job"]["project_id"] == project["id"]
    assert response.json()["job"]["result"]["jurisdiction"] == "BR-RS-4301008"


HTML_HOST_SEM_WWW = """
<html><body>
  <a href="https://lajeado.rs.gov.br/leis/plano-diretor">Lei 11.052/2020 - Plano Diretor</a>
  <a href="https://www.lajeado.rs.gov.br/leis/codigo">Lei 5.848/1996 - Código de Obras</a>
</body></html>
"""


def test_lajeado_sem_www_fica_fora_por_certificado_invalido():
    """Decisão sobre **este** host, não política sobre hosts sem `www`.

    `lajeado.rs.gov.br` sem `www` responde com certificado autoassinado.

    Verificado em 2026-08-13. Nenhum dos 183 links dos índices oficiais aponta
    para lá — todos usam `www.`. Mantê-lo na lista só abriria caminho para uma
    busca falhar por certificado, e a correção tentadora nessa hora é desligar
    a verificação, que é pior que o problema original.
    """
    source = SOURCES["BR-RS-4311403"][0]

    assert "lajeado.rs.gov.br" not in source.allowed_hosts
    assert "www.lajeado.rs.gov.br" in source.allowed_hosts

    found = extract_candidates(HTML_HOST_SEM_WWW, source)
    urls = {item.url for item in found}

    assert urls == {"https://www.lajeado.rs.gov.br/leis/codigo"}


def test_leismunicipais_entra_sem_www():
    """O contraexemplo, e é por isso que ele tem teste próprio.

    Os índices referenciam este host **sem** `www` — 21 links no primeiro. Uma
    "padronização" que removesse as versões sem `www` quebraria a descoberta
    de 21 normas. Não há regra sobre `www`; há verificação por host.
    """
    source = SOURCES["BR-RS-4311403"][0]
    assert "leismunicipais.com.br" in source.allowed_hosts
