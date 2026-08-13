from app.regulatory.jurisdiction import applicable_jurisdictions, jurisdiction_chain


def test_cadeia_municipal_inclui_brasil_estado_e_municipio():
    assert jurisdiction_chain("BR-RS-4301008") == ("BR", "BR-RS", "BR-RS-4301008")


def test_expansao_de_municipios_nao_inclui_municipio_vizinho():
    assert applicable_jurisdictions({"BR-RS-4311403", "BR-RS-4301008"}) == {
        "BR", "BR-RS", "BR-RS-4311403", "BR-RS-4301008"
    }
