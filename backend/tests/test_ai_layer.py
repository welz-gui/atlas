"""Camada de IA: recuperação, conferência de citações e proveniência (§3.3, §6.8).

O que precisa ficar provado, porque é aqui que o dano seria irreversível:

1. **a IA não publica** — rascunho extraído por modelo nasce e permanece em
   `rascunho_extraido_por_ia`, fora do motor e fora do laudo;
2. **a IA não inventa citação legal** — chave fora do contexto é descartada, a
   resposta cai para a busca determinística e a interação fica marcada;
3. **tudo fica registrado** — inclusive falhas, recusas e ausência de provedor.
"""

from datetime import datetime, timedelta

import pytest

from app.ai.provider import AIProvider, AIResult, NullProvider
from app.ai.retrieval import retrieve, tokenize
from app.ai.schemas import AssistantAnswer, RuleDraft, RuleDraftBatch, RuleDraftCheck
from app.ai.service import ask, extract_rule_drafts
from app.core.config import settings
from app.models.domain import AIInteraction, RegulatoryRule
from app.regulatory.catalog import RegulatoryCatalog, RuleState


class FakeProvider(AIProvider):
    """Provedor de mentira: devolve o que o teste mandar, sem rede."""

    name = "fake"
    available = True
    model = "fake-model-1"

    def __init__(self, parsed=None, error=None, refused=False):
        self.parsed = parsed
        self.error = error
        self.refused = refused
        self.calls = []

    def complete(self, system, prompt, output_model, max_tokens=2048, cacheable_prefix=None):
        self.calls.append(
            {"system": system, "prompt": prompt, "prefix": cacheable_prefix}
        )
        return AIResult(
            parsed=self.parsed,
            provider=self.name,
            model=self.model,
            refused=self.refused,
            error=self.error,
            stop_reason="refusal" if self.refused else "end_turn",
            input_tokens=100,
            output_tokens=50,
            latency_ms=42,
        )


@pytest.fixture
def catalog_rules(db_session, seeded_catalog):
    return RegulatoryCatalog.from_db(db_session, "BR-RS-4311403").for_jurisdiction(
        "BR-RS-4311403"
    )


# =============================================================================
# Recuperação
# =============================================================================

@pytest.mark.parametrize("input_text, expected", [
    ("Ação", "acao"),
    ("Coração", "coracao"),
    ("Árvore", "arvore"),
    ("Pão", "pao"),
    ("pé", "pe"),
    ("café", "cafe"),
    ("você", "voce"),
    ("MÚSICA", "musica"),
    ("não", "nao"),
    ("açúcar", "acucar"),
    ("", ""),
    ("123", "123"),
    ("AaBb", "aabb"),
])
def test_fold_remove_acentos_e_minusculas(input_text, expected):
    from app.ai.retrieval import fold
    assert fold(input_text) == expected


def test_tokenizacao_ignora_acento_e_palavra_vazia():
    assert "permeabilidade" in tokenize("Qual a taxa de permeabilidade mínima?")
    assert "de" not in tokenize("taxa de ocupação")


def test_recupera_regra_pelo_jargao_do_usuario(catalog_rules):
    """'afastamento' e 'alinhamento' são o que se fala; 'recuo' é o cadastrado."""
    encontradas = [r.rule_key for r in retrieve("afastamento frontal", catalog_rules)]
    assert "lajeado_recuo_frontal_z2" in encontradas

    encontradas = [r.rule_key for r in retrieve("quantas vagas de garagem", catalog_rules)]
    assert "lajeado_vagas_estacionamento" in encontradas


def test_consulta_fora_do_catalogo_nao_recupera_nada(catalog_rules):
    assert retrieve("custo do metro quadrado de alvenaria", catalog_rules) == []


def test_recuperacao_ordena_por_relevancia(catalog_rules):
    resultados = retrieve("taxa de permeabilidade do solo", catalog_rules)
    assert resultados
    assert resultados[0].rule_key == "lajeado_taxa_permeabilidade_min_z2"


# =============================================================================
# Assistente com modelo
# =============================================================================

def test_resposta_do_modelo_e_usada_quando_se_sustenta(
    db_session, engineer, seeded_catalog
):
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="O recuo frontal mínimo cadastrado para a Zona Z2 é de 4,00 m.",
            cited_rule_keys=["lajeado_recuo_frontal_z2"],
            suggested_actions=["Conferir a implantação."],
            answered_from_context=True,
        )
    )

    resposta = ask(db_session, "qual o recuo frontal", engineer, provider=provider)

    assert resposta.is_ai_generated is True
    assert resposta.method == "modelo_de_linguagem_sobre_catalogo"
    assert resposta.model == "fake-model-1"
    assert resposta.matched_rules == ["lajeado_recuo_frontal_z2"]
    # A citação é resolvida pelo catálogo, não pelo texto do modelo.
    assert any("Plano Diretor" in c for c in resposta.law_citations)


def test_a_politica_vai_no_prefixo_cacheavel(db_session, engineer, seeded_catalog):
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="ok", cited_rule_keys=[], answered_from_context=True
        )
    )
    ask(db_session, "recuo frontal", engineer, provider=provider)

    prefixo = provider.calls[0]["prefix"]
    assert "NUNCA cite artigo" in prefixo
    # O contexto recuperado vai no prompt, nunca no prefixo cacheado.
    assert "lajeado_recuo_frontal_z2" in provider.calls[0]["prompt"]
    assert "lajeado_recuo_frontal_z2" not in prefixo


def test_citacao_inventada_e_descartada(db_session, engineer, seeded_catalog):
    """O dano central: uma chave que não estava no contexto não pode passar."""
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="O recuo é de 10 m conforme a regra de gabarito de Porto Alegre.",
            cited_rule_keys=["porto_alegre_recuo_inventado"],
            answered_from_context=True,
        )
    )

    resposta = ask(db_session, "qual o recuo frontal", engineer, provider=provider)

    assert resposta.is_ai_generated is False
    assert "10 m" not in resposta.answer
    assert any("fora do catálogo" in w for w in resposta.warnings)

    registro = db_session.query(AIInteraction).order_by(
        AIInteraction.created_at.desc()
    ).first()
    assert registro.grounded is False
    assert "porto_alegre_recuo_inventado" not in registro.cited_rule_keys


def test_modelo_sem_base_no_contexto_cai_para_o_deterministico(
    db_session, engineer, seeded_catalog
):
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="Acho que são uns 3 metros.",
            cited_rule_keys=[],
            answered_from_context=False,
        )
    )

    resposta = ask(db_session, "recuo frontal", engineer, provider=provider)

    assert resposta.is_ai_generated is False
    assert "3 metros" not in resposta.answer
    assert any("não sustenta" in w for w in resposta.warnings)


def test_falha_do_provedor_nao_derruba_a_consulta(db_session, engineer, seeded_catalog):
    provider = FakeProvider(error="Limite de requisições do provedor atingido.")
    resposta = ask(db_session, "recuo frontal", engineer, provider=provider)

    assert resposta.is_ai_generated is False
    assert "Recuo Frontal" in resposta.answer  # o catálogo respondeu
    assert any("Limite de requisições" in w for w in resposta.warnings)

    registro = db_session.query(AIInteraction).order_by(
        AIInteraction.created_at.desc()
    ).first()
    assert "Limite de requisições" in registro.error


def test_recusa_do_modelo_e_registrada_como_recusa(db_session, engineer, seeded_catalog):
    provider = FakeProvider(refused=True, error="O modelo recusou-se a responder.")
    resposta = ask(db_session, "recuo frontal", engineer, provider=provider)

    assert resposta.is_ai_generated is False
    registro = db_session.query(AIInteraction).order_by(
        AIInteraction.created_at.desc()
    ).first()
    assert registro.stop_reason == "refusal"


def test_sem_contexto_o_modelo_nem_e_consultado(db_session, engineer, seeded_catalog):
    """Perguntar sem contexto é convidar o modelo a preencher a lacuna."""
    provider = FakeProvider(
        parsed=AssistantAnswer(answer="qualquer", cited_rule_keys=[], answered_from_context=True)
    )

    resposta = ask(
        db_session, "custo do metro quadrado de alvenaria", engineer, provider=provider
    )

    assert provider.calls == []
    assert resposta.is_ai_generated is False
    assert "Não encontrei" in resposta.answer


def test_sem_provedor_a_resposta_e_deterministica_e_registrada(
    db_session, engineer, seeded_catalog
):
    resposta = ask(db_session, "recuo frontal", engineer, provider=NullProvider())

    assert resposta.is_ai_generated is False
    assert resposta.method == "busca_por_palavra_chave_no_catalogo"
    assert resposta.interaction_id is not None

    registro = db_session.query(AIInteraction).one()
    assert registro.provider == "none"
    assert registro.answer_is_advisory is True


# =============================================================================
# Cache
# =============================================================================

def test_resposta_identica_vem_do_cache(db_session, engineer, seeded_catalog):
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="Recuo frontal mínimo: 4,00 m.",
            cited_rule_keys=["lajeado_recuo_frontal_z2"],
            answered_from_context=True,
        )
    )

    primeira = ask(db_session, "qual o recuo frontal", engineer, provider=provider)
    segunda = ask(db_session, "qual o recuo frontal", engineer, provider=provider)

    assert len(provider.calls) == 1
    assert segunda.served_from_cache is True
    assert segunda.answer == primeira.answer


def test_regra_alterada_invalida_o_cache(
    db_session, engineer, validator, seeded_catalog
):
    """Publicar a regra muda a resposta; o cache não pode segurar a antiga."""
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="Recuo frontal mínimo: 4,00 m.",
            cited_rule_keys=["lajeado_recuo_frontal_z2"],
            answered_from_context=True,
        )
    )
    ask(db_session, "qual o recuo frontal", engineer, provider=provider)

    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.rule_key == "lajeado_recuo_frontal_z2")
        .one()
    )
    regra.state = RuleState.VIGENTE
    regra.validated_by_name = validator.name
    regra.validated_at = datetime.utcnow()
    db_session.commit()

    ask(db_session, "qual o recuo frontal", engineer, provider=provider)
    assert len(provider.calls) == 2


def test_cache_desligado_sempre_consulta(
    db_session, engineer, seeded_catalog, monkeypatch
):
    monkeypatch.setattr(settings, "AI_CACHE_HOURS", 0)
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="ok", cited_rule_keys=["lajeado_recuo_frontal_z2"], answered_from_context=True
        )
    )

    ask(db_session, "recuo frontal", engineer, provider=provider)
    ask(db_session, "recuo frontal", engineer, provider=provider)
    assert len(provider.calls) == 2


def test_cache_nao_atravessa_organizacoes(db_session, engineer, seeded_catalog):
    from app.models.domain import UserRole
    from tests.conftest import make_org, make_user

    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="ok", cited_rule_keys=["lajeado_recuo_frontal_z2"], answered_from_context=True
        )
    )
    ask(db_session, "recuo frontal", engineer, provider=provider)

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-cache@atlas-qa.com")
    ask(db_session, "recuo frontal", intruso, provider=provider)

    assert len(provider.calls) == 2


# =============================================================================
# Extração de rascunhos — a IA propõe, não publica
# =============================================================================

def _batch():
    return RuleDraftBatch(
        drafts=[
            RuleDraft(
                rule_key="lajeado_recuo_lateral_z3",
                title="Recuo Lateral Mínimo — Zona Z3",
                severity="bloqueio",
                zones=["Z3"],
                building_types=["residencial_multifamiliar"],
                check=RuleDraftCheck(
                    field="side_setback", operator=">=", value=1.5, unit="m"
                ),
                evidence_required=["implantacao"],
                source_article="Art. 62, §1º",
                verbatim_excerpt="O recuo lateral mínimo será de 1,50 m (um metro e cinquenta).",
                confidence="alta",
            )
        ],
        notes="A tabela de zonas não foi fornecida.",
    )


def test_rascunho_nasce_como_rascunho_e_fora_do_motor(
    db_session, validator, seeded_catalog
):
    provider = FakeProvider(parsed=_batch())
    resultado = extract_rule_drafts(
        db_session, "texto legal qualquer", "BR-RS-4311403", validator, provider=provider
    )

    assert len(resultado.created_rule_ids) == 1
    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.id == resultado.created_rule_ids[0])
        .one()
    )

    assert regra.state == RuleState.RASCUNHO_EXTRAIDO_POR_IA
    assert regra.validated_by_id is None
    assert regra.validated_at is None

    # Fora do motor: rascunho não é estado executável.
    catalogo = RegulatoryCatalog.from_db(db_session, "BR-RS-4311403")
    executaveis = [r.rule_id for r in catalogo.executable_for("BR-RS-4311403")]
    assert "lajeado_recuo_lateral_z3" not in executaveis


def test_rascunho_registra_o_trecho_de_origem(db_session, validator, seeded_catalog):
    """O validador confere sem reabrir a lei."""
    resultado = extract_rule_drafts(
        db_session, "texto", "BR-RS-4311403", validator, provider=FakeProvider(parsed=_batch())
    )
    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.id == resultado.created_rule_ids[0])
        .one()
    )

    assert "1,50 m" in regra.notes
    assert "Conferir contra o texto legal" in regra.notes
    assert regra.events[0].action == "extraida_por_ia"
    assert regra.events[0].to_state == RuleState.RASCUNHO_EXTRAIDO_POR_IA


def test_rascunho_nao_sobrescreve_regra_existente(
    db_session, validator, seeded_catalog
):
    """Saída de modelo não altera cadastro que já passou por gente."""
    batch = RuleDraftBatch(
        drafts=[
            RuleDraft(
                rule_key="lajeado_recuo_frontal_z2",  # já existe no catálogo
                title="Título proposto pelo modelo",
                severity="alerta",
                check=RuleDraftCheck(field="front_setback", operator=">=", value=99.0),
                verbatim_excerpt="qualquer",
                confidence="baixa",
            )
        ]
    )
    resultado = extract_rule_drafts(
        db_session, "texto", "BR-RS-4311403", validator, provider=FakeProvider(parsed=batch)
    )

    assert resultado.created_rule_ids == []
    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.rule_key == "lajeado_recuo_frontal_z2")
        .one()
    )
    assert regra.check["value"] == 4.0
    assert regra.title != "Título proposto pelo modelo"


def test_exigencia_sem_numero_vira_analise_manual(db_session, validator, seeded_catalog):
    batch = RuleDraftBatch(
        drafts=[
            RuleDraft(
                rule_key="lajeado_ventilacao_natural",
                title="Ventilação Natural em Dormitórios",
                severity="bloqueio",
                check=None,
                verbatim_excerpt="Os dormitórios deverão dispor de ventilação natural.",
                confidence="media",
            )
        ]
    )
    resultado = extract_rule_drafts(
        db_session, "texto", "BR-RS-4311403", validator, provider=FakeProvider(parsed=batch)
    )
    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.id == resultado.created_rule_ids[0])
        .one()
    )

    assert regra.check is None
    assert regra.requires_manual_review is True


def test_extracao_sem_provedor_recusa_com_motivo(db_session, validator, seeded_catalog):
    resultado = extract_rule_drafts(
        db_session, "texto legal", "BR-RS-4311403", validator, provider=NullProvider()
    )

    assert resultado.created_rule_ids == []
    assert "Nenhum provedor de modelo configurado" in resultado.error
    assert resultado.interaction_id is not None


# =============================================================================
# Endpoints
# =============================================================================

def test_status_declara_ausencia_de_modelo(client, engineer_headers):
    body = client.get("/api/v1/ai/status", headers=engineer_headers).json()
    assert body["provider"] == "none"
    assert body["available"] is False
    assert "determinística" in body["description"]


def test_extracao_de_rascunho_exige_papel_de_validador(client, engineer_headers):
    response = client.post(
        "/api/v1/ai/rule-drafts",
        headers=engineer_headers,
        json={"legal_text": "x" * 100, "jurisdiction": "BR-RS-4311403"},
    )
    assert response.status_code == 403


def test_proveniencia_e_consultavel_pelo_validador(
    client, validator_headers, engineer_headers, seeded_catalog
):
    client.post(
        "/api/v1/ai/chat",
        headers=engineer_headers,
        json={"prompt": "recuo frontal"},
    )

    registros = client.get("/api/v1/ai/interactions", headers=validator_headers).json()
    assert len(registros) == 1
    assert registros[0]["provider"] == "none"
    assert registros[0]["answer_is_advisory"] is True
    assert "lajeado_recuo_frontal_z2" in registros[0]["retrieved_rule_keys"]


def test_proveniencia_nao_vaza_entre_organizacoes(
    client, db_session, engineer_headers, seeded_catalog
):
    from app.models.domain import UserRole
    from tests.conftest import auth_headers, make_org, make_user

    client.post(
        "/api/v1/ai/chat", headers=engineer_headers, json={"prompt": "recuo frontal"}
    )

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-prov@atlas-qa.com")

    registros = client.get(
        "/api/v1/ai/interactions", headers=auth_headers(client, intruso.email)
    ).json()
    assert registros == []
