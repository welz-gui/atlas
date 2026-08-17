"""Sonda de vida (§12).

A versão anterior deste arquivo fixava a resposta antiga:

    {"status": "healthy", "service": "Atlas API Backend", "version": "1.0.0"}

O problema não era o formato — era o `"healthy"`. A resposta era estática e
afirmava saúde sem apurar nada, de modo que a API se declarava saudável com o
banco fora do ar. O teste, ao travar aquele corpo, protegia a afirmação falsa.

A verificação de dependências mora agora em `/health/ready`, e está coberta em
`test_observabilidade.py`. Aqui fica o que esta sonda de fato promete: **o
processo responde**.
"""

from app.core.config import settings


def test_liveness_responde(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    corpo = response.json()

    # "vivo", e não "saudável": a sonda não consulta dependência nenhuma, e
    # dizer-se saudável seria afirmar mais do que se apurou.
    assert corpo["status"] == "vivo"
    assert corpo["service"] == settings.PROJECT_NAME
    assert corpo["version"] == settings.VERSION
    assert corpo["environment"] == settings.ENVIRONMENT


def test_liveness_dispensa_autenticacao(client):
    """Um orquestrador consulta a sonda sem credencial."""
    assert client.get("/api/v1/health").status_code == 200
