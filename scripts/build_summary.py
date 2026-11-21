#!/usr/bin/env python3
"""Rebuild the one-page technical summary. Optional dev dependency: ReportLab."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'docs/TECHNICAL_SUMMARY.md').read_text(encoding='utf-8')
parts = text.strip().split('\n\n')
output = ROOT / 'docs/TECHNICAL_SUMMARY.pdf'
navy = colors.HexColor('#173044'); green = colors.HexColor('#28735f')
styles = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=navy, spaceAfter=6),
    'subtitle': ParagraphStyle('subtitle', fontName='Helvetica', fontSize=8, leading=11, textColor=green, spaceAfter=13),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10.5, leading=14.5, textColor=colors.HexColor('#233746'), spaceAfter=9.5, alignment=TA_LEFT),
}
def inline(value): return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escape(value))
story = [Paragraph(escape(parts[0].removeprefix('# ')), styles['title']), Paragraph(escape(parts[1]), styles['subtitle']), HRFlowable(width='100%', thickness=.8, color=green), Spacer(1,12)]
story += [Paragraph(inline(p), styles['body']) for p in parts[2:]]
def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#d4dedf')); canvas.line(43, 35, A4[0]-43, 35)
    canvas.setFont('Helvetica',7); canvas.setFillColor(colors.HexColor('#60757c'))
    canvas.drawString(43,24,'SAHIL ATLAS / CHALLENGE 01 / PRIVATE SUBMISSION')
    canvas.drawRightString(A4[0]-43,24,str(doc.page))
doc = SimpleDocTemplate(str(output),pagesize=A4,rightMargin=43,leftMargin=43,topMargin=35,bottomMargin=45,
                        title='Sahil Atlas - Technical Summary',author='Challenge 01 submission')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(output)
