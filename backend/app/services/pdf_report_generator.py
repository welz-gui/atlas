"""Geração do laudo de pré-análise urbanística.

O laudo é um **documento técnico de apoio**. Ele não atesta aprovação, não
substitui o responsável técnico e não afirma validade perante nenhum órgão
público — as ressalvas do §12 do Plano de Implementação são impressas em todo
laudo, sem exceção.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Rótulo e cor por estado da verificação (§7.7).
STATUS_PRESENTATION = {
    "conforme": ("CONFORME", "#059669"),
    "nao_conforme": ("NAO CONFORME", "#dc2626"),
    "atencao": ("ATENCAO", "#b45309"),
    "nao_aplicavel": ("NAO APLICAVEL", "#64748b"),
    "nao_verificavel": ("NAO VERIFICAVEL", "#1d4ed8"),
}

DISCLAIMERS = [
    "Este documento é uma <b>pré-análise técnica de apoio</b>. Não constitui aprovação, "
    "licença, alvará ou manifestação de qualquer órgão público, e não possui validade "
    "perante a Administração Municipal.",
    "Este documento <b>não substitui o responsável técnico</b> pelo projeto. A "
    "responsabilidade técnica pela concepção, pelo dimensionamento e pela conformidade "
    "legal do empreendimento permanece integralmente com o profissional habilitado.",
    "As verificações refletem exclusivamente os parâmetros informados no cadastro do "
    "empreendimento e as regras cadastradas no catálogo regulatório do Atlas. Parâmetros "
    "incorretos ou desatualizados produzem resultados incorretos.",
    "Itens marcados como <b>NÃO VERIFICÁVEL</b> não foram analisados e não devem ser "
    "interpretados como conformes.",
    "A responsabilidade do Atlas limita-se à execução das regras cadastradas sobre os "
    "dados fornecidos, não alcançando decisões de projeto, de protocolo ou de execução "
    "tomadas com base neste documento.",
]


class RegulatoryReportGenerator:
    """Renderiza o laudo de uma análise já persistida."""

    # -- estilos -----------------------------------------------------------
    @staticmethod
    def _styles() -> Dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "DocTitle", parent=base["Heading1"], fontName="Helvetica-Bold",
                fontSize=16, leading=20, textColor=colors.HexColor("#0f172a"), alignment=1,
            ),
            "subtitle": ParagraphStyle(
                "DocSubTitle", parent=base["Normal"], fontName="Helvetica",
                fontSize=9.5, leading=13, textColor=colors.HexColor("#475569"), alignment=1,
            ),
            "h2": ParagraphStyle(
                "SectionH2", parent=base["Heading2"], fontName="Helvetica-Bold",
                fontSize=11, leading=15, textColor=colors.HexColor("#0284c7"),
                spaceBefore=10, spaceAfter=6,
            ),
            "normal": ParagraphStyle(
                "DocNormal", parent=base["Normal"], fontName="Helvetica",
                fontSize=8.5, leading=11.5, textColor=colors.HexColor("#1e293b"),
            ),
            "bold": ParagraphStyle(
                "DocBold", parent=base["Normal"], fontName="Helvetica-Bold",
                fontSize=8.5, leading=11.5, textColor=colors.HexColor("#0f172a"),
            ),
            "small": ParagraphStyle(
                "DocSmall", parent=base["Normal"], fontName="Helvetica",
                fontSize=7.5, leading=10, textColor=colors.HexColor("#475569"),
            ),
        }

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _fmt(value: Any, unit: str = "", decimals: int = 2) -> str:
        """Formata um parâmetro. Ausência é dita, nunca preenchida com zero."""
        if value is None:
            return "não informado"
        if isinstance(value, float):
            sep = "" if unit == "%" else " "
            return f"{value:.{decimals}f}{sep}{unit}".strip()
        return f"{value} {unit}".strip()

    @classmethod
    def _warning_banner(cls, text: str, styles, accent: str, background: str) -> Table:
        table = Table([[Paragraph(text, styles["normal"])]], colWidths=[523])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
            ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor(accent)),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    # -- documento ---------------------------------------------------------
    @classmethod
    def generate_pdf(
        cls,
        project_data: Dict[str, Any],
        validations: List[Dict[str, Any]],
        run_data: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        run_data = run_data or {}
        styles = cls._styles()
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36,
            title=f"Pré-análise urbanística — {project_data.get('name', '')}",
            author="Atlas",
        )

        story: List[Any] = []

        # 1. Cabeçalho
        story.append(Paragraph("<b>ATLAS</b> — PRÉ-ANÁLISE URBANÍSTICA", styles["title"]))
        story.append(Paragraph(
            "Documento técnico de apoio — não constitui aprovação nem licença",
            styles["subtitle"],
        ))
        municipality = project_data.get("city_name", "—")
        story.append(Paragraph(
            f"Jurisdição de referência: {municipality} / {project_data.get('state', '—')} "
            f"— Zona {project_data.get('zone', '—')}",
            styles["subtitle"],
        ))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5,
                                color=colors.HexColor("#0284c7"), spaceAfter=12))

        # 2. Tarja de não publicável (§7.5)
        if not run_data.get("is_publishable", False):
            story.append(cls._warning_banner(
                "<b>USO INTERNO — NÃO ENTREGÁVEL AO CLIENTE.</b> Este laudo aplica regras "
                "que ainda não passaram por validação técnica humana. Enquanto o catálogo "
                "regulatório não for conferido contra o texto legal publicado pelo "
                "município, os resultados abaixo servem apenas para conferência interna.",
                styles, "#b45309", "#fffbeb",
            ))
            story.append(Spacer(1, 12))

        # 3. Dados do empreendimento
        story.append(Paragraph("1. DADOS DO EMPREENDIMENTO", styles["h2"]))
        rows = [
            ("Nome do Projeto", str(project_data.get("name", "—")),
             "Município / Zona", f"{municipality} / {project_data.get('zone', '—')}"),
            ("Área do Terreno", cls._fmt(project_data.get("lot_area"), "m²"),
             "Área Construída", cls._fmt(project_data.get("built_area"), "m²")),
            ("Recuo Frontal", cls._fmt(project_data.get("front_setback"), "m"),
             "Recuo Fundos", cls._fmt(project_data.get("rear_setback"), "m")),
            ("Taxa de Ocupação (derivada)", cls._fmt(project_data.get("occupancy_rate"), "%", 1),
             "Permeabilidade", cls._fmt(project_data.get("permeability_rate"), "%", 1)),
            ("Pavimentos", cls._fmt(project_data.get("floors")),
             "Linha de Base Oficial", "SIM" if project_data.get("is_official_baseline") else "NÃO"),
        ]
        proj_table = Table(
            [[Paragraph(f"<b>{a}:</b>", styles["bold"]), Paragraph(b, styles["normal"]),
              Paragraph(f"<b>{c}:</b>", styles["bold"]), Paragraph(d, styles["normal"])]
             for a, b, c, d in rows],
            colWidths=[125, 135, 125, 138],
        )
        proj_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(proj_table)
        story.append(Spacer(1, 14))

        # 4. Resultado das verificações
        story.append(Paragraph("2. VERIFICAÇÃO DETERMINÍSTICA DE REGRAS", styles["h2"]))

        header = [Paragraph(f"<b>{h}</b>", styles["bold"])
                  for h in ("Parâmetro / Regra", "Exigido", "Apurado", "Status", "Base legal")]
        table_rows = [header]
        status_row_styles = []

        for index, item in enumerate(validations, start=1):
            status = str(item.get("status", ""))
            label, color = STATUS_PRESENTATION.get(status, (status.upper(), "#334155"))

            citation = str(item.get("source_citation") or "—")
            if not item.get("source_is_verified", False):
                citation += " <font color='#b45309'>[não conferida]</font>"

            table_rows.append([
                Paragraph(str(item.get("rule_title", "")), styles["normal"]),
                Paragraph(str(item.get("expected_value", "")), styles["normal"]),
                Paragraph(str(item.get("actual_value", "")), styles["normal"]),
                Paragraph(f"<font color='{color}'><b>{label}</b></font>", styles["bold"]),
                Paragraph(citation, styles["small"]),
            ])
            if status == "nao_verificavel":
                status_row_styles.append(
                    ("BACKGROUND", (0, index), (-1, index), colors.HexColor("#eff6ff"))
                )

        rules_table = Table(table_rows, colWidths=[150, 72, 78, 85, 138], repeatRows=1)
        rules_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            *status_row_styles,
        ]))
        story.append(rules_table)
        story.append(Spacer(1, 14))

        # 5. Não verificáveis em destaque (§7.7)
        unverifiable = [v for v in validations if v.get("status") == "nao_verificavel"]
        story.append(Paragraph("3. ITENS NÃO VERIFICÁVEIS", styles["h2"]))
        if unverifiable:
            story.append(cls._warning_banner(
                f"<b>{len(unverifiable)} item(ns) não puderam ser verificados.</b> "
                "Ausência de verificação não é conformidade: estes pontos permanecem em "
                "aberto e exigem análise do responsável técnico.",
                styles, "#1d4ed8", "#eff6ff",
            ))
            story.append(Spacer(1, 8))
            unverifiable_rows = [[
                Paragraph("<b>Item</b>", styles["bold"]),
                Paragraph("<b>Motivo</b>", styles["bold"]),
                Paragraph("<b>Evidência necessária</b>", styles["bold"]),
            ]]
            for item in unverifiable:
                unverifiable_rows.append([
                    Paragraph(str(item.get("rule_title", "")), styles["normal"]),
                    Paragraph(str(item.get("details", "")), styles["normal"]),
                    Paragraph(str(item.get("evidence_required") or "—"), styles["normal"]),
                ])
            unverifiable_table = Table(unverifiable_rows, colWidths=[150, 233, 140])
            unverifiable_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#93c5fd")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(unverifiable_table)
        else:
            story.append(Paragraph(
                "Nenhum item ficou sem verificação nesta análise.", styles["normal"]))
        story.append(Spacer(1, 14))

        # 6. Ressalvas obrigatórias (§12)
        story.append(Paragraph("4. RESSALVAS E LIMITAÇÕES", styles["h2"]))
        for index, text in enumerate(DISCLAIMERS, start=1):
            story.append(Paragraph(f"{index}. {text}", styles["normal"]))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

        # 7. Proveniência
        story.append(Paragraph("5. PROVENIÊNCIA DA ANÁLISE", styles["h2"]))
        verified = sum(1 for v in validations if v.get("source_is_verified"))
        emitted_at = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
        provenance = [
            ("Identificador da análise", str(run_data.get("id", "—"))),
            ("Hash SHA-256 do conteúdo analisado", str(run_data.get("content_hash", "—"))),
            ("Versão do catálogo regulatório", str(run_data.get("catalog_version", "—"))),
            ("Versão do motor de regras", str(run_data.get("engine_version", "—"))),
            ("Regras aplicadas", str(len(validations))),
            ("Regras com fonte legal conferida", f"{verified} de {len(validations)}"),
            ("Validação técnica humana", "PENDENTE" if not run_data.get("is_publishable") else "CONCLUÍDA"),
            ("Emitido em", emitted_at),
        ]
        provenance_table = Table(
            [[Paragraph(f"<b>{k}</b>", styles["small"]),
              Paragraph(f"<font face='Courier'>{v}</font>", styles["small"])]
             for k, v in provenance],
            colWidths=[200, 323],
        )
        provenance_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f9ff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0284c7")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bae6fd")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(provenance_table)
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "O hash acima cobre os parâmetros avaliados, as regras aplicadas e os "
            "resultados obtidos, permitindo verificar posteriormente se a análise foi "
            "alterada.",
            styles["small"],
        ))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
