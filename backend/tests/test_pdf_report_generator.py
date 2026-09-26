"""Gerador do laudo em PDF (§12) — o que o documento afirma sobre si mesmo."""

import io

import pytest
from pypdf import PdfReader

from app.services.pdf_report_generator import RegulatoryReportGenerator


def _texto_do_pdf(pdf: bytes) -> str:
    leitor = PdfReader(io.BytesIO(pdf))
    return "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)


def _projeto():
    return {
        "name": "Residência Teste",
        "city_name": "Lajeado",
        "state": "RS",
        "zone": "Z2",
        "lot_area": 450.0,
        "built_area": 240.0,
        "front_setback": 4.5,
        "rear_setback": 3.5,
        "occupancy_rate": 53.3,
        "permeability_rate": 22.5,
        "floors": 2,
        "is_official_baseline": True,
        "version_number": 1,
        "version_state": "aprovada",
    }


def _validacoes():
    return [
        {
            "status": "conforme",
            "rule_title": "Recuo Frontal Mínimo",
            "expected_value": ">= 4,00 m",
            "actual_value": "4,50 m",
            "source_citation": "Plano Diretor",
            "source_is_verified": True,
        },
        {
            "status": "nao_verificavel",
            "rule_title": "Ventilação Natural",
            "expected_value": "exigida",
            "actual_value": "não informado",
            "details": "Exige análise documental.",
            "evidence_required": "planta baixa",
        },
    ]


def _run(publicavel: bool):
    return {
        "id": "run-1",
        "content_hash": "hash-1",
        "catalog_version": "1.0.0",
        "engine_version": "2.0.0",
        "is_publishable": publicavel,
    }


# =============================================================================
# _fmt — ausência é dita, nunca preenchida com zero
# =============================================================================


@pytest.mark.parametrize(
    "valor, kwargs, esperado",
    [
        (None, {}, "não informado"),
        (None, {"unit": "m²"}, "não informado"),
        (10.5, {}, "10.50"),
        (10.5, {"decimals": 1}, "10.5"),
        (10.5, {"decimals": 3}, "10.500"),
        (10.5, {"unit": "m²"}, "10.50 m²"),
        (10.5, {"unit": "%"}, "10.50%"),
        (0.1234, {"unit": "%", "decimals": 1}, "0.1%"),
        (10, {}, "10"),
        (10, {"unit": "pavimentos"}, "10 pavimentos"),
        ("texto", {}, "texto"),
        ("texto", {"unit": "un"}, "texto un"),
    ],
)
def test_fmt(valor, kwargs, esperado):
    assert RegulatoryReportGenerator._fmt(valor, **kwargs) == esperado


def test_fmt_zero_e_valor_nao_e_ausencia():
    """Regressão clássica: tratar 0.0 como 'falsy' diria 'não informado'."""
    assert RegulatoryReportGenerator._fmt(0.0) == "0.00"
    assert RegulatoryReportGenerator._fmt(0) == "0"


# =============================================================================
# generate_pdf — gera o PDF de verdade, sem mock
# =============================================================================


def test_gera_pdf_de_verdade():
    pdf = RegulatoryReportGenerator.generate_pdf(_projeto(), _validacoes(), _run(False))

    assert pdf.startswith(b"%PDF")
    texto = _texto_do_pdf(pdf)
    assert "Recuo Frontal Mínimo" in texto
    assert "Ventilação Natural" in texto


def test_laudo_sem_regra_conferida_sai_marcado_como_uso_interno():
    """§7.5 — regra não validada por pessoa não vai ao cliente."""
    pdf = RegulatoryReportGenerator.generate_pdf(_projeto(), _validacoes(), _run(False))

    assert "USO INTERNO" in _texto_do_pdf(pdf)


def test_laudo_publicavel_nao_leva_a_marca_de_uso_interno():
    pdf = RegulatoryReportGenerator.generate_pdf(_projeto(), _validacoes(), _run(True))

    assert "USO INTERNO" not in _texto_do_pdf(pdf)


def test_parametro_ausente_e_dito_no_laudo_e_nao_vira_zero():
    projeto = _projeto()
    projeto["lot_area"] = None

    pdf = RegulatoryReportGenerator.generate_pdf(projeto, _validacoes(), _run(False))

    assert "não informado" in _texto_do_pdf(pdf)
