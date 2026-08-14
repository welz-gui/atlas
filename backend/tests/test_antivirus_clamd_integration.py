"""clamd de verdade (§6.6 — item D6).

**Pula quando `ANTIVIRUS_BACKEND` não é `clamav`**, pelo mesmo motivo do teste
de S3: sem daemon, mediria o dublê.

O que a suíte já cobria era o **protocolo**, com socket monkeypatchado: que a
resposta `FOUND` vira `infectado` e que daemon fora do ar vira
`nao_verificado`. O que faltava é o que só o clamd responde — se a varredura
por `INSTREAM` funciona de fato contra um daemon com assinaturas carregadas, e
se o EICAR é reconhecido.

O EICAR é o arquivo-teste padrão da indústria, feito exatamente para isto: não
é malware, e todo antivírus o reconhece. É montado por concatenação para que a
cadeia completa não fique no repositório e dispare varreduras alheias.
"""

import os

import pytest

from app.services.antivirus import ClamAVScanner, ScanStatus

BACKEND = os.environ.get("ANTIVIRUS_BACKEND", "")

pytestmark = pytest.mark.skipif(
    BACKEND != "clamav",
    reason="Sem ANTIVIRUS_BACKEND=clamav: não há daemon para exercitar.",
)

#: Assinatura de teste EICAR, montada em partes.
EICAR = (
    r"X5O!P%@AP[4\PZX54(P^)7CC)7}$"
    + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    + r"!$H+H*"
).encode("ascii")


@pytest.fixture
def scanner():
    return ClamAVScanner(
        host=os.environ.get("ANTIVIRUS_HOST", "127.0.0.1"),
        port=int(os.environ.get("ANTIVIRUS_PORT", "3310")),
    )


def _arquivo(tmp_path, nome, conteudo):
    caminho = tmp_path / nome
    caminho.write_bytes(conteudo)
    return str(caminho)


# --- O daemon responde -------------------------------------------------------


def test_daemon_esta_no_ar_e_informa_a_versao(scanner):
    versao = scanner._version()

    assert versao, "clamd não respondeu ao VERSION"
    assert "ClamAV" in versao


# --- Detecção ----------------------------------------------------------------


def test_eicar_e_reconhecido_como_infectado(scanner, tmp_path):
    """A prova de que a varredura acontece de verdade."""
    resultado = scanner.scan_file(_arquivo(tmp_path, "eicar.txt", EICAR))

    assert resultado.status == ScanStatus.INFECTADO
    assert resultado.is_infected is True
    assert resultado.signature, "o daemon precisa dizer o que encontrou"
    assert "EICAR" in resultado.signature.upper()


def test_arquivo_limpo_passa(scanner, tmp_path):
    conteudo = b"%PDF-1.4 memorial descritivo sem nada demais"
    resultado = scanner.scan_file(_arquivo(tmp_path, "limpo.pdf", conteudo))

    assert resultado.status == ScanStatus.LIMPO
    assert resultado.is_clean is True
    assert resultado.signature is None


def test_arquivo_grande_atravessa_o_instream(scanner, tmp_path):
    """`INSTREAM` empurra em blocos; um PDF real não cabe num só."""
    conteudo = b"%PDF-1.4 " + b"a" * (2 * 1024 * 1024)
    resultado = scanner.scan_file(_arquivo(tmp_path, "grande.pdf", conteudo))

    assert resultado.status == ScanStatus.LIMPO


def test_eicar_no_meio_de_um_arquivo_maior_e_encontrado(scanner, tmp_path):
    """Quem esconde carga não a põe no primeiro byte."""
    conteudo = b"%PDF-1.4 " + b"z" * 100_000 + EICAR + b"y" * 100_000
    resultado = scanner.scan_file(_arquivo(tmp_path, "escondido.pdf", conteudo))

    assert resultado.status == ScanStatus.INFECTADO


# --- Proveniência da varredura -----------------------------------------------


def test_resultado_registra_a_versao_do_motor(scanner, tmp_path):
    """Sem isso, não dá para dizer contra quais assinaturas o arquivo passou."""
    resultado = scanner.scan_file(_arquivo(tmp_path, "limpo.pdf", b"conteudo"))

    assert resultado.engine_version
    assert resultado.scanned_at is not None
