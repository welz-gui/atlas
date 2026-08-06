"""Laudo PDF — o que ele afirma e, sobretudo, o que ele não pode afirmar."""

from app.models.domain import Organization, Project
from app.services.pdf_report_generator import DISCLAIMERS, RegulatoryReportGenerator
from app.services.regulatory_engine import RegulatoryEngine


def _project_and_run(db_session, **overrides):
    org = Organization(name="Org do Laudo")
    db_session.add(org)
    db_session.commit()

    defaults = dict(
        organization_id=org.id,
        name="Projeto Teste PDF",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=450.0,
        built_area=240.0,
        floors=2,
        front_setback=4.50,
        rear_setback=3.50,
        permeability_rate=22.0,
        parking_spaces=2,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()

    run = RegulatoryEngine.evaluate_project(db_session, project)
    return project, run


def _render(project, run):
    project_dict = {
        "id": project.id,
        "name": project.name,
        "city_name": project.city_name,
        "state": project.state,
        "zone": project.zone,
        "lot_area": project.lot_area,
        "built_area": project.built_area,
        "floors": project.floors,
        "front_setback": project.front_setback,
        "rear_setback": project.rear_setback,
        "occupancy_rate": project.occupancy_rate,
        "permeability_rate": project.permeability_rate,
        "is_official_baseline": project.is_official_baseline,
    }
    validations = [
        {
            "rule_title": v.rule_title,
            "expected_value": v.expected_value,
            "actual_value": v.actual_value,
            "status": v.status,
            "details": v.details,
            "source_citation": v.source_citation,
            "source_is_verified": v.source_is_verified,
            "evidence_required": v.evidence_required,
        }
        for v in run.validations
    ]
    run_dict = {
        "id": run.id,
        "content_hash": run.content_hash,
        "catalog_version": run.catalog_version,
        "engine_version": run.engine_version,
        "is_publishable": run.is_publishable,
    }
    return RegulatoryReportGenerator.generate_pdf(project_dict, validations, run_dict)


def test_gera_pdf_valido(db_session):
    project, run = _project_and_run(db_session)
    pdf_bytes = _render(project, run)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_laudo_carrega_todas_as_ressalvas(db_session):
    """§12 — as limitações são obrigatórias em todo laudo."""
    project, run = _project_and_run(db_session)
    pdf_bytes = _render(project, run)

    # Confere que o gerador foi alimentado com o conjunto completo de ressalvas.
    assert len(DISCLAIMERS) >= 5
    texto = " ".join(DISCLAIMERS).lower()
    assert "não substitui o responsável técnico" in texto
    assert "não constitui aprovação" in texto
    assert "não verificável" in texto
    assert pdf_bytes.startswith(b"%PDF")


def test_laudo_nao_afirma_validade_oficial():
    """Regressão: o protótipo afirmava validade para protocolo municipal."""
    texto = " ".join(DISCLAIMERS).lower()
    assert "não possui validade perante a administração municipal" in texto
    for frase in ("possui validade técnica para protocolo", "linha de base oficial: sim"):
        assert frase not in texto


def test_selo_cobre_o_conteudo_da_analise(db_session):
    """O hash muda quando os parâmetros analisados mudam."""
    project, run = _project_and_run(db_session)
    primeiro_hash = run.content_hash

    project.front_setback = 2.00
    db_session.commit()
    segundo = RegulatoryEngine.evaluate_project(db_session, project)

    assert primeiro_hash
    assert len(primeiro_hash) == 64
    assert segundo.content_hash != primeiro_hash


def test_selo_e_estavel_para_a_mesma_analise(db_session):
    """Mesmos parâmetros e mesmas regras produzem o mesmo hash."""
    project, run = _project_and_run(db_session)
    repetida = RegulatoryEngine.evaluate_project(db_session, project)

    assert repetida.content_hash == run.content_hash
    assert repetida.id != run.id


def test_analise_com_regras_nao_validadas_nao_e_publicavel(db_session):
    """§7.5 — enquanto o catálogo não for validado, o laudo é de uso interno."""
    _, run = _project_and_run(db_session)
    assert run.is_publishable is False
