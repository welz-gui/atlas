"""Motor de regras: aplicabilidade, veredictos e append-only."""

from app.models.domain import AnalysisRun, Organization, Project, ValidationRecord
from app.regulatory.catalog import CheckOutcome, RuleState, catalog
from app.services.regulatory_engine import RegulatoryEngine


def _make_project(db_session, **overrides):
    org = Organization(name=overrides.pop("org_name", "Org de Teste"))
    db_session.add(org)
    db_session.commit()

    defaults = dict(
        organization_id=org.id,
        name="Projeto de Teste",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar",
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    return project


def test_projeto_conforme(db_session):
    project = _make_project(
        db_session,
        lot_area=450.0,
        built_area=240.0,    # 53,3% < 60%
        floors=2,            # <= 3
        front_setback=4.50,  # >= 4,00
        rear_setback=3.50,   # >= 3,00
        side_setback=1.80,
        permeability_rate=22.5,
        parking_spaces=2,
    )

    run = RegulatoryEngine.evaluate_project(db_session, project)
    status_map = {v.rule_id: v.status for v in run.validations}

    assert status_map["lajeado_recuo_frontal_z2"] == CheckOutcome.CONFORME
    assert status_map["lajeado_taxa_ocupacao_max_z2"] == CheckOutcome.CONFORME
    assert status_map["lajeado_recuo_fundos_z2"] == CheckOutcome.CONFORME
    assert status_map["lajeado_gabarito_maximo_z2"] == CheckOutcome.CONFORME
    assert status_map["lajeado_acessibilidade_nbr9050"] == CheckOutcome.NAO_VERIFICAVEL
    assert run.nao_conforme_count == 0


def test_projeto_nao_conforme(db_session):
    project = _make_project(
        db_session,
        lot_area=300.0,
        built_area=210.0,    # 70% > 60%
        floors=2,
        front_setback=3.00,  # < 4,00
        rear_setback=3.50,
        permeability_rate=22.0,
        parking_spaces=1,
    )

    run = RegulatoryEngine.evaluate_project(db_session, project)
    status_map = {v.rule_id: v.status for v in run.validations}

    assert status_map["lajeado_recuo_frontal_z2"] == CheckOutcome.NAO_CONFORME
    assert status_map["lajeado_taxa_ocupacao_max_z2"] == CheckOutcome.NAO_CONFORME
    assert run.nao_conforme_count >= 2


def test_parametro_ausente_nao_vira_nao_conforme(db_session):
    """Ausência de dado é `nao_verificavel`, jamais um veredicto negativo."""
    project = _make_project(db_session)  # nenhum parâmetro informado

    run = RegulatoryEngine.evaluate_project(db_session, project)
    status_map = {v.rule_id: v.status for v in run.validations}

    assert status_map["lajeado_recuo_frontal_z2"] == CheckOutcome.NAO_VERIFICAVEL
    assert status_map["lajeado_taxa_ocupacao_max_z2"] == CheckOutcome.NAO_VERIFICAVEL
    assert run.nao_conforme_count == 0
    assert run.nao_verificavel_count == run.total_checks


def test_severidade_alerta_produz_atencao(db_session):
    """Regra de severidade `alerta` gera `atencao`, não `nao_conforme`."""
    project = _make_project(
        db_session,
        lot_area=450.0, built_area=240.0, floors=2,
        front_setback=4.5, rear_setback=3.5,
        permeability_rate=22.0,
        parking_spaces=0,  # abaixo do mínimo, mas a regra é de alerta
    )

    run = RegulatoryEngine.evaluate_project(db_session, project)
    status_map = {v.rule_id: v.status for v in run.validations}

    assert status_map["lajeado_vagas_estacionamento"] == CheckOutcome.ATENCAO
    assert run.atencao_count == 1


def test_tolerancia_e_respeitada(db_session):
    """Recuo de 3,99 m passa com tolerância de 0,02 m."""
    project = _make_project(db_session, front_setback=3.99)

    run = RegulatoryEngine.evaluate_project(db_session, project)
    status_map = {v.rule_id: v.status for v in run.validations}

    assert status_map["lajeado_recuo_frontal_z2"] == CheckOutcome.CONFORME


def test_analises_sao_append_only(db_session):
    """Cada avaliação cria uma análise nova; nenhuma é apagada (§3.5)."""
    project = _make_project(db_session, front_setback=3.00)
    first = RegulatoryEngine.evaluate_project(db_session, project, trigger="project_created")

    project.front_setback = 4.50
    db_session.commit()
    second = RegulatoryEngine.evaluate_project(db_session, project, trigger="project_updated")

    assert first.id != second.id
    assert db_session.query(AnalysisRun).filter_by(project_id=project.id).count() == 2

    # Os registros da primeira análise continuam existindo, com o veredicto antigo.
    first_record = (
        db_session.query(ValidationRecord)
        .filter_by(analysis_run_id=first.id, rule_id="lajeado_recuo_frontal_z2")
        .one()
    )
    assert first_record.status == CheckOutcome.NAO_CONFORME

    # E o projeto expõe apenas a análise mais recente.
    latest = {v.rule_id: v.status for v in project.validations}
    assert latest["lajeado_recuo_frontal_z2"] == CheckOutcome.CONFORME


def test_jurisdicao_estrangeira_nao_aplica_regras_de_lajeado(db_session):
    """Regras de Lajeado não podem vazar para outro município."""
    project = _make_project(
        db_session,
        city_ibge="BR-SP-3550308",
        city_name="São Paulo",
        front_setback=1.0,
        parking_spaces=0,
    )

    run = RegulatoryEngine.evaluate_project(db_session, project)
    assert run.total_checks == 0


def test_taxa_de_ocupacao_tem_fonte_unica(db_session):
    """A taxa é sempre derivada de área construída ÷ área do lote."""
    project = _make_project(db_session, lot_area=400.0, built_area=200.0)
    assert project.occupancy_rate == 50.0

    sem_lote = _make_project(db_session, built_area=200.0)
    assert sem_lote.occupancy_rate is None


def test_nenhuma_regra_do_catalogo_e_publicavel_sem_validacao():
    """§7.5 — regra não validada não pode ir para laudo entregue ao cliente."""
    for rule in catalog.all_rules:
        if rule.state != RuleState.VIGENTE or rule.validated_by is None:
            assert not rule.is_publishable


def test_catalogo_nao_inventa_artigo():
    """Fonte legal não conferida não pode exibir número de artigo."""
    for rule in catalog.all_rules:
        if not rule.source.is_verified:
            assert rule.source.article is None
            assert "não verificado" in rule.source.citation()
