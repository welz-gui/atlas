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


def test_eicar_com_espaco_ao_fim_ainda_e_reconhecido(scanner, tmp_path):
    """O padrão EICAR admite espaços em branco ao fim, e só isso.

    A primeira versão deste teste embutia o EICAR no meio de um arquivo maior e
    esperava detecção. O clamd devolveu `limpo`, e estava certo: por definição
    do padrão, o arquivo de teste precisa ser a cadeia exata, opcionalmente
    seguida de espaço em branco. Antivírus não o detectam embutido de
    propósito, para que o arquivo de teste não vire falso positivo dentro de
    conteúdo legítimo.

    O teste ficou para registrar isso — o engano era meu sobre o padrão, não
    defeito do scanner.
    """
    conteudo = EICAR + b"  " + bytes([10])
    resultado = scanner.scan_file(_arquivo(tmp_path, "com-espaco.txt", conteudo))

    assert resultado.status == ScanStatus.INFECTADO


# --- Proveniência da varredura -----------------------------------------------


def test_resultado_registra_a_versao_do_motor(scanner, tmp_path):
    """Sem isso, não dá para dizer contra quais assinaturas o arquivo passou."""
    resultado = scanner.scan_file(_arquivo(tmp_path, "limpo.pdf", b"conteudo"))

    assert resultado.engine_version
    assert resultado.scanned_at is not None
