"""Extração assistida — o extrator não pode inventar medida alguma."""

import pytest

from app.services.pdf_parser import EXPECTED_FIELDS, PDFPlanParser, parse_number

QUADRO_COMPLETO = """
MEMORIAL DESCRITIVO E QUADRO DE ÁREAS
Projeto Arquitetônico Unifamiliar
Área do Terreno: 450,00 m²
Área Construída: 240,00 m²
Recuo Frontal: 4,50 m
Recuo Fundos: 3,50 m
Taxa de Permeabilidade: 20,0 %
Nº de Pavimentos: 2
"""


def test_extrai_quadro_de_areas_completo():
    res = PDFPlanParser.parse_text_content(QUADRO_COMPLETO)

    assert res["lot_area"] == 450.0
    assert res["built_area"] == 240.0
    assert res["front_setback"] == 4.50
    assert res["rear_setback"] == 3.50
    assert res["permeability_rate"] == 20.0
    assert res["floors"] == 2
    assert res["status"] == "extraido"
    assert res["fields_found"] == len(EXPECTED_FIELDS)


def test_texto_vazio_nao_produz_numeros():
    """Regressão: o protótipo devolvia um quadro de áreas fictício aqui."""
    res = PDFPlanParser.parse_text_content("")

    assert res["status"] == "nao_verificavel"
    assert res["fields_found"] == 0
    for name in EXPECTED_FIELDS:
        assert res[name] is None
    assert res["warnings"]


def test_pdf_sem_camada_de_texto_nao_produz_numeros():
    res = PDFPlanParser.parse_file(b"%PDF-1.4 conteudo binario invalido", "prancha.pdf")

    assert res["status"] == "nao_verificavel"
    for name in EXPECTED_FIELDS:
        assert res[name] is None
    assert res["warnings"]


def test_documento_sem_o_parametro_deixa_campo_ausente():
    res = PDFPlanParser.parse_text_content("Área do Terreno: 380,00 m²")

    assert res["lot_area"] == 380.0
    assert res["front_setback"] is None
    assert res["status"] == "extraido_parcial"
    assert any("Recuo Frontal" in w for w in res["warnings"])


def test_evidencia_cita_o_trecho_de_origem():
    res = PDFPlanParser.parse_text_content(QUADRO_COMPLETO)
    assert any("Área do Terreno: 450,00 m²" in item for item in res["evidence"])


def _pdf_com_texto(linhas):
    """Gera um PDF real, com camada de texto, para exercitar o pypdf."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for linha in linhas:
        pdf.drawString(50, y, linha)
        y -= 18
    pdf.save()
    return buffer.getvalue()


def test_extrai_de_pdf_real_com_camada_de_texto():
    pdf_bytes = _pdf_com_texto([
        "QUADRO DE AREAS",
        "Area do Terreno: 512,40 m²",
        "Area Construida: 268,15 m²",
        "Recuo Frontal: 5,10 m",
        "N de Pavimentos: 3",
    ])

    res = PDFPlanParser.parse_file(pdf_bytes, "prancha.pdf")

    assert res["lot_area"] == 512.40
    assert res["built_area"] == 268.15
    assert res["front_setback"] == 5.10
    assert res["floors"] == 3
    # O que não estava no documento continua ausente.
    assert res["rear_setback"] is None
    assert res["permeability_rate"] is None
    assert res["status"] == "extraido_parcial"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("450,00", 450.0),      # decimal brasileiro
        ("450.00", 450.0),      # decimal inglês
        ("1.234,56", 1234.56),  # milhar brasileiro
        ("1,234.56", 1234.56),  # milhar inglês
        ("1.234", 1234.0),      # ponto como separador de milhar
        ("2", 2.0),
        ("", None),
        ("abc", None),
        ("1.234.567", 1234567.0),  # múltiplos pontos (milhar sem decimal)
        ("1,234,567", 1234567.0),  # múltiplas vírgulas (milhar sem decimal)
        ("1.234.567,89", 1234567.89), # múltiplos pontos (milhar com decimal brasileiro)
        ("1,234,567.89", 1234567.89), # múltiplas vírgulas (milhar com decimal inglês)
        ("1a", None),              # string com letras junto aos dígitos falha no float
        ("123 abc", None),         # string com espaços e letras falha no float
        ("1-2-3", None),           # string com hifens falha no float
        ("123,456.78.9", None),    # excesso de pontos e vírgulas combinados
    ],
)
def test_normalizacao_de_numeros(raw, expected):
    assert parse_number(raw) == expected
