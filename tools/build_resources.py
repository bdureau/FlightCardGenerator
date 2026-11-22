"""Génère les ressources : manuels PDF (4 langues) et icône de l'application.

Usage : python tools/build_resources.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtCore import QMarginsF, QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import (QColor, QImage, QPageLayout, QPageSize, QPainter,  # noqa: E402
                         QPainterPath, QPdfWriter, QTextDocument)
from PyQt6.QtWidgets import QApplication  # noqa: E402

from flightcard.i18n import Translator  # noqa: E402
from manual_content import MANUALS, SHORTCUTS  # noqa: E402

CSS = """
body { font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif; font-size: 10.5pt; color: #222; }
h1 { color: #1b2a8f; font-size: 20pt; border-bottom: 2px solid #1b2a8f; }
h2 { color: #1b2a8f; font-size: 13.5pt; margin-top: 16px; }
code { font-family: 'DejaVu Sans Mono', Consolas, monospace; background: #eef; }
td { padding: 3px 10px; border-bottom: 1px solid #ccd; }
"""


def build_manuals(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for lang, html in MANUALS.items():
        tr = Translator(lang)
        rows = "".join(f"<tr><td><b>{k}</b></td><td>{tr(a).replace('&', '')}</td></tr>"
                       for k, a in SHORTCUTS)
        body = html.replace("{shortcuts}", f"<table>{rows}</table>")
        path = out_dir / f"manual_{lang}.pdf"
        writer = QPdfWriter(str(path))
        writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                         QPageLayout.Orientation.Portrait,
                                         QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter))
        writer.setResolution(300)
        writer.setTitle(f"FlightCard Generator — manual ({lang})")
        writer.setCreator("FlightCard Generator")
        doc = QTextDocument()
        doc.setDefaultStyleSheet(CSS)
        doc.setHtml(f"<html><body>{body}</body></html>")
        doc.print(writer)
        print("écrit", path)


def build_icon(path: Path, size: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#1b2a8f"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(8, 8, size - 16, size - 16), 44, 44)
    p.translate(size / 2, size / 2)
    p.rotate(35)
    s = size / 256
    body = QPainterPath()
    body.moveTo(0, -95 * s)
    body.cubicTo(28 * s, -60 * s, 26 * s, 10 * s, 22 * s, 55 * s)
    body.lineTo(-22 * s, 55 * s)
    body.cubicTo(-26 * s, 10 * s, -28 * s, -60 * s, 0, -95 * s)
    p.setBrush(QColor("white"))
    p.drawPath(body)
    for sign in (-1, 1):
        fin = QPainterPath()
        fin.moveTo(sign * 22 * s, 15 * s)
        fin.lineTo(sign * 50 * s, 70 * s)
        fin.lineTo(sign * 22 * s, 55 * s)
        fin.closeSubpath()
        p.setBrush(QColor("#e46c0a"))
        p.drawPath(fin)
    p.setBrush(QColor("#1b2a8f"))
    p.drawEllipse(QPointF(0, -35 * s), 11 * s, 11 * s)
    flame = QPainterPath()
    flame.moveTo(-14 * s, 58 * s)
    flame.quadTo(0, 115 * s, 14 * s, 58 * s)
    flame.closeSubpath()
    p.setBrush(QColor("#ffcc33"))
    p.drawPath(flame)
    p.end()
    img.save(str(path))
    print("écrit", path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    res = ROOT / "flightcard" / "resources"
    build_manuals(res / "manuals")
    build_icon(res / "icons" / "app.png")
