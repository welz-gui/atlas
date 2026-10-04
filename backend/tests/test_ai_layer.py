"""Camada de IA: recuperação, conferência de citações e proveniência (§3.3, §6.8).

O que precisa ficar provado, porque é aqui que o dano seria irreversível:

1. **a IA não publica** — rascunho extraído por modelo nasce e permanece em
   `rascunho_extraido_por_ia`, fora do motor e fora do laudo;
2. **a IA não inventa citação legal** — chave fora do contexto é descartada, a
   resposta cai para a busca determinística e a interação fica marcada;
3. **tudo fica registrado** — inclusive falhas, recusas e ausência de provedor.
"""

from datetime import datetime

import pytest

from app.ai.provider import AIProvider, AIRequest, AIResult, NullProvider
from app.ai.retrieval import retrieve, tokenize
from app.ai.schemas import AssistantAnswer, RuleDraft, RuleDraftBatch, RuleDraftCheck
from app.ai.service import AskContext, ExtractionContext, ask, extract_rule_drafts
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

    def complete(self, request: AIRequest) -> AIResult:
        self.calls.append(
            {"system": request.system, "prompt": request.prompt, "prefix": request.cacheable_prefix}
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


def test_tokenize_remove_punctuation_and_special_characters():
    assert tokenize("recuo, frontal: 4m!") == ["recuo", "frontal", "4m"]
    assert tokenize("taxa de ocupação (total)") == ["taxa", "ocupacao", "total"]


def test_tokenize_filters_short_words():
    # Palavras com tamanho <= 1 são removidas (e também stopwords)
    assert "a" not in tokenize("a casa")
    assert "o" not in tokenize("o predio")
    assert "1" not in tokenize("recuo 1 metro")


def test_tokenize_multiple_spaces():
    assert tokenize("recuo   frontal    total") == ["recuo", "frontal", "total"]


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


@pytest.mark.parametrize("consulta", ["", "   ", "a o de os"])
def test_consulta_vazia_ou_so_de_palavras_vazias_nao_recupera_nada(
    catalog_rules, consulta
):
    assert retrieve(consulta, catalog_rules) == []


def test_sem_regras_nao_ha_o_que_recuperar():
    assert retrieve("taxa de permeabilidade", []) == []


def test_recuperacao_ignora_caixa(catalog_rules):
    minuscula = retrieve("taxa de permeabilidade", catalog_rules)
    maiuscula = retrieve("TAXA DE PERMEABILIDADE", catalog_rules)

    assert minuscula
    assert [r.rule_key for r in minuscula] == [r.rule_key for r in maiuscula]


def test_resultado_ordena_por_escore_e_desempata_pela_chave(catalog_rules):
    """"taxa recuo" tem empate de escore: é ele que expõe o critério de desempate."""
    resultados = retrieve("taxa recuo", catalog_rules)

    assert len(resultados) >= 3
    assert len({r.score for r in resultados}) < len(resultados), "precisa haver empate"
    ordem = [(-r.score, r.rule_key) for r in resultados]
    assert ordem == sorted(ordem)


@pytest.mark.parametrize("limite", [1, 2, 3])
def test_limite_devolve_o_inicio_da_lista_ordenada(catalog_rules, limite):
    completo = retrieve("taxa recuo", catalog_rules)

    limitado = retrieve("taxa recuo", catalog_rules, limit=limite)

    assert [r.rule_key for r in limitado] == [r.rule_key for r in completo[:limite]]


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

    resposta = ask(AskContext(db=db_session, query="qual o recuo frontal", user=engineer, provider=provider))

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
    ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))

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

    resposta = ask(AskContext(db=db_session, query="qual o recuo frontal", user=engineer, provider=provider))

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

    resposta = ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))

    assert resposta.is_ai_generated is False
    assert "3 metros" not in resposta.answer
    assert any("não sustenta" in w for w in resposta.warnings)


def test_falha_do_provedor_nao_derruba_a_consulta(db_session, engineer, seeded_catalog):
    provider = FakeProvider(error="Limite de requisições do provedor atingido.")
    resposta = ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))

    assert resposta.is_ai_generated is False
    assert "Recuo Frontal" in resposta.answer  # o catálogo respondeu
    assert any("Limite de requisições" in w for w in resposta.warnings)

    registro = db_session.query(AIInteraction).order_by(
        AIInteraction.created_at.desc()
    ).first()
    assert "Limite de requisições" in registro.error


def test_recusa_do_modelo_e_registrada_como_recusa(db_session, engineer, seeded_catalog):
    provider = FakeProvider(refused=True, error="O modelo recusou-se a responder.")
    resposta = ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))

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

    resposta = ask(AskContext(db=db_session, query="custo do metro quadrado de alvenaria", user=engineer, provider=provider))

    assert provider.calls == []
    assert resposta.is_ai_generated is False
    assert "Não encontrei" in resposta.answer


def test_sem_provedor_a_resposta_e_deterministica_e_registrada(
    db_session, engineer, seeded_catalog
):
    resposta = ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=NullProvider()))

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

    primeira = ask(AskContext(db=db_session, query="qual o recuo frontal", user=engineer, provider=provider))
    segunda = ask(AskContext(db=db_session, query="qual o recuo frontal", user=engineer, provider=provider))

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
    ask(AskContext(db=db_session, query="qual o recuo frontal", user=engineer, provider=provider))

    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.rule_key == "lajeado_recuo_frontal_z2")
        .one()
    )
    regra.state = RuleState.VIGENTE
    regra.validated_by_name = validator.name
    regra.validated_at = datetime.utcnow()
    db_session.commit()

    ask(AskContext(db=db_session, query="qual o recuo frontal", user=engineer, provider=provider))
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

    ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))
    ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))
    assert len(provider.calls) == 2


def test_cache_nao_atravessa_organizacoes(db_session, engineer, seeded_catalog):
    from app.models.domain import UserRole
    from tests.conftest import make_org, make_user

    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="ok", cited_rule_keys=["lajeado_recuo_frontal_z2"], answered_from_context=True
        )
    )
    ask(AskContext(db=db_session, query="recuo frontal", user=engineer, provider=provider))

    outra = make_org(db_session, "Concorrente S.A.")
    intruso = make_user(db_session, outra, UserRole.OWNER, "intruso-cache@atlas-qa.com")
    ask(AskContext(db=db_session, query="recuo frontal", user=intruso, provider=provider))

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
        "texto legal qualquer",
        ExtractionContext(db=db_session, user=validator, jurisdiction="BR-RS-4311403", provider=provider),
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
        "texto",
        ExtractionContext(db=db_session, user=validator, jurisdiction="BR-RS-4311403", provider=FakeProvider(parsed=_batch())),
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
        "texto",
        ExtractionContext(db=db_session, user=validator, jurisdiction="BR-RS-4311403", provider=FakeProvider(parsed=batch)),
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
        "texto",
        ExtractionContext(db=db_session, user=validator, jurisdiction="BR-RS-4311403", provider=FakeProvider(parsed=batch)),
    )
    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.id == resultado.created_rule_ids[0])
        .one()
    )

    assert regra.check is None
    assert regra.requires_manual_review is True


def test_falha_do_provedor_na_extracao_nao_cria_rascunho(
    db_session, validator, seeded_catalog
):
    """Modelo que falha não pode deixar regra pela metade — e a falha fica registrada."""
    antes = db_session.query(RegulatoryRule).count()

    resultado = extract_rule_drafts(
        "texto legal",
        ExtractionContext(
            db=db_session,
            user=validator,
            jurisdiction="BR-RS-4311403",
            provider=FakeProvider(error="Limite de requisições do provedor atingido."),
        ),
    )

    assert resultado.created_rule_ids == []
    assert "Limite de requisições" in resultado.error
    assert db_session.query(RegulatoryRule).count() == antes

    registro = db_session.query(AIInteraction).order_by(
        AIInteraction.created_at.desc()
    ).first()
    assert registro.id == resultado.interaction_id
    assert "Limite de requisições" in registro.error


def test_extracao_sem_provedor_recusa_com_motivo(db_session, validator, seeded_catalog):
    resultado = extract_rule_drafts(
        "texto legal",
        ExtractionContext(db=db_session, user=validator, jurisdiction="BR-RS-4311403", provider=NullProvider()),
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

def test_reset_provider_cache():
    from app.ai.provider import get_provider, reset_provider_cache

    provider1 = get_provider()
    provider2 = get_provider()
    assert provider1 is provider2, "get_provider() should return a cached instance"

    reset_provider_cache()

    provider3 = get_provider()
    assert provider1 is not provider3, "reset_provider_cache() should clear the cache so a new instance is returned"


# =============================================================================
# Citação — artigo de regra não validada não aparece (§7.5)
# =============================================================================


def _regra_com_artigo(db_session, rule_key, artigo):
    regra = (
        db_session.query(RegulatoryRule)
        .filter(RegulatoryRule.rule_key == rule_key)
        .one()
    )
    regra.source_article = artigo
    db_session.commit()
    return regra


def test_resposta_deterministica_nao_cita_artigo_de_regra_nao_validada(
    db_session, engineer, seeded_catalog
):
    """O aviso da resposta diz que o artigo foi omitido — tem de ser verdade."""
    regra = _regra_com_artigo(db_session, "lajeado_recuo_frontal_z2", "Art. 99-X")
    assert regra.validated_by_name is None

    resposta = ask(
        AskContext(
            db=db_session, query="recuo frontal", user=engineer, provider=NullProvider()
        )
    )

    assert any("omitida" in w for w in resposta.warnings)
    assert not any("Art. 99-X" in c for c in resposta.law_citations)
    assert any("artigo não verificado" in c for c in resposta.law_citations)


def test_resposta_do_modelo_tambem_nao_cita_artigo_de_regra_nao_validada(
    db_session, engineer, seeded_catalog
):
    _regra_com_artigo(db_session, "lajeado_recuo_frontal_z2", "Art. 99-X")
    provider = FakeProvider(
        parsed=AssistantAnswer(
            answer="Recuo frontal mínimo: 4,00 m.",
            cited_rule_keys=["lajeado_recuo_frontal_z2"],
            answered_from_context=True,
        )
    )

    resposta = ask(
        AskContext(
            db=db_session, query="qual o recuo frontal", user=engineer, provider=provider
        )
    )

    assert resposta.is_ai_generated is True
    assert not any("Art. 99-X" in c for c in resposta.law_citations)


def test_regra_validada_continua_citando_o_artigo(
    db_session, engineer, validator, seeded_catalog
):
    """O outro lado: omitir tem de valer só para o que não foi conferido."""
    regra = _regra_com_artigo(db_session, "lajeado_recuo_frontal_z2", "Art. 45")
    regra.state = RuleState.VIGENTE
    regra.validated_by_name = validator.name
    regra.validated_at = datetime.utcnow()
    db_session.commit()

    resposta = ask(
        AskContext(
            db=db_session, query="recuo frontal", user=engineer, provider=NullProvider()
        )
    )

    assert any("Art. 45" in c for c in resposta.law_citations)



# =============================================================================
# ask(): jurisdição do projeto e formatação do que foi recuperado
# =============================================================================
def _projeto(cidade_ibge, cidade):
    from app.models.domain import Project

    return Project(
        name="Projeto de Teste",
        organization_id="org",
        city_ibge=cidade_ibge,
        city_name=cidade,
    )


def test_projeto_de_outro_municipio_nao_usa_o_catalogo_de_lajeado(
    db_session, engineer, seeded_catalog
):
    provider = FakeProvider(
        parsed=AssistantAnswer(answer="qualquer", cited_rule_keys=[], answered_from_context=True)
    )

    resposta = ask(
        AskContext(
            db=db_session,
            query="recuo frontal",
            user=engineer,
            project=_projeto("BR-RS-4316907", "Santa Maria"),
            provider=provider,
        )
    )

    assert provider.calls == []  # nada recuperado: o modelo nem é consultado
    assert resposta.matched_rules == []
    assert "Não encontrei no catálogo de Santa Maria" in resposta.answer


def test_projeto_de_lajeado_acrescenta_o_contexto_e_o_status_da_verificacao(
    db_session, engineer, seeded_catalog
):
    resposta = ask(
        AskContext(
            db=db_session,
            query="recuo frontal",
            user=engineer,
            project=_projeto("BR-RS-4311403", "Lajeado"),
            statuses={"lajeado_recuo_frontal_z2": "conforme"},
            provider=NullProvider(),
        )
    )

    assert "lajeado_recuo_frontal_z2" in resposta.matched_rules
    assert "esta verificação está 'conforme'" in resposta.answer
    assert "Empreendimento em contexto: 'Projeto de Teste' — Lajeado" in resposta.answer


def test_regra_sem_verificacao_numerica_vira_pedido_de_analise_tecnica(
    db_session, engineer, seeded_catalog
):
    db_session.add(
        RegulatoryRule(
            rule_key="lajeado_marquise_sobre_calcada",
            jurisdiction="BR-RS-4311403",
            title="Marquise sobre a calçada",
            state="vigente",
            check=None,
            requires_manual_review=True,
            evidence_required=["projeto arquitetônico"],
        )
    )
    db_session.commit()

    resposta = ask(
        AskContext(db=db_session, query="marquise calçada", user=engineer, provider=NullProvider())
    )

    assert resposta.matched_rules == ["lajeado_marquise_sobre_calcada"]
    assert "verificação documental (não derivável de parâmetros numéricos)" in resposta.answer
    assert resposta.suggested_actions == [
        "Providenciar análise técnica de marquise sobre a calçada (projeto arquitetônico)."
    ]
