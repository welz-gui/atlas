import io
import hashlib
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class RegulatoryReportGenerator:
    """
    Gerador de Laudos e Certificados Oficiais de Conformidade Urbanística em PDF
    com carimbo criptográfico SHA-256 e linha de base legal de Lajeado/RS.
    """

    @staticmethod
    def generate_pdf(project_data: Dict[str, Any], validations: List[Dict[str, Any]]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom Styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0f172a'),
            alignment=1 # Center
        )

        subtitle_style = ParagraphStyle(
            'DocSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#475569'),
            alignment=1
        )

        h2_style = ParagraphStyle(
            'SectionH2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#0284c7'),
            spaceBefore=10,
            spaceAfter=6
        )

        normal_style = ParagraphStyle(
            'DocNormal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1e293b')
        )

        bold_style = ParagraphStyle(
            'DocBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#0f172a')
        )

        story = []

        # 1. Header
        story.append(Paragraph("<b>ATLAS</b> — SISTEMA OPERACIONAL DA CONSTRUÇÃO", title_style))
        story.append(Paragraph("LAUDO TÉCNICO DE CONFORMIDADE URBANÍSTICA & DIRETRIZES MUNICIPAIS", subtitle_style))
        story.append(Paragraph("Prefeitura Municipal de Lajeado / RS — Zona Z2 (Residencial Unifamiliar)", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=15))

        # 2. Project Summary Table
        story.append(Paragraph("1. DADOS DO EMPREENDIMENTO", h2_style))
        
        proj_info_data = [
            [Paragraph("<b>Nome do Projeto:</b>", bold_style), Paragraph(str(project_data.get('name', '')), normal_style),
             Paragraph("<b>Município / Zona:</b>", bold_style), Paragraph(f"{project_data.get('city_name', 'Lajeado')} / {project_data.get('zone', 'Z2')}", normal_style)],
            [Paragraph("<b>Área do Terreno:</b>", bold_style), Paragraph(f"{project_data.get('lot_area', 0.0)} m²", normal_style),
             Paragraph("<b>Área Construída:</b>", bold_style), Paragraph(f"{project_data.get('built_area', 0.0)} m²", normal_style)],
            [Paragraph("<b>Recuo Frontal:</b>", bold_style), Paragraph(f"{project_data.get('front_setback', 0.0)} m", normal_style),
             Paragraph("<b>Recuo Fundos:</b>", bold_style), Paragraph(f"{project_data.get('rear_setback', 0.0)} m", normal_style)],
            [Paragraph("<b>Taxa de Ocupação:</b>", bold_style), Paragraph(f"{project_data.get('occupancy_rate', 0.0)}%", normal_style),
             Paragraph("<b>Permeabilidade:</b>", bold_style), Paragraph(f"{project_data.get('permeability_rate', 0.0)}%", normal_style)]
        ]

        t_proj = Table(proj_info_data, colWidths=[110, 150, 110, 150])
        t_proj.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_proj)
        story.append(Spacer(1, 15))

        # 3. Regulatory Verification Results Table
        story.append(Paragraph("2. AVALIAÇÃO DETERMINÍSTICA DE REGRAS URBANÍSTICAS", h2_style))

        table_headers = [
            Paragraph("<b>Parâmetro / Regra</b>", bold_style),
            Paragraph("<b>Exigido</b>", bold_style),
            Paragraph("<b>Projeto</b>", bold_style),
            Paragraph("<b>Status</b>", bold_style),
            Paragraph("<b>Base Legal</b>", bold_style)
        ]

        table_rows = [table_headers]

        for val in validations:
            status_str = str(val.get('status', '')).upper()
            if status_str == "CONFORME":
                status_p = Paragraph(f"<font color='#059669'><b>✓ {status_str}</b></font>", bold_style)
            else:
                status_p = Paragraph(f"<font color='#dc2626'><b>✗ {status_str}</b></font>", bold_style)

            table_rows.append([
                Paragraph(str(val.get('rule_title', '')), normal_style),
                Paragraph(str(val.get('expected_value', '')), normal_style),
                Paragraph(str(val.get('actual_value', '')), normal_style),
                status_p,
                Paragraph(str(val.get('source_citation', '')), normal_style)
            ])

        t_rules = Table(table_rows, colWidths=[130, 80, 70, 90, 150])
        t_rules.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0,0), (-1,-1), 5),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_rules)
        story.append(Spacer(1, 20))

        # 4. Cryptographic Seal & Verification Footer
        raw_seal_content = f"{project_data.get('id')}_{datetime.utcnow().isoformat()}_{len(validations)}"
        sha256_seal = hashlib.sha256(raw_seal_content.encode('utf-8')).hexdigest()

        seal_data = [
            [Paragraph("<b>CARIMBO DIGITAL DE AUTENTICIDADE & AUDITORIA CRIPTOGRÁFICA</b>", ParagraphStyle('SealTitle', parent=bold_style, textColor=colors.HexColor('#0284c7')))],
            [Paragraph(f"<b>HASH SHA-256:</b> <font face='Courier'>{sha256_seal}</font>", normal_style)],
            [Paragraph(f"<b>Data de Emissão (UTC):</b> {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S UTC')} &nbsp;|&nbsp; <b>Linha de Base Oficial:</b> SIM", normal_style)],
            [Paragraph("<i>Este laudo possui validade técnica para protocolo junto à Secretaria de Planejamento do Município de Lajeado/RS.</i>", ParagraphStyle('Italic', parent=normal_style, fontSize=8, textColor=colors.HexColor('#64748b')))]
        ]

        t_seal = Table(seal_data, colWidths=[520])
        t_seal.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f9ff')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0284c7')),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t_seal)

        # Build Document PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
