from app.ai.service import deterministic_answer, QueryContext
from app.ai.retrieval import RetrievedRule
from app.regulatory.catalog import RegulatoryCatalog, Rule, RuleSource, RuleState
from app.models.domain import Project, ProjectVersion

def test_deterministic_answer_with_retrieved_rules():
    # Setup
    rule = Rule(
        rule_id="lajeado_recuo_frontal",
        title="Recuo Frontal",
        jurisdiction="lajeado",
        state=RuleState.VIGENTE,
        severity="bloqueio",
        validated_by="user123",
        source=RuleSource(
            url="http://example.com/law",
            document="Lei 123",
            article="Art. 4"
        ),
        check={"field": "front_setback", "operator": ">=", "value": 4.0, "unit": "m"}
    )
    retrieved_rule = RetrievedRule(rule=rule, score=0.9)

    context = QueryContext(
        query="qual o recuo?",
        retrieved=[retrieved_rule],
        catalog=RegulatoryCatalog(rules=[], versions={"lajeado": "1.0.0"}),
        jurisdiction="lajeado",
        municipality="Lajeado",
        statuses={"lajeado_recuo_frontal": "conforme"}
    )

    # Execute
    response = deterministic_answer(context)

    # Verify
    assert "O catálogo regulatório do Atlas para Lajeado registra os seguintes parâmetros relacionados à sua consulta:" in response.answer
    assert "Recuo Frontal: >= 4.00 m" in response.answer
    assert "conforme" in response.answer
    assert "Recuo Frontal — Lei 123, Art. 4" in response.law_citations[0]
    assert len(response.matched_rules) == 1
    assert response.matched_rules[0] == "lajeado_recuo_frontal"
    assert response.is_ai_generated is False
    assert response.method == "busca_por_palavra_chave_no_catalogo"


def test_deterministic_answer_without_retrieved_rules():
    rule = Rule(
        rule_id="lajeado_taxa_ocupacao",
        title="Taxa de Ocupação",
        jurisdiction="lajeado",
        state=RuleState.VIGENTE,
        severity="bloqueio",
        source=RuleSource(document="Lei 456", article="Art. 5")
    )
    catalog = RegulatoryCatalog(rules=[rule], versions={"lajeado": "1.0.0"})

    context = QueryContext(
        query="qual o recuo?",
        retrieved=[],
        catalog=catalog,
        jurisdiction="lajeado",
        municipality="Lajeado"
    )

    # Execute
    response = deterministic_answer(context)

    # Verify
    assert "Não encontrei no catálogo de Lajeado nenhum parâmetro" in response.answer
    assert "Taxa de Ocupação" in response.answer
    assert "Catálogo regulatório de Lajeado" in response.law_citations[0]
    assert len(response.matched_rules) == 0
    assert response.is_ai_generated is False


def test_deterministic_answer_with_project_context():
    rule = Rule(
        rule_id="lajeado_recuo_frontal",
        title="Recuo Frontal",
        jurisdiction="lajeado",
        state=RuleState.VIGENTE,
        severity="bloqueio",
        validated_by="user123",
        source=RuleSource(document="Lei 123", article="Art. 4")
    )
    retrieved_rule = RetrievedRule(rule=rule, score=0.9)

    project = Project(name="Edifício Teste")
    project_version = ProjectVersion(zone="Z3", lot_area=500.0, built_area=1200.0, version_number=1)
    project.versions = [project_version]

    context = QueryContext(
        query="recuo",
        retrieved=[retrieved_rule],
        catalog=RegulatoryCatalog(rules=[], versions={"lajeado": "1.0.0"}),
        jurisdiction="lajeado",
        municipality="Lajeado",
        project=project
    )

    # Execute
    response = deterministic_answer(context)

    # Verify
    assert "Empreendimento em contexto: 'Edifício Teste'" in response.answer
    assert "zona Z3" in response.answer
    assert "lote 500.0 m²" in response.answer
    assert "área construída 1200.0 m²" in response.answer


def test_deterministic_answer_with_unvalidated_rule():
    rule = Rule(
        rule_id="lajeado_recuo_frontal",
        title="Recuo Frontal",
        jurisdiction="lajeado",
        state=RuleState.RASCUNHO_EXTRAIDO_POR_IA,
        severity="bloqueio",
        source=RuleSource(document="Lei 123", article="Art. 4")
    )
    retrieved_rule = RetrievedRule(rule=rule, score=0.9)

    context = QueryContext(
        query="recuo",
        retrieved=[retrieved_rule],
        catalog=RegulatoryCatalog(rules=[], versions={"lajeado": "1.0.0"}),
        jurisdiction="lajeado",
        municipality="Lajeado"
    )

    # Execute
    response = deterministic_answer(context)

    # Verify
    assert "regra ainda não validada tecnicamente" in response.answer
    assert len(response.warnings) == 1
    assert "Atenção:" in response.answer
