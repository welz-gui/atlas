"""Extração assistida — o extrator não pode inventar medida alguma."""

import builtins
import re
import sys

import pytest

from app.services import pdf_parser
from app.services.pdf_parser import (
    EXPECTED_FIELDS,
    PDFPlanParser,
    fold_accents,
    parse_number,
)

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


# =============================================================================
# Caminhos de falha — o extrator diz "não extraí", nunca inventa
# =============================================================================


def test_numero_ilegivel_vira_aviso_e_nao_valor():
    res = PDFPlanParser.parse_text_content("Área do Terreno: 1,234.56.7 m²")

    assert res["lot_area"] is None
    assert any(
        "valor '1,234.56.7' não pôde ser interpretado" in w for w in res["warnings"]
    )


def test_inteiro_ilegivel_vira_aviso_e_nao_valor(monkeypatch):
    # O padrão real só casa dígitos, então o ramo de erro só é alcançável
    # forçando um padrão que case texto.
    monkeypatch.setattr(
        pdf_parser,
        "_COMPILED_INT_PATTERNS",
        [("floors", re.compile(r"Pavimentos: (.*)"), "pavimentos")],
    )

    res = PDFPlanParser.parse_text_content("Pavimentos: abc")

    assert res["floors"] is None
    assert any(
        "Nº de Pavimentos: valor 'abc' não pôde ser interpretado" in w
        for w in res["warnings"]
    )


def test_nada_encontrado_e_nao_verificavel():
    res = PDFPlanParser._finalize_extraction({}, [], [])

    assert res["status"] == "nao_verificavel"
    assert res["fields_found"] == 0


def test_extrair_texto_de_arquivo_vazio():
    texto, avisos = PDFPlanParser.extract_text(b"\xff\xfe\x00\x00", "memorial.rtf")

    assert texto == ""
    assert any("Formato de 'memorial.rtf' não suportado" in a for a in avisos)


def test_pypdf_indisponivel_nao_derruba_a_extracao(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)

    texto, avisos = PDFPlanParser.extract_text(b"%PDF-1.4 x", "prancha.pdf")

    assert texto == ""
    assert any("Biblioteca de leitura de PDF indisponível" in a for a in avisos)


def test_pdf_corrompido_vira_aviso(monkeypatch):
    import pypdf

    def _falha(*_args, **_kwargs):
        raise Exception("PDF corrompido")

    monkeypatch.setattr(pypdf, "PdfReader", _falha)

    texto, avisos = PDFPlanParser.extract_text(b"%PDF-1.4 x", "prancha.pdf")

    assert texto == ""
    assert any("Falha ao ler o PDF: PDF corrompido" in a for a in avisos)


@pytest.mark.parametrize("conteudo_da_pagina", [None, "   "])
def test_pdf_sem_camada_de_texto_avisa_que_precisa_de_ocr(
    monkeypatch, conteudo_da_pagina
):
    import pypdf

    class _Pagina:
        def extract_text(self):
            return conteudo_da_pagina

    class _Leitor:
        def __init__(self, _stream):
            self.pages = [_Pagina()]

    monkeypatch.setattr(pypdf, "PdfReader", _Leitor)

    texto, avisos = PDFPlanParser.extract_text(b"%PDF-1.4 x", "prancha.pdf")

    assert not texto.strip()
    assert any("não contém camada de texto" in a for a in avisos)


@pytest.mark.parametrize("interrupcao", [KeyboardInterrupt, SystemExit])
def test_interrupcao_do_operador_nao_e_engolida(monkeypatch, interrupcao):
    """O `except` amplo da importação não pode capturar Ctrl+C nem `sys.exit`."""
    importar_de_verdade = builtins.__import__

    def _importar(nome, *args, **kwargs):
        if nome == "pypdf":
            raise interrupcao()
        return importar_de_verdade(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _importar)

    with pytest.raises(interrupcao):
        PDFPlanParser.extract_text(b"%PDF-1.4 x", "prancha.pdf")


@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("Área construída", "Area construida"),
        ("çãõñüÇÃÕÑÜ", "caonuCAONU"),
        ("áéíóúÁÉÍÓÚ", "aeiouAEIOU"),
        ("vovó, avô, maçã", "vovo, avo, maca"),
        ("abc 123", "abc 123"),
        ("123 m²", "123 m²"),
        ("", ""),
    ],
)
def test_fold_accents_remove_diacriticos_e_preserva_o_comprimento(bruto, esperado):
    """O comprimento importa: é o que permite recortar a evidência do original."""
    resultado = fold_accents(bruto)

    assert resultado == esperado
    assert len(resultado) == len(bruto)
