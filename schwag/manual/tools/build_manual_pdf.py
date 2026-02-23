#!/usr/bin/env python3
"""Build a simple PDF booklet from markdown content using ReportLab."""

from __future__ import annotations

import textwrap
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD = ROOT / "usermanual-booklet.md"
OUTPUT_PDF = ROOT / "Super_Dragons_Lair_Manual.pdf"


TITLE_FONT = "Helvetica-Bold"
BODY_FONT = "Helvetica"
TITLE_SIZE = 22
H1_SIZE = 16
H2_SIZE = 13
BODY_SIZE = 11
LINE_GAP = 15
MARGIN_X = 54
MARGIN_Y = 54


def draw_wrapped_lines(pdf: canvas.Canvas, y: float, text: str, width_chars: int = 92) -> float:
    wrapped = textwrap.wrap(text, width=width_chars) or [""]
    for line in wrapped:
        pdf.drawString(MARGIN_X, y, line)
        y -= LINE_GAP
    return y


def add_page_number(pdf: canvas.Canvas, page_num: int) -> None:
    page_width, _ = LETTER
    pdf.setFont(BODY_FONT, 9)
    pdf.drawRightString(page_width - MARGIN_X, MARGIN_Y / 2, f"Page {page_num}")


def build_pdf() -> None:
    if not SOURCE_MD.exists():
        raise FileNotFoundError(f"Missing source markdown: {SOURCE_MD}")

    lines = SOURCE_MD.read_text(encoding="utf-8").splitlines()

    pdf = canvas.Canvas(str(OUTPUT_PDF), pagesize=LETTER)
    page_width, page_height = LETTER
    y = page_height - MARGIN_Y
    page_num = 1

    for raw in lines:
        line = raw.rstrip()

        if y < MARGIN_Y + 2 * LINE_GAP:
            add_page_number(pdf, page_num)
            pdf.showPage()
            page_num += 1
            y = page_height - MARGIN_Y

        if not line.strip():
            y -= LINE_GAP / 2
            continue

        if line.startswith("# "):
            pdf.setFont(TITLE_FONT, TITLE_SIZE)
            y = draw_wrapped_lines(pdf, y, line[2:].strip(), width_chars=58)
            y -= LINE_GAP / 2
            continue

        if line.startswith("## "):
            pdf.setFont(TITLE_FONT, H1_SIZE)
            y = draw_wrapped_lines(pdf, y, line[3:].strip(), width_chars=74)
            y -= LINE_GAP / 3
            continue

        if line.startswith("### "):
            pdf.setFont(TITLE_FONT, H2_SIZE)
            y = draw_wrapped_lines(pdf, y, line[4:].strip(), width_chars=82)
            continue

        if line.startswith("- "):
            pdf.setFont(BODY_FONT, BODY_SIZE)
            y = draw_wrapped_lines(pdf, y, f"• {line[2:].strip()}")
            continue

        pdf.setFont(BODY_FONT, BODY_SIZE)
        y = draw_wrapped_lines(pdf, y, line)

    add_page_number(pdf, page_num)
    pdf.save()

    print(f"Built PDF: {OUTPUT_PDF}")


if __name__ == "__main__":
    build_pdf()
