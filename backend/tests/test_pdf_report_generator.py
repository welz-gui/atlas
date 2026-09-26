from app.services.pdf_report_generator import RegulatoryReportGenerator

def test_fmt_none():
    assert RegulatoryReportGenerator._fmt(None) == "não informado"

def test_fmt_float_default_decimals():
    assert RegulatoryReportGenerator._fmt(10.5) == "10.50"

def test_fmt_float_custom_decimals():
    assert RegulatoryReportGenerator._fmt(10.5, decimals=1) == "10.5"
    assert RegulatoryReportGenerator._fmt(10.5, decimals=3) == "10.500"

def test_fmt_float_unit_percentage():
    assert RegulatoryReportGenerator._fmt(10.5, unit="%") == "10.50%"

def test_fmt_float_unit_other():
    assert RegulatoryReportGenerator._fmt(10.5, unit="m²") == "10.50 m²"

def test_fmt_integer():
    assert RegulatoryReportGenerator._fmt(10) == "10"
    assert RegulatoryReportGenerator._fmt(10, unit="unidades") == "10 unidades"

def test_fmt_string():
    assert RegulatoryReportGenerator._fmt("texto") == "texto"
    assert RegulatoryReportGenerator._fmt("texto", unit="unidades") == "texto unidades"
