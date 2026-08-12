"""Extração assistida de parâmetros urbanísticos (§3.6).

Regra inegociável deste módulo: **nunca inventar um número**. Quando o texto
não traz um parâmetro, o campo volta `None` e o resultado é marcado como
`nao_verificavel`. Um valor plausível é pior do que nenhum valor, porque entra
no laudo com a mesma aparência de um dado medido.
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Any, Dict, List, Tuple

#: Campos que o extrator tenta localizar no quadro de áreas.
EXPECTED_FIELDS = (
    "lot_area",
    "built_area",
    "front_setback",
    "rear_setback",
    "permeability_rate",
    "floors",
)

# Padrões do quadro de áreas / memorial descritivo.
#
# Os padrões são escritos **sem acento**: a busca ocorre sobre uma versão do
# texto com os diacríticos removidos, porque pranchas reais chegam com acentuação
# inconsistente (fontes sem mapeamento, OCR, exportações de CAD). A remoção
# preserva o comprimento do texto, de modo que a evidência citada ao usuário
# continua sendo o trecho original, acentuado.
_NUMBER = r"([\d.,]+)"

FLOAT_PATTERNS: Tuple[Tuple[str, str, str], ...] = (
    (
        "lot_area",
        rf"(?:area\s+do\s+terreno|area\s+do\s+lote|area\s+total\s+do\s+lote)\s*[:=]?\s*{_NUMBER}\s*m[²2]",
        "m²",
    ),
    (
        "built_area",
        rf"(?:area\s+total\s+construida|area\s+construida|area\s+de\s+projecao)\s*[:=]?\s*{_NUMBER}\s*m[²2]",
        "m²",
    ),
    (
        "front_setback",
        rf"(?:recuo\s+frontal|afastamento\s+frontal)\s*[:=]?\s*{_NUMBER}\s*m\b",
        "m",
    ),
    (
        "rear_setback",
        rf"(?:recuo\s+dos\s+fundos|recuo\s+fundos|afastamento\s+posterior)\s*[:=]?\s*{_NUMBER}\s*m\b",
        "m",
    ),
    (
        "permeability_rate",
        rf"(?:taxa\s+de\s+permeabilidade|area\s+permeavel)\s*[:=]?\s*{_NUMBER}\s*%",
        "%",
    ),
)

INT_PATTERNS: Tuple[Tuple[str, str, str], ...] = (
    (
        "floors",
        r"(?:n[ºo°]?\s*(?:de\s+)?pavimentos|pavimentos)\s*[:=]?\s*(\d+)",
        "pavimentos",
    ),
)

FIELD_LABELS = {
    "lot_area": "Área do Lote",
    "built_area": "Área Construída",
    "front_setback": "Recuo Frontal",
    "rear_setback": "Recuo dos Fundos",
    "permeability_rate": "Taxa de Permeabilidade",
    "floors": "Nº de Pavimentos",
}


def fold_accents(text: str) -> str:
    """Remove diacríticos preservando o comprimento do texto.

    Cada caractere é decomposto e reduzido à sua letra base, de modo que os
    índices do resultado continuem apontando para as mesmas posições do texto
    original — é isso que permite casar sobre o texto normalizado e recortar a
    evidência do texto original.
    """
    return "".join(unicodedata.normalize("NFD", char)[0] for char in text)


def parse_number(raw: str) -> float | None:
    """Converte um número escrito em formato brasileiro ou inglês.

    ``1.234,56`` → 1234.56 · ``450,00`` → 450.0 · ``450.00`` → 450.0 ·
    ``1,234.56`` → 1234.56 · ``1.234`` → 1234.0 (milhar)
    """
    text = raw.strip()
    if not text or not any(ch.isdigit() for ch in text):
        return None

    has_dot, has_comma = "." in text, "," in text

    if has_dot and has_comma:
        # O separador decimal é o que aparece por último.
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_comma:
        text = text.replace(",", ".") if text.count(",") == 1 else text.replace(",", "")
    elif has_dot:
        # Ponto único seguido de exatamente 3 dígitos e precedido de dígitos
        # é separador de milhar ("1.234"); caso contrário, é decimal.
        if text.count(".") > 1:
            text = text.replace(".", "")
        else:
            integer_part, _, fraction = text.partition(".")
            if len(fraction) == 3 and integer_part.isdigit():
                text = integer_part + fraction

    try:
        return float(text)
    except ValueError:
        return None


class PDFPlanParser:
    """Extrator assistido para quadros de áreas e memoriais descritivos."""

    @staticmethod
    def parse_text_content(text: str) -> Dict[str, Any]:
        extracted: Dict[str, Any] = {name: None for name in EXPECTED_FIELDS}
        evidence: List[str] = []
        warnings: List[str] = []

        if not text or not text.strip():
            extracted.update(
                status="nao_verificavel",
                fields_found=0,
                fields_expected=len(EXPECTED_FIELDS),
                confidence_score=0.0,
                evidence=[],
                warnings=[
                    "Nenhum texto extraível no documento. Pode ser um PDF digitalizado "
                    "(imagem), que exige OCR — ainda não disponível."
                ],
                raw_matches=[],
            )
            return extracted

        # Busca sobre o texto sem acentos; evidência recortada do original.
        haystack = fold_accents(text)

        def snippet(match: "re.Match[str]") -> str:
            return text[match.start():match.end()].strip()

        for name, pattern, unit in FLOAT_PATTERNS:
            match = re.search(pattern, haystack, re.IGNORECASE)
            if not match:
                continue
            value = parse_number(match.group(1))
            if value is None:
                warnings.append(
                    f"{FIELD_LABELS[name]}: valor '{match.group(1)}' não pôde ser interpretado."
                )
                continue
            extracted[name] = value
            evidence.append(
                f'{FIELD_LABELS[name]}: {value:g} {unit} — trecho: "{snippet(match)}"'
            )

        for name, pattern, unit in INT_PATTERNS:
            match = re.search(pattern, haystack, re.IGNORECASE)
            if not match:
                continue
            try:
                value = int(match.group(1))
            except ValueError:
                warnings.append(
                    f"{FIELD_LABELS[name]}: valor '{match.group(1)}' não pôde ser interpretado."
                )
                continue
            extracted[name] = value
            evidence.append(
                f'{FIELD_LABELS[name]}: {value} {unit} — trecho: "{snippet(match)}"'
            )

        found = sum(1 for name in EXPECTED_FIELDS if extracted[name] is not None)
        missing = [FIELD_LABELS[n] for n in EXPECTED_FIELDS if extracted[n] is None]
        if missing:
            warnings.append(
                "Não localizados no documento (permanecem não verificáveis): "
                + ", ".join(missing)
            )

        if found == 0:
            status = "nao_verificavel"
        elif found < len(EXPECTED_FIELDS):
            status = "extraido_parcial"
        else:
            status = "extraido"

        extracted.update(
            status=status,
            fields_found=found,
            fields_expected=len(EXPECTED_FIELDS),
            # Proporção de campos localizados. Não é probabilidade de acerto:
            # mede cobertura da extração, não confiança na leitura.
            confidence_score=round(found / len(EXPECTED_FIELDS) * 100, 1),
            evidence=evidence,
            warnings=warnings,
            raw_matches=evidence,
        )
        return extracted

    @staticmethod
    def extract_text(file_bytes: bytes, filename: str = "") -> Tuple[str, List[str]]:
        """Obtém o texto do arquivo. Devolve ``(texto, avisos)``."""
        warnings: List[str] = []
        if not file_bytes:
            return "", ["Arquivo vazio."]

        if file_bytes[:5] == b"%PDF-":
            # A importação é protegida de forma ampla de propósito: uma
            # dependência nativa quebrada pode falhar com algo que não é
            # ImportError. Em qualquer cenário, o resultado é "não extraí",
            # nunca um valor inventado.
            try:
                import pypdf
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as exc:
                return "", [
                    "Biblioteca de leitura de PDF indisponível no servidor "
                    f"(pypdf): {type(exc).__name__}. Extração não executada."
                ]
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                text = "".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:  # PDF corrompido, cifrado etc.
                return "", [f"Falha ao ler o PDF: {exc}"]

            if not text.strip():
                warnings.append(
                    "O PDF não contém camada de texto — provavelmente digitalizado. "
                    "Extração automática exige OCR."
                )
            return text, warnings

        # Demais formatos: tentativa de leitura como texto simples.
        try:
            return file_bytes.decode("utf-8"), warnings
        except UnicodeDecodeError:
            return "", [
                f"Formato de '{filename or 'arquivo'}' não suportado pela extração "
                "automática. Formatos suportados: PDF com camada de texto e texto simples."
            ]

    @classmethod
    def parse_file(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        text, warnings = cls.extract_text(file_bytes, filename)
        result = cls.parse_text_content(text)
        if warnings:
            result["warnings"] = warnings + list(result.get("warnings") or [])
        return result
