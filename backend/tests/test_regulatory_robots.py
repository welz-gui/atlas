"""Conformidade com `robots.txt` na descoberta regulatória (§7.2).

O caso que motiva o arquivo inteiro é `test_html_com_200_nao_e_robots_txt`:
verificado em 2026-08-13, `https://www.lajeado.rs.gov.br/robots.txt` devolve
**200 com HTML**. Um parser ingênuo lê o HTML, não acha diretiva válida e
libera tudo — conclusão certa, pelo motivo errado, e desastrosa num site que
tivesse regras de verdade.
"""

from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from app.regulatory.robots import (
    RobotsDenied,
    RobotsGate,
    RobotsPolicy,
    load_policy,
    parse_robots,
)


class _Resposta:
    """Dublê do que `urlopen` devolve."""

    def __init__(self, corpo: bytes, content_type: str = "text/plain", status: int = 200):
        self._corpo = BytesIO(corpo)
        self.status = status
        self.headers = _Headers(content_type)

    def read(self, n=None):
        return self._corpo.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Headers:
    def __init__(self, content_type: str):
        self._content_type = content_type

    def get(self, chave, padrao=None):
        if chave.lower() == "content-type":
            return self._content_type
        return padrao

    def get_content_charset(self):
        return "utf-8"


def _opener(resposta):
    def abrir(_url, _timeout):
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    return abrir


# --- Interpretação do arquivo ------------------------------------------------


def test_grupo_do_agente_prevalece_sobre_o_curinga():
    """Acumular os dois grupos inventaria regra que o arquivo não expressa."""
    regras = parse_robots(
        """
        User-agent: *
        Disallow: /

        User-agent: Atlas-Regulatory-Discovery
        Disallow: /admin
        Crawl-delay: 5
        """
    )
    assert regras["disallow"] == ("/admin",)
    assert regras["delay"] == 5.0


def test_disallow_vazio_libera_tudo():
    regras = parse_robots("User-agent: *\nDisallow:")
    assert regras["disallow"] == ()


def test_comentarios_e_linhas_invalidas_sao_ignorados():
    regras = parse_robots(
        "# comentário\nUser-agent: *\nDisallow: /privado  # nota\nlixo sem dois pontos\n"
    )
    assert regras["disallow"] == ("/privado",)


# --- Decisão de permissão ----------------------------------------------------


def test_regra_mais_especifica_vence():
    policy = RobotsPolicy(
        origin="https://exemplo.gov.br",
        disallow=("/leis",),
        allow=("/leis/publicas",),
    )
    assert policy.path_allowed("https://exemplo.gov.br/leis/publicas/1") is True
    assert policy.path_allowed("https://exemplo.gov.br/leis/internas/1") is False
    assert policy.path_allowed("https://exemplo.gov.br/outra") is True


# --- O caso de Lajeado -------------------------------------------------------


def test_html_com_200_nao_e_robots_txt():
    """200 com `text/html` significa "não há arquivo", não "sem regras lidas".

    O portal de Lajeado devolve o shell da própria página para `/robots.txt`.
    Exigir `text/plain` é o que impede tratar HTML como diretiva.
    """
    resposta = _Resposta(
        b"<!doctype html><html><title>Portal</title></html>",
        content_type="text/html; charset=UTF-8",
    )
    policy = load_policy("https://www.lajeado.rs.gov.br/conteudo/4516/969",
                         opener=_opener(resposta))

    assert policy.fetchable is True
    assert policy.disallow == ()
    assert "não publica robots.txt" in policy.reason
    assert policy.path_allowed("https://www.lajeado.rs.gov.br/conteudo/4516/969")


def test_arquivo_de_verdade_e_obedecido():
    resposta = _Resposta(b"User-agent: *\nDisallow: /conteudo\n")
    policy = load_policy("https://exemplo.gov.br/conteudo/1", opener=_opener(resposta))

    assert policy.reason == "robots.txt lido"
    assert policy.path_allowed("https://exemplo.gov.br/conteudo/1") is False


# --- Ausência libera; falha bloqueia ----------------------------------------


def test_404_significa_ausencia_e_libera():
    erro = HTTPError("https://x/robots.txt", 404, "Not Found", {}, None)
    policy = load_policy("https://exemplo.gov.br/a", opener=_opener(erro))

    assert policy.fetchable is True
    assert "ausente" in policy.reason


def test_403_e_tratado_como_ausencia_pela_rfc():
    """RFC 9309: 4xx é "não existe arquivo de regras"."""
    erro = HTTPError("https://x/robots.txt", 403, "Forbidden", {}, None)
    policy = load_policy("https://www.leismunicipais.com.br/a", opener=_opener(erro))

    assert policy.fetchable is True


@pytest.mark.parametrize("codigo", [429, 500, 503])
def test_falha_de_servidor_suspende_a_busca(codigo):
    """Não deu para perguntar. Não perguntar não é permissão (I10)."""
    erro = HTTPError("https://x/robots.txt", codigo, "erro", {}, None)
    policy = load_policy("https://exemplo.gov.br/a", opener=_opener(erro))

    assert policy.fetchable is False
    with pytest.raises(RobotsDenied):
        RobotsGate(loader=lambda _u: policy).check("https://exemplo.gov.br/a")


def test_rede_indisponivel_suspende_a_busca():
    policy = load_policy(
        "https://exemplo.gov.br/a", opener=_opener(URLError("sem rota"))
    )
    assert policy.fetchable is False
    assert "inacessível" in policy.reason


# --- Intervalo entre buscas --------------------------------------------------


def test_primeira_busca_nao_espera():
    dormidas = []
    relogio = iter([100.0, 100.0])
    gate = RobotsGate(
        loader=lambda _u: RobotsPolicy(origin="https://exemplo.gov.br"),
        sleeper=dormidas.append,
        clock=lambda: next(relogio),
    )
    policy = gate.check("https://exemplo.gov.br/a")
    gate.wait("https://exemplo.gov.br/a", policy)

    assert dormidas == []


def test_segunda_busca_ao_mesmo_host_respeita_o_intervalo():
    dormidas = []
    tempos = iter([100.0, 100.5, 102.0])
    gate = RobotsGate(
        loader=lambda _u: RobotsPolicy(origin="https://exemplo.gov.br"),
        sleeper=dormidas.append,
        clock=lambda: next(tempos),
    )
    policy = gate.policy_for("https://exemplo.gov.br/a")
    gate.wait("https://exemplo.gov.br/a", policy)
    gate.wait("https://exemplo.gov.br/b", policy)

    # Piso de 2 s, 0,5 s decorrido → dorme 1,5 s.
    assert dormidas == [pytest.approx(1.5)]


def test_crawl_delay_maior_que_o_piso_prevalece():
    policy = RobotsPolicy(origin="https://x", crawl_delay=10.0)
    assert policy.delay == 10.0


def test_crawl_delay_menor_nao_reduz_o_piso():
    """Cortesia declarada pelo site não autoriza ir mais rápido que o nosso piso."""
    policy = RobotsPolicy(origin="https://x", crawl_delay=0.1)
    assert policy.delay == 2.0


# --- Integração com a descoberta --------------------------------------------


def test_fonte_recusada_vira_resultado_e_nao_erro(db_session, monkeypatch):
    """Fonte proibida precisa aparecer no registro do trabalho, não sumir."""
    from app.regulatory import discovery

    def fetcher_recusado(_url, gate=None):
        raise RobotsDenied("https://exemplo.gov.br: proibido pelo robots.txt")

    resultado = discovery.discover_regulations(
        db_session, "BR-RS-4311403", fetcher=fetcher_recusado
    )

    assert resultado["candidates_found"] == 0
    assert resultado["sources_checked"] == []
    assert len(resultado["sources_skipped"]) == 2
    assert "proibido" in resultado["sources_skipped"][0]["reason"]
