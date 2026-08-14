"""Descoberta conservadora de normas em índices oficiais.

Este módulo encontra candidatos; ele não interpreta artigos, cria regras nem
publica conteúdo. Toda norma nova entra como ``descoberto`` e continua
dependendo da conferência de um validador técnico.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from datetime import datetime
from html.parser import HTMLParser
import re
import unicodedata
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models.domain import RegulatoryDocument, RegulatoryDocumentState
from app.regulatory.jurisdiction import jurisdiction_chain
from app.regulatory.robots import RobotsDenied, RobotsGate


@dataclass(frozen=True)
class DiscoveredDocument:
    title: str
    url: str
    doc_type: str
    number: str | None
    theme: str | None


@dataclass(frozen=True)
class DiscoverySource:
    jurisdiction: str
    url: str
    issuing_body: str
    allowed_hosts: tuple[str, ...]
    known_documents: tuple[DiscoveredDocument, ...] = ()


#: Hosts em que um candidato de Lajeado pode estar hospedado.
#:
#: **A lista é por fonte, não global.** Cada município novo traz a sua, e nada
#: aqui restringe outra jurisdição. Como montá-la está em `docs/OPERACAO.md`,
#: seção "Allowlist de um município novo" — o resumo é que cada host se
#: justifica por evidência, e não por convenção de nome.
#:
#: `lajeado.rs.gov.br` **sem `www`** ficou de fora de propósito: em 2026-08-13
#: ele responde com **certificado autoassinado**, e nenhum dos 183 links dos
#: dois índices oficiais aponta para lá — todos usam `www.`. Mantê-lo na lista
#: só criaria o caminho para uma busca falhar por certificado, e a correção
#: tentadora nessa hora é desligar a verificação, que é bem pior que o problema
#: original.
#:
#: `leismunicipais.com.br` entra **sem `www`** porque é assim que os índices o
#: referenciam — 21 links no primeiro índice. O oposto de Lajeado, e o motivo
#: de a lista ser conferida contra o HTML real em vez de suposta.
ALLOWED_HOSTS_LAJEADO = (
    "www.lajeado.rs.gov.br",
    "leismunicipais.com.br",
    "www.leismunicipais.com.br",
    "api.leismunicipais.com.br",
)

SOURCES: dict[str, tuple[DiscoverySource, ...]] = {
    "BR": (
        DiscoverySource(
            jurisdiction="BR",
            url="https://www.planalto.gov.br/ccivil_03/leis/l10098.htm",
            issuing_body="Presidência da República",
            allowed_hosts=("planalto.gov.br", "www.planalto.gov.br"),
            known_documents=(
                DiscoveredDocument(
                    title="Lei nº 10.098/2000 — Lei da Acessibilidade",
                    url="https://www.planalto.gov.br/ccivil_03/leis/l10098.htm",
                    doc_type="lei", number="10.098/2000", theme="acessibilidade",
                ),
            ),
        ),
        DiscoverySource(
            jurisdiction="BR",
            url="https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/decreto/d5296.htm",
            issuing_body="Presidência da República",
            allowed_hosts=("planalto.gov.br", "www.planalto.gov.br"),
            known_documents=(
                DiscoveredDocument(
                    title="Decreto nº 5.296/2004 — Regulamenta a acessibilidade",
                    url="https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/decreto/d5296.htm",
                    doc_type="decreto", number="5.296/2004", theme="acessibilidade",
                ),
            ),
        ),
        DiscoverySource(
            jurisdiction="BR",
            url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm",
            issuing_body="Presidência da República",
            allowed_hosts=("planalto.gov.br", "www.planalto.gov.br"),
            known_documents=(
                DiscoveredDocument(
                    title="Lei nº 13.146/2015 — Lei Brasileira de Inclusão",
                    url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm",
                    doc_type="lei", number="13.146/2015", theme="acessibilidade",
                ),
            ),
        ),
    ),
    "BR-RS-4311403": (
        DiscoverySource(
            jurisdiction="BR-RS-4311403",
            url=(
                "https://www.lajeado.rs.gov.br/conteudo/4516/969"
                "?titulo=Legisla%C3%A7%C3%A3o"
            ),
            issuing_body="Prefeitura Municipal de Lajeado",
            allowed_hosts=ALLOWED_HOSTS_LAJEADO,
        ),
        DiscoverySource(
            jurisdiction="BR-RS-4311403",
            url=(
                "https://www.lajeado.rs.gov.br/conteudo/3714/969"
                "?titulo=Plano+Diretor"
            ),
            issuing_body="Prefeitura Municipal de Lajeado",
            allowed_hosts=ALLOWED_HOSTS_LAJEADO,
        ),
    ),
    "BR-RS-4301008": (
        DiscoverySource(
            jurisdiction="BR-RS-4301008",
            url="https://arroiodomeio.rs.gov.br/legislacao",
            issuing_body="Prefeitura Municipal de Arroio do Meio",
            allowed_hosts=(
                "arroiodomeio.rs.gov.br", "www.arroiodomeio.rs.gov.br",
                "cespro.com.br", "www.cespro.com.br",
            ),
            known_documents=(
                DiscoveredDocument(
                    title="Lei nº 2.493/2006 — Código de Edificações",
                    url="https://arroiodomeio.rs.gov.br/uploads/midia/16431/LEI_N_2493_2006_Cdigo_de_edificaes.pdf",
                    doc_type="lei", number="2.493/2006", theme="edificações",
                ),
                DiscoveredDocument(
                    title="Lei nº 2.491/2006 — Parcelamento do Solo Urbano",
                    url="https://arroiodomeio.rs.gov.br/uploads/midia/16430/LEI_N_2491_2006_Parcelamento_do_solo_urbano.pdf",
                    doc_type="lei", number="2.491/2006", theme="parcelamento do solo",
                ),
                DiscoveredDocument(
                    title="Lei nº 3.269/2014 — Altera o Parcelamento do Solo Urbano",
                    url="https://arroiodomeio.rs.gov.br/uploads/midia/16432/LEI_N_3269_2014_Parcelamento_do_solo_urbano.pdf",
                    doc_type="lei", number="3.269/2014", theme="parcelamento do solo",
                ),
            ),
        ),
    ),
}

RELEVANT_THEMES = {
    "plano diretor": "planejamento urbano",
    "codigo de obras": "edificações",
    "aprovacao de projetos": "aprovação de projetos",
    "zoneamento": "zoneamento",
    "uso do solo": "uso do solo",
    "parcelamento": "parcelamento do solo",
    "recuo": "recuos",
    "calcada": "calçadas",
    "acessibilidade": "acessibilidade",
    "faixa nao edificavel": "faixa não edificável",
    "movimentacao de solo": "movimentação de solo",
    "efluentes": "saneamento",
    "parklet": "uso do passeio público",
    "patrimonio cultural": "patrimônio cultural",
}

LEGAL_NUMBER = re.compile(
    r"\b(lei(?:\s+complementar)?|decreto|instru[cç][aã]o\s+normativa)"
    r"\s*(?:n[º°o.]?\s*)?([\d.]+(?:[-/]\d{2,4})?)",
    re.IGNORECASE,
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        self._href = next((value for key, value in attrs if key == "href"), None)
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _clean(value: str) -> str:
    return " ".join(value.split()).strip(" -–—|\n\t")


def _classify(title: str) -> tuple[str, str | None]:
    match = LEGAL_NUMBER.search(title)
    if not match:
        return ("anexo_regulatorio" if "anexo" in _fold(title) else "outro", None)
    kind = _fold(match.group(1))
    doc_type = {
        "lei": "lei",
        "lei complementar": "lei_complementar",
        "decreto": "decreto",
        "instrucao normativa": "instrucao_normativa",
    }.get(kind, "outro")
    return doc_type, match.group(2)


def extract_candidates(html: str, source: DiscoverySource) -> list[DiscoveredDocument]:
    """Extrai apenas links regulatórios relevantes e hospedados em domínios permitidos."""
    parser = _LinkParser()
    parser.feed(html)
    found: dict[str, DiscoveredDocument] = {}

    for raw_href, raw_title in parser.links:
        title = _clean(raw_title)
        if not title:
            continue
        folded = _fold(title)
        theme = next((label for key, label in RELEVANT_THEMES.items() if key in folded), None)
        if theme is None:
            continue

        url = urljoin(source.url, raw_href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in source.allowed_hosts:
            continue

        doc_type, number = _classify(title)
        # Páginas de serviço e navegação podem conter as mesmas palavras-chave
        # ("aprovação", "parcelamento", "acessibilidade"). Sem espécie e
        # número legal, só anexos explicitamente nomeados são candidatos.
        if doc_type == "outro":
            continue
        found[url] = DiscoveredDocument(
            title=title,
            url=url,
            doc_type=doc_type,
            number=number,
            theme=theme,
        )

    return sorted(found.values(), key=lambda item: item.title.casefold())


def fetch_source(
    url: str,
    timeout: int = 30,
    max_bytes: int = 5_000_000,
    gate: RobotsGate | None = None,
) -> str:
    """Busca um índice oficial, depois de consultar o `robots.txt` da origem.

    O `gate` guarda a política por origem e impõe o intervalo entre buscas —
    ver `app.regulatory.robots`. Sem ele, cada chamada relê o arquivo, o que só
    faz sentido em uso avulso.
    """
    portao = gate or RobotsGate()
    policy = portao.check(url)
    portao.wait(url, policy)

    # O portal de Lajeado escolhe o template por um cookie de mídia e, na
    # primeira resposta sem ele, devolve apenas JavaScript para recarregar a
    # página. Declarar o layout desktop é equivalente ao que o navegador faz.
    request = Request(
        url,
        headers={
            "User-Agent": "Atlas-Regulatory-Discovery/1.0",
            "Cookie": "media=2",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL vem do registro fixo
        final_host = urlparse(response.geturl()).hostname
        configured_source = next(
            (
                source
                for sources in SOURCES.values()
                for source in sources
                if source.url == url
            ),
            None,
        )
        if configured_source and final_host not in configured_source.allowed_hosts:
            raise ValueError("A fonte oficial redirecionou para um domínio não permitido.")
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            raise ValueError(f"Fonte não devolveu HTML: {content_type or 'tipo desconhecido'}.")
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("Índice oficial excede o limite de 5 MB.")
        charset = response.headers.get_content_charset() or "utf-8"
        return content.decode(charset, errors="replace")


def discover_regulations(
    db: Session,
    jurisdiction: str,
    fetcher: Callable[[str], str] = fetch_source,
) -> dict:
    """Sincroniza candidatos encontrados, de forma idempotente por URL.

    Documento já validado nunca é rebaixado. Uma mudança de metadados apenas
    atualiza a data de consulta; cabe ao validador decidir se há nova versão.
    """
    uses_gate = "gate" in inspect.signature(fetcher).parameters

    sources = SOURCES.get(jurisdiction)
    if not sources:
        raise ValueError(f"Não há fontes oficiais configuradas para {jurisdiction}.")

    now = datetime.utcnow()
    candidates: dict[str, tuple[DiscoveredDocument, DiscoverySource]] = {}
    checked_sources: list[str] = []
    skipped_sources: list[dict] = []

    # Um portão por execução: duas fontes do mesmo município compartilham a
    # leitura do robots.txt, e o intervalo de cortesia vale entre elas.
    gate = RobotsGate()

    for source in sources:
        try:
            html = fetcher(source.url, gate=gate) if uses_gate else fetcher(source.url)
        except RobotsDenied as recusa:
            # Fonte recusada não é erro de execução: é resultado, e precisa
            # aparecer no registro do trabalho em vez de sumir em log.
            skipped_sources.append({"url": source.url, "reason": str(recusa)})
            continue
        checked_sources.append(source.url)
        for candidate in source.known_documents:
            candidates[candidate.url] = (candidate, source)
        for candidate in extract_candidates(html, source):
            candidates[candidate.url] = (candidate, source)

    created = 0
    updated = 0
    unchanged = 0
    document_ids: list[str] = []
    for candidate, source in candidates.values():
        existing = (
            db.query(RegulatoryDocument)
            .filter(
                RegulatoryDocument.jurisdiction == jurisdiction,
                RegulatoryDocument.url == candidate.url,
            )
            .order_by(RegulatoryDocument.created_at.desc())
            .first()
        )
        if existing is None:
            existing = RegulatoryDocument(
                jurisdiction=jurisdiction,
                doc_type=candidate.doc_type,
                number=candidate.number,
                title=candidate.title,
                issuing_body=source.issuing_body,
                url=candidate.url,
                theme=candidate.theme,
                state=RegulatoryDocumentState.DESCOBERTO,
                consulted_at=now,
            )
            db.add(existing)
            db.flush()
            created += 1
        else:
            changed = any(
                (
                    existing.title != candidate.title,
                    existing.doc_type != candidate.doc_type,
                    existing.number != candidate.number,
                    existing.theme != candidate.theme,
                    existing.issuing_body != source.issuing_body,
                )
            )
            existing.consulted_at = now
            if changed and existing.state != RegulatoryDocumentState.VALIDADO:
                existing.title = candidate.title
                existing.doc_type = candidate.doc_type
                existing.number = candidate.number
                existing.theme = candidate.theme
                existing.issuing_body = source.issuing_body
                existing.state = RegulatoryDocumentState.DESCOBERTO
                updated += 1
            else:
                unchanged += 1
        document_ids.append(existing.id)

    db.commit()
    return {
        "jurisdiction": jurisdiction,
        "sources_checked": checked_sources,
        "sources_skipped": skipped_sources,
        "candidates_found": len(candidates),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "document_ids": document_ids,
        "requires_human_validation": True,
    }


def discover_applicable_regulations(
    db: Session,
    jurisdiction: str,
    fetcher: Callable[[str], str] = fetch_source,
) -> dict:
    """Descobre normas nacionais, estaduais e municipais aplicáveis ao local."""
    scopes = [scope for scope in jurisdiction_chain(jurisdiction) if scope in SOURCES]
    if not scopes:
        raise ValueError(
            f"Não há fontes oficiais configuradas para {jurisdiction} ou seus pais."
        )

    results = [discover_regulations(db, scope, fetcher=fetcher) for scope in scopes]
    return {
        "jurisdiction": jurisdiction,
        "jurisdictions_checked": scopes,
        "sources_checked": [source for result in results for source in result["sources_checked"]],
        "sources_skipped": [source for result in results for source in result["sources_skipped"]],
        "candidates_found": sum(result["candidates_found"] for result in results),
        "created": sum(result["created"] for result in results),
        "updated": sum(result["updated"] for result in results),
        "unchanged": sum(result["unchanged"] for result in results),
        "document_ids": [item for result in results for item in result["document_ids"]],
        "requires_human_validation": True,
    }
