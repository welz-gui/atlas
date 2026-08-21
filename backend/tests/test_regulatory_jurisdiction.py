from app.regulatory.jurisdiction import applicable_jurisdictions, jurisdiction_chain


def test_cadeia_municipal_inclui_brasil_estado_e_municipio():
    assert jurisdiction_chain("BR-RS-4301008") == ("BR", "BR-RS", "BR-RS-4301008")


def test_jurisdiction_chain_normalization():
    assert jurisdiction_chain(" br-sp-sao_paulo ") == ("BR", "BR-SP", "BR-SP-SAO_PAULO")


def test_jurisdiction_chain_not_br():
    assert jurisdiction_chain("US-NY-NEW_YORK") == ("US-NY-NEW_YORK",)
    assert jurisdiction_chain("XX") == ("XX",)


def test_jurisdiction_chain_empty_string():
    assert jurisdiction_chain("") == ("",)


def test_jurisdiction_chain_only_country():
    assert jurisdiction_chain("BR") == ("BR",)


def test_jurisdiction_chain_country_and_state():
    assert jurisdiction_chain("BR-SP") == ("BR", "BR-SP")


def test_jurisdiction_chain_more_than_three_parts():
    assert jurisdiction_chain("BR-SP-SAO_PAULO-CENTRO") == ("BR", "BR-SP", "BR-SP-SAO_PAULO")


def test_expansao_de_municipios_nao_inclui_municipio_vizinho():
    assert applicable_jurisdictions({"BR-RS-4311403", "BR-RS-4301008"}) == {
        "BR", "BR-RS", "BR-RS-4311403", "BR-RS-4301008"
    }
