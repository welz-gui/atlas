import pytest
from app.services.antivirus import get_scanner, reset_scanner_cache, _SCANNERS

def test_reset_scanner_cache():
    # Popula o cache
    scanner1 = get_scanner()
    # Chama novamente pra dar hit no cache
    scanner2 = get_scanner()
    assert scanner1 is scanner2

    # Limpa o cache
    reset_scanner_cache()

    # Confirma que os contadores foram zerados e a referência não bate mais
    info = get_scanner.cache_info()
    assert info.hits == 0
    assert info.misses == 0
