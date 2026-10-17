#!/usr/bin/env python3
"""The Morning Atlas: reproducible newspaper PDF + Markdown from one JSON manuscript.

Dependencies: reportlab, pymupdf
Usage: python morning_atlas_pdf.py edition.json --out-dir output --verify
"""
import argparse
import html
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A3
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, HRFlowable,
    KeepTogether, CondPageBreak, NextPageTemplate
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

INK = colors.HexColor("#24211d")
MUTED = colors.HexColor("#665f54")
RULE = colors.HexColor("#9c9283")
PAPER = colors.HexColor("#fbf8f0")
PAGE_W, PAGE_H = A3
MARGIN_X = 42
MARGIN_BOTTOM = 44
GUTTER = 23
TOP_SPACE = 116
BODY_TOP = 53

def register_fonts():
    paths = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for regular, bold, sans in paths:
        if all(Path(p).exists() for p in (regular, bold, sans)):
            pdfmetrics.registerFont(TTFont("AtlasSerif", regular))
            pdfmetrics.registerFont(TTFont("AtlasSerifBold", bold))
            pdfmetrics.registerFont(TTFont("AtlasSans", sans))
            pdfmetrics.registerFontFamily("AtlasSerif", normal="AtlasSerif", bold="AtlasSerifBold")
            return
    raise RuntimeError("Install DejaVu or Liberation TTF fonts; see README.")

def safe_url(url):
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise ValueError(f"Invalid external link: {url}")
    return url

def rich(s):
    """Escape user text, allowing only Markdown-style **bold** and *italic*."""
    escaped = html.escape(s, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", escaped)
    return escaped.replace("\n", "<br/>")

def styles():
    return {
        "kicker": ParagraphStyle("kicker", fontName="AtlasSans", fontSize=8.2,
            leading=11, textColor=MUTED, spaceBefore=13, spaceAfter=4),
        "headline": ParagraphStyle("headline", fontName="AtlasSerifBold", fontSize=18,
            leading=21, textColor=INK, spaceAfter=8),
        "deck": ParagraphStyle("deck", fontName="AtlasSerif", fontSize=11.5,
            leading=15, textColor=MUTED, spaceAfter=9),
        "body": ParagraphStyle("body", fontName="AtlasSerif", fontSize=10.2,
            leading=15.1, alignment=TA_JUSTIFY, textColor=INK, spaceAfter=9),
        "subhead": ParagraphStyle("subhead", fontName="AtlasSerifBold", fontSize=11.5,
            leading=15, textColor=INK, spaceBefore=8, spaceAfter=6),
        "source": ParagraphStyle("source", fontName="AtlasSans", fontSize=7.7,
            leading=11, textColor=MUTED, spaceAfter=4, wordWrap="CJK"),
        "toc": ParagraphStyle("toc", fontName="AtlasSerifBold", fontSize=10.5,
            leading=15, spaceAfter=6, textColor=INK),
        "closing": ParagraphStyle("closing", fontName="AtlasSerif", fontSize=10.2,
            leading=15.1, textColor=INK, spaceAfter=9),
    }

class Newspaper(BaseDocTemplate):
    def __init__(self, filename, edition, **kwargs):
        super().__init__(filename, pagesize=A3, leftMargin=MARGIN_X,
            rightMargin=MARGIN_X, topMargin=BODY_TOP,
            bottomMargin=MARGIN_BOTTOM, **kwargs)
        self.edition = edition
        column_w = (PAGE_W - 2*MARGIN_X - GUTTER) / 2
        frames = [
            Frame(MARGIN_X, MARGIN_BOTTOM, column_w,
                  PAGE_H - MARGIN_BOTTOM - TOP_SPACE,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                  id="first_left"),
            Frame(MARGIN_X + column_w + GUTTER, MARGIN_BOTTOM, column_w,
                  PAGE_H - MARGIN_BOTTOM - TOP_SPACE,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                  id="first_right")
        ]
        other_frames = [
            Frame(MARGIN_X, MARGIN_BOTTOM, column_w,
                  PAGE_H - MARGIN_BOTTOM - BODY_TOP,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                  id="left"),
            Frame(MARGIN_X + column_w + GUTTER, MARGIN_BOTTOM, column_w,
                  PAGE_H - MARGIN_BOTTOM - BODY_TOP,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                  id="right")
        ]
        self.addPageTemplates([
            PageTemplate(id="front", frames=frames, onPage=self.front),
            PageTemplate(id="inside", frames=other_frames, onPage=self.inside),
        ])

    def paper(self, canv):
        canv.setFillColor(PAPER)
        canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.5)
        canv.line(MARGIN_X, 32, PAGE_W-MARGIN_X, 32)
        canv.setFillColor(MUTED)
        canv.setFont("AtlasSans", 7.5)
        canv.drawString(MARGIN_X, 20, "THE MORNING ATLAS  /  " + self.edition["date"])
        canv.drawRightString(PAGE_W-MARGIN_X, 20, f"PAGE {self.page}")

    def front(self, canv, doc):
        self.paper(canv)
        canv.setFillColor(INK)
        canv.setFont("AtlasSerifBold", 34)
        canv.drawCentredString(PAGE_W/2, PAGE_H-63, "THE MORNING ATLAS")
        canv.setStrokeColor(INK)
        canv.setLineWidth(2.3)
        canv.line(MARGIN_X, PAGE_H-76, PAGE_W-MARGIN_X, PAGE_H-76)
        canv.setFont("AtlasSans", 9)
        line = f'{self.edition["date"]}  |  {self.edition.get("edition","Daily Edition")}  |  {self.edition.get("tagline","The independent journal of knowledge and discovery")}'
        canv.drawCentredString(PAGE_W/2, PAGE_H-91, line)
        canv.setLineWidth(.6)
        canv.line(MARGIN_X, PAGE_H-102, PAGE_W-MARGIN_X, PAGE_H-102)

    def inside(self, canv, doc):
        self.paper(canv)
        canv.setFont("AtlasSerifBold", 15)
        canv.setFillColor(INK)
        canv.drawString(MARGIN_X, PAGE_H-34, "THE MORNING ATLAS")
        canv.setFont("AtlasSans", 8)
        canv.drawRightString(PAGE_W-MARGIN_X, PAGE_H-32, self.edition["date"])
        canv.setStrokeColor(INK)
        canv.line(MARGIN_X, PAGE_H-41, PAGE_W-MARGIN_X, PAGE_H-41)

def validate(edition):
    if not edition.get("date") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", edition["date"]):
        raise ValueError("date must be YYYY-MM-DD")
    if not edition.get("articles"):
        raise ValueError("At least one article is required")
    for article in edition["articles"]:
        if not article.get("headline") or not article.get("paragraphs"):
            raise ValueError("Each article requires headline and paragraphs")
        for src in article.get("sources", []):
            safe_url(src.get("url"))

def manuscript(edition):
    lines = [
        "# THE MORNING ATLAS",
        f'**{edition["date"]} | {edition.get("edition", "Daily Edition")}**',
        f'*{edition.get("tagline", "The independent journal of knowledge and discovery")}*',
        "",
    ]
    for a in edition["articles"]:
        if a.get("section"):
            lines.extend([f'## {a["section"]}', ""])
        lines.extend([f'### {a["headline"]}', ""])
        if a.get("deck"):
            lines.extend([f'*{a["deck"]}*', ""])
        for p in a["paragraphs"]:
            lines.extend([p, ""])
        if a.get("sources"):
            lines.append("Sources:")
            for s in a["sources"]:
                lines.append(f'- [{s["label"]}]({s["url"]})')
            lines.append("")
    if edition.get("closing_note"):
        lines.extend(["## THE EDITOR'S CLOSING NOTE", "", edition["closing_note"], ""])
    return "\n".join(lines)

def build_pdf(edition, output):
    register_fonts()
    ss = styles()
    doc = Newspaper(str(output), edition, title=f'The Morning Atlas - {edition["date"]}',
                    author="The Morning Atlas")
    story = [NextPageTemplate("inside")]
    for i, a in enumerate(edition["articles"]):
        if i:
            story.append(Spacer(1, 9))
            story.append(HRFlowable(width="100%", thickness=.6, color=RULE,
                                    spaceBefore=3, spaceAfter=7))
        if a.get("section"):
            story.append(CondPageBreak(95))
            story.append(Paragraph(rich(a["section"].upper()), ss["kicker"]))
        story.append(CondPageBreak(78))
        story.append(Paragraph(rich(a["headline"]), ss["headline"]))
        if a.get("deck"):
            story.append(Paragraph(rich(a["deck"]), ss["deck"]))
        for paragraph in a["paragraphs"]:
            story.append(Paragraph(rich(paragraph), ss["body"]))
        if a.get("sources"):
            story.append(Paragraph("SOURCES", ss["kicker"]))
            for source in a["sources"]:
                url = safe_url(source["url"])
                escaped = html.escape(url, quote=True)
                label = html.escape(source["label"])
                story.append(Paragraph(
                    f'<link href="{escaped}" color="#4b453e">{label}</link>  '
                    f'<link href="{escaped}" color="#4b453e">{escaped}</link>',
                    ss["source"]))
    if edition.get("closing_note"):
        story.append(HRFlowable(width="100%", thickness=1.1, color=INK,
                                spaceBefore=12, spaceAfter=9))
        story.append(Paragraph("THE EDITOR'S CLOSING NOTE", ss["kicker"]))
        story.append(Paragraph(rich(edition["closing_note"]), ss["closing"]))
    doc.build(story)

def normalize(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().casefold()

def verify_pdf(pdf_path, edition):
    import fitz
    document = fitz.open(str(pdf_path))
    text = "\n".join(page.get_text(sort=False) for page in document)
    # Layout extraction can reorder columns; check each article independently.
    missing = []
    for article in edition["articles"]:
        for field in ["headline", "deck"]:
            if article.get(field) and normalize(article[field]) not in normalize(text):
                missing.append(f'{article["headline"]}: {field}')
        for index, paragraph in enumerate(article["paragraphs"], 1):
            plain = re.sub(r"\*\*|\*", "", paragraph)
            # ReportLab inserts line wraps and may split words in narrow columns.
            words = normalize(plain).split()
            pdf_words = normalize(text).split()
            needle = " ".join(words[:min(8,len(words))])
            if needle not in " ".join(pdf_words):
                missing.append(f'{article["headline"]}: paragraph {index}')
        for source in article.get("sources", []):
            if source["url"] not in text.replace("\n", ""):
                # PDF can wrap long URLs. Annotation check below provides stronger test.
                annotations = [
                    link.get("uri", "") for page in document for link in page.get_links()
                ]
                if source["url"] not in annotations:
                    missing.append(f'{article["headline"]}: source {source["url"]}')
    if edition.get("closing_note"):
        if normalize(edition["closing_note"]) not in normalize(text):
            words = normalize(edition["closing_note"]).split()
            if " ".join(words[:min(8,len(words))]) not in normalize(text):
                missing.append("closing note")
    if missing:
        raise RuntimeError("PDF parity check failed:\n - " + "\n - ".join(missing))
    return len(document)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("output"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    edition = json.loads(args.manuscript.read_text(encoding="utf-8"))
    validate(edition)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f'Morning_Atlas_{edition["date"]}'
    md_path = args.out_dir / f"{stem}.md"
    pdf_path = args.out_dir / f"{stem}.pdf"
    md_path.write_text(manuscript(edition), encoding="utf-8")
    build_pdf(edition, pdf_path)
    if args.verify:
        pages = verify_pdf(pdf_path, edition)
        print(f"Verified {pages} PDF pages")
    print(f"Markdown: {md_path}")
    print(f"PDF:      {pdf_path}")

if __name__ == "__main__":
    main()
