"""Moteur de rendu de la fiche de vol (QPainter).

Le même code dessine l'aperçu à l'écran (QImage), l'aperçu avant impression,
l'impression (QPrinter) et l'export PDF. Les coordonnées logiques sont exprimées
en dixièmes de millimètre sur une page A4 paysage (2970 × 2100).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QDate, QMarginsF, QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize,
                         QPainter, QPainterPath, QPen)
from PyQt6.QtPrintSupport import QPrinter

from .. import __app_name__
from ..core.card import FlightCard
from ..core.rocketry import thrust_to_weight_verdict, to_float
from ..i18n import Translator

PAGE_W, PAGE_H = 2970.0, 2100.0
MARGIN = 70.0
FONT_FAMILIES = ["Arial", "Helvetica", "Helvetica Neue", "Liberation Sans", "DejaVu Sans",
                 "Noto Sans", "Segoe UI", "sans-serif"]

NAVY = QColor("#1b2a8f")
ORANGE = QColor("#e46c0a")
YELLOW = QColor("#ffff4d")
GRID = QColor("#000000")
GREEN = QColor("#1e8449")
AMBER = QColor("#b9770e")
RED = QColor("#c0392b")
GREY = QColor("#666666")

# Colonnes de la carte (x relatifs à la marge)
XA, XB, XC, XD, XE, XF, XG, XEND = 0, 570, 860, 1150, 1380, 1830, 2160, 2830


def make_font(size: float, bold=False, italic=False, underline=False) -> QFont:
    f = QFont()
    f.setFamilies(FONT_FAMILIES)
    f.setPixelSize(max(1, int(round(size))))
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(underline)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    return f


def setup_printer_page(printer: QPrinter) -> None:
    layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape,
                         QMarginsF(5, 5, 5, 5),
                         QPageLayout.Unit.Millimeter)
    printer.setPageLayout(layout)


class CardRenderer:
    def __init__(self, card: FlightCard, tr: Translator, logo: Optional[QImage] = None,
                 include_annex: bool = True):
        self.card = card
        self.tr = tr
        self.logo = logo if logo is not None and not logo.isNull() else None
        self.include_annex = include_annex
        self.p: Optional[QPainter] = None

    # ================================================================ API publique
    def page_count(self) -> int:
        return 2 if self.include_annex else 1

    def render_page(self, painter: QPainter, target: QRectF, page: int) -> None:
        self.p = painter
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        s = min(target.width() / PAGE_W, target.height() / PAGE_H)
        painter.translate(target.x() + (target.width() - PAGE_W * s) / 2,
                          target.y() + (target.height() - PAGE_H * s) / 2)
        painter.scale(s, s)
        painter.fillRect(QRectF(0, 0, PAGE_W, PAGE_H), Qt.GlobalColor.white)
        painter.translate(MARGIN, MARGIN)
        if page == 0:
            self._draw_card()
        else:
            self._draw_annex()
        self._draw_footer(page)
        painter.restore()
        self.p = None

    def render_to_printer(self, printer: QPrinter) -> None:
        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError("Unable to start printing")
        try:
            rect = printer.pageLayout().paintRectPixels(printer.resolution())
            target = QRectF(0, 0, rect.width(), rect.height())
            for i in range(self.page_count()):
                if i:
                    printer.newPage()
                self.render_page(painter, target, i)
        finally:
            painter.end()

    def render_to_image(self, page: int, width_px: int = 1600) -> QImage:
        height = int(width_px * PAGE_H / PAGE_W)
        img = QImage(width_px, height, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        try:
            self.render_page(painter, QRectF(0, 0, width_px, height), page)
        finally:
            painter.end()
        return img

    def export_pdf(self, path: str | Path) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(path))
        setup_printer_page(printer)
        printer.setDocName(self.card.get("rocket_name") or "flight card")
        self.render_to_printer(printer)

    # ================================================================ primitives
    def _fit_font(self, rect: QRectF, text: str, font: QFont, flags: int,
                  min_ratio: float = 0.55) -> QFont:
        size = font.pixelSize()
        f = QFont(font)
        min_size = max(8, int(size * min_ratio))
        while size > min_size:
            f.setPixelSize(size)
            br = QFontMetricsF(f).boundingRect(rect, flags, text)
            if br.width() <= rect.width() + 0.5 and br.height() <= rect.height() + 0.5:
                return f
            size -= 1
        f.setPixelSize(min_size)
        return f

    def text(self, rect: QRectF, text: str, size: float = 30, *, bold=False, italic=False,
             underline=False, color: QColor = QColor("black"), align: str = "left",
             valign: str = "center", wrap: bool = False, pad: float = 12, shrink: bool = True):
        if not text:
            return
        p = self.p
        r = rect.adjusted(pad, 3, -pad, -3)
        h = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
             "right": Qt.AlignmentFlag.AlignRight}[align]
        v = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter,
             "bottom": Qt.AlignmentFlag.AlignBottom}[valign]
        flags = int(h | v)
        if wrap:
            flags |= int(Qt.TextFlag.TextWordWrap)
        font = make_font(size, bold, italic, underline)
        if shrink:
            font = self._fit_font(r, text, font, flags)
        p.setFont(font)
        p.setPen(color)
        if not wrap:
            fm = QFontMetricsF(font)
            if fm.horizontalAdvance(text) > r.width():
                text = fm.elidedText(text, Qt.TextElideMode.ElideRight, r.width())
        p.drawText(r, flags, text)

    def box(self, rect: QRectF, fill: Optional[QColor] = None, width: float = 2.0):
        p = self.p
        if fill is not None:
            p.fillRect(rect, fill)
        p.setPen(QPen(GRID, width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect)

    def checkbox(self, x: float, y: float, checked: bool, size: float = 34):
        p = self.p
        r = QRectF(x, y, size * 1.25, size)
        p.setPen(QPen(GRID, 2.5))
        p.setBrush(Qt.GlobalColor.white)
        p.drawRect(r)
        if checked:
            p.setPen(QPen(NAVY, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            path = QPainterPath()
            path.moveTo(r.left() + r.width() * 0.2, r.top() + r.height() * 0.55)
            path.lineTo(r.left() + r.width() * 0.43, r.bottom() - r.height() * 0.18)
            path.lineTo(r.right() - r.width() * 0.15, r.top() + r.height() * 0.15)
            p.drawPath(path)

    # Helpers de grille ------------------------------------------------------
    def _row_y(self, k: int) -> float:
        return (2 + k) * self.R

    def cell(self, x0: float, x1: float, k0: int, k1: int, text: str = "", *,
             fill: Optional[QColor] = None, **kw) -> QRectF:
        rect = QRectF(x0, self._row_y(k0), x1 - x0, self._row_y(k1 + 1) - self._row_y(k0))
        self.box(rect, fill)
        if text:
            self.text(rect, text, kw.pop("size", self.FS), **kw)
        return rect

    def check_cell(self, x0: float, x1: float, k: int, label: str, checked: bool,
                   color: QColor = QColor("black"), align: str = "left", **kw):
        rect = self.cell(x0, x1, k, k)
        box_w = 34 * 1.25
        bx = rect.right() - box_w - 40
        self.text(QRectF(rect.left(), rect.top(), bx - rect.left() - 10, rect.height()),
                  label, self.FS, color=color, align=align, **kw)
        self.checkbox(bx, rect.center().y() - 17, checked)

    def yes_no_cell(self, x0: float, x1: float, k0: int, k1: int, value: Optional[bool] = None):
        rect = self.cell(x0, x1, k0, k1)
        cy = rect.center().y() - 17
        w = rect.width()
        x = rect.left() + 12
        self.text(QRectF(x, rect.top(), w * 0.22, rect.height()), self.tr("pc_yes"), self.FS, pad=0)
        self.checkbox(x + w * 0.22, cy, value is True)
        x2 = rect.left() + w * 0.52
        self.text(QRectF(x2, rect.top(), w * 0.22, rect.height()),
                  self.tr("pc_no").capitalize(), self.FS, pad=0)
        self.checkbox(x2 + w * 0.22, cy, value is False)

    # ================================================================ valeurs
    def v(self, key: str) -> str:
        return self.card.get(key).strip()

    def flag(self, key: str) -> bool:
        return self.card.flag(key)

    def _date_text(self) -> str:
        d = QDate.fromString(self.v("flight_date"), "yyyy-MM-dd")
        if d.isValid():
            return self.tr.locale.toString(d, "d MMMM yyyy")
        return self.v("flight_date")

    def _level_text(self) -> str:
        lvl = self.v("pilot_level")
        return self.tr(f"level_{lvl}") if lvl else ""

    def _yes_no_text(self, key: str) -> str:
        val = self.v(key)
        if val == "yes":
            return self.tr("yes")
        if val == "no":
            return self.tr("no")
        return val

    # ================================================================ page 1
    def _draw_card(self):
        self.R = 63.0
        self.FS = 30.0
        R, tr, v = self.R, self.tr, self.v
        p = self.p

        # --- En-tête -----------------------------------------------------------
        head = QRectF(XA, 0, XE - XA, 2 * R)
        self.box(head)
        title_x = XA
        if self.logo is not None:
            lr = QRectF(XA + 15, 8, 2 * R * 1.6, 2 * R - 16)
            img = self.logo.scaled(int(lr.width() * 4), int(lr.height() * 4),
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            sw = lr.height() * img.width() / max(1, img.height())
            sw = min(sw, lr.width())
            sh = sw * img.height() / max(1, img.width())
            p.drawImage(QRectF(lr.left(), lr.center().y() - sh / 2, sw, sh), img)
            title_x = lr.left() + sw + 20
        self.text(QRectF(title_x, 0, XE - title_x, 2 * R), tr("pc_title"), 64, bold=True,
                  color=NAVY, align="center")
        date_rect = QRectF(XE, 0, XEND - XE, 2 * R)
        self.box(date_rect)
        place = " — ".join(x for x in (self._date_text(), v("flight_location")) if x)
        self.text(QRectF(XE, 0, 520, 2 * R), tr("pc_date_place"), self.FS)
        self.text(QRectF(XE + 500, 0, XEND - XE - 500, 2 * R), place, 36, bold=True,
                  color=NAVY, wrap=True)

        # --- Partie gauche -----------------------------------------------------
        name = " ".join(x for x in (v("pilot_firstname"), v("pilot_lastname").upper()) if x)
        self.cell(XA, XB, 0, 0, tr("pc_pilot_name"), bold=True, align="center")
        self.cell(XB, XE, 0, 0, name, bold=True, color=NAVY)
        self.cell(XA, XB, 1, 1, tr("pc_license"), align="center")
        self.cell(XB, XE, 1, 1, v("pilot_license"))
        self.cell(XA, XB, 2, 2, tr("pc_mass"), align="center")
        self.cell(XB, XE, 2, 2, v("rocket_mass_kg"), bold=True)
        lvl = self._level_text()
        self.cell(XA, XE, 3, 3, f"{tr('pc_cert_level')}  {lvl}" if lvl else tr("pc_cert_level"),
                  fill=YELLOW, bold=bool(lvl))

        self.cell(XA, XB, 4, 4, tr("pc_motors"), bold=True, color=NAVY, align="center")
        self.cell(XB, XC, 4, 4, tr("pc_col_type"), bold=True, color=NAVY, align="center")
        self.cell(XC, XD, 4, 4, tr("pc_col_mfg"), bold=True, color=NAVY, align="center")
        self.cell(XD, XE, 4, 4, tr("pc_col_impulse"), bold=True, color=NAVY, align="center")
        for k, row, lbl in ((5, "stage1", "pc_stage1"), (6, "stage2", "pc_stage2"),
                            (7, "cluster", "pc_cluster")):
            self.cell(XA, XB, k, k, tr(lbl), align="center")
            self.cell(XB, XC, k, k, v(f"{row}_type"), align="center", bold=True)
            self.cell(XC, XD, k, k, v(f"{row}_manufacturer"), align="center")
            self.cell(XD, XE, k, k, v(f"{row}_impulse"), align="center")
        self.cell(XA, XD, 8, 8, tr("pc_total_impulse"), bold=True, align="center")
        self.cell(XD, XE, 8, 8, v("total_impulse"), bold=True, align="center")

        tw_rect = self.cell(XA, XD, 9, 11)
        self.text(QRectF(tw_rect.left(), tw_rect.top(), tw_rect.width(), R),
                  f"{tr('pc_tw_title')}  {tr('pc_tw_formula')}", 27, bold=True)
        rules = "\n".join(tr(k) for k in ("pc_tw_rule1", "pc_tw_rule2", "pc_tw_rule3"))
        self.text(QRectF(tw_rect.left(), tw_rect.top() + R * 0.85, tw_rect.width(), R * 2.1),
                  rules, 23, valign="top", wrap=True)
        tw_cell = self.cell(XD, XE, 9, 11)
        ratio = to_float(v("thrust_weight_ratio"))
        verdict = thrust_to_weight_verdict(ratio)
        col = {"ok": GREEN, "rso": AMBER, "forbidden": RED}.get(verdict, QColor("black"))
        self.text(QRectF(tw_cell.left(), tw_cell.top(), tw_cell.width(), tw_cell.height() * 0.62),
                  v("thrust_weight_ratio"), 52, bold=True, color=col, align="center")
        if verdict:
            self.text(QRectF(tw_cell.left(), tw_cell.top() + tw_cell.height() * 0.55,
                             tw_cell.width(), tw_cell.height() * 0.45),
                      tr(f"tw_{verdict}"), 20, color=col, align="center", wrap=True, pad=6)

        self.cell(XA, XC, 12, 12, tr("pc_sim_altitude"), align="center")
        self.cell(XC, XD, 12, 12, v("sim_apogee_m"), bold=True, align="center")
        self.cell(XD, XE, 12, 12, tr("pc_meters"), align="center")
        self.cell(XA, XB, 13, 13, tr("pc_first_flight"))
        self.cell(XB, XC, 13, 13, self._yes_no_text("first_flight"), bold=True, align="center")
        self.cell(XC, XE, 13, 13, fill=YELLOW)
        self.cell(XA, XE, 14, 16, tr("pc_pilot_signature"), bold=True, italic=True,
                  underline=True, color=NAVY, valign="top", size=32)

        # LCO
        self.cell(XA, XB, 17, 17, tr("pc_lco"), bold=True, color=ORANGE, size=40)
        self.cell(XB, XC, 17, 17)
        self.cell(XC, XE, 17, 17, tr("pc_notes"), bold=True, color=NAVY, align="center")
        self.cell(XA, XB, 18, 18, tr("pc_launcher_type"), bold=True, color=NAVY)
        self.check_cell(XB, XC, 18, tr("pc_rod"), self.flag("launch_rod"))
        self.cell(XC, XD, 18, 18, tr("pc_pilot"), align="center")
        self.cell(XD, XE, 18, 18, tr("pc_lco"), align="center")
        self.cell(XA, XB, 19, 19)
        self.check_cell(XB, XC, 19, tr("pc_rail").capitalize(), self.flag("launch_rail"))
        self.cell(XA, XB, 20, 20, tr("pc_flight_type"), bold=True, color=NAVY)
        self.cell(XB, XC, 20, 20)
        for k, key in zip(range(21, 28), ("pc_stable", "pc_overstable", "pc_unstable",
                                          "pc_ballistic", "pc_recovery_failure",
                                          "pc_igniter_failure", "pc_motor_failure")):
            self.cell(XA, XB, k, k, tr(key).capitalize() if k == 21 else tr(key), align="right")
            rect = self.cell(XB, XC, k, k)
            self.checkbox(rect.left() + 30, rect.center().y() - 17, False)
        notes = self.cell(XC, XD, 19, 27)
        self.text(notes, v("pilot_notes"), 24, valign="top", wrap=True)
        self.cell(XD, XE, 19, 27)

        # --- Partie droite -------------------------------------------------------
        self.cell(XE, XF, 0, 0, tr("pc_rocket_name"), bold=True, align="center")
        self.cell(XF, XEND, 0, 0, v("rocket_name"), bold=True, color=NAVY, size=34)
        self.cell(XE, XF, 1, 1, tr("pc_level"))
        self.cell(XF, XG, 1, 1, v("flight_level"), fill=YELLOW, bold=True, align="center")
        self.cell(XG, XEND, 1, 1, tr("pc_ejection"), bold=True, color=NAVY, align="center")
        self.cell(XE, XG, 2, 2, tr("pc_rocket_type"), bold=True, color=NAVY, align="center")
        self.check_cell(XG, XEND, 2, tr("pc_ej_charge"), self.flag("ejection_charge"))
        self.cell(XE, XF, 3, 3, tr("pc_length"), align="right")
        self.cell(XF, XG, 3, 3, v("rocket_length_cm"), bold=True, align="center")
        self.check_cell(XG, XEND, 3, tr("pc_ej_electronic"), self.flag("ejection_electronic"))
        self.cell(XE, XF, 4, 4, tr("pc_diameter"), align="right")
        self.cell(XF, XG, 4, 4, v("rocket_diameter_mm"), bold=True, align="center")
        self.check_cell(XG, XEND, 4, tr("pc_ej_dual"), self.flag("ejection_dual"))
        self.cell(XE, XF, 5, 7, tr("pc_static_margin"), size=26, wrap=True, align="center")
        stab = to_float(v("stability_cal"))
        stab_col = RED if (stab is not None and stab < 1.0) else QColor("black")
        self.cell(XF, XG, 5, 7, v("stability_cal") + (" cal" if v("stability_cal") else ""),
                  bold=True, align="center", size=40, color=stab_col)
        self.cell(XG, XEND, 5, 5, tr("pc_recovery"), bold=True, color=NAVY, align="center")
        self.check_cell(XG, XEND, 6, tr("pc_streamer"), self.flag("recovery_streamer"))
        self.check_cell(XG, XEND, 7, tr("pc_parachute").capitalize(), self.flag("recovery_parachute"))
        for k, key, flag in ((8, "pc_kit", "kit"), (9, "pc_kit_modified", "kit_modified"),
                             (10, "pc_scratch", "scratch_built")):
            self.cell(XE, XF, k, k, tr(key), align="center")
            rect = self.cell(XF, XG, k, k)
            self.checkbox(rect.left() + 50, rect.center().y() - 17, self.flag(flag))
        self.cell(XG, XEND, 8, 8)
        self.check_cell(XG, XEND, 9, tr("pc_dual_parachute"), self.flag("recovery_dual_parachute"))
        other = v("recovery_other")
        self.cell(XG, XEND, 10, 10, f"{tr('pc_other')} {other}".strip())
        self.cell(XE, XF, 11, 11, tr("pc_sim_software"), align="center")
        self.cell(XF, XG, 11, 11, v("sim_software"), size=26, align="center")
        self.cell(XG, XEND, 11, 11, tr("pc_model"), bold=True, color=NAVY, align="center")
        self.cell(XE, XF, 12, 12, tr("pc_cg_cp"), size=26, align="center")
        cgcp = " / ".join(x or "—" for x in (v("rocket_cg_cm"), v("rocket_cp_cm")))
        self.cell(XF, XG, 12, 12, cgcp if cgcp != "— / —" else "", bold=True, align="center")
        self.check_cell(XG, XEND, 12, tr("pc_classic"), self.flag("model_classic"))
        self.cell(XE, XG, 13, 13, tr("pc_payload"), align="center", size=28)
        self.check_cell(XG, XEND, 13, tr("pc_fantasy"), self.flag("model_fantasy"))
        pay = self.cell(XE, XG, 14, 16)
        self.text(pay, v("payload"), 26, wrap=True, valign="top")
        self.check_cell(XG, XEND, 14, tr("pc_scale"), self.flag("model_scale"))
        self.cell(XG, XEND, 15, 16)

        # RSO
        self.cell(XE, XF, 17, 17, tr("pc_rso"), bold=True, color=ORANGE, size=40)
        self.cell(XF, XG, 17, 17)
        self.cell(XG, XEND, 17, 17, tr("pc_rso_signature"), bold=True, italic=True,
                  underline=True, color=ORANGE, align="center")
        for k, key in zip(range(18, 23), ("pc_motor_sheet", "pc_sim_sheet", "pc_cpcg_marked",
                                          "pc_recovery_system", "pc_rigid")):
            self.cell(XE, XF, k, k, tr(key), align="right")
            self.yes_no_cell(XF, XG, k, k)
        self.cell(XE, XF, 23, 24, tr("pc_safety_device"), align="center", wrap=True)
        self.yes_no_cell(XF, XG, 23, 24)
        self.cell(XE, XF, 25, 25, tr("pc_validation"), bold=True, color=NAVY, align="center")
        self.yes_no_cell(XF, XG, 25, 25)
        self.cell(XG, XEND, 18, 25)
        self.cell(XE, XEND, 26, 26, tr("pc_remarks"), italic=True)
        self.cell(XE, XEND, 27, 27, tr("pc_disclaimer"), bold=True, italic=True, color=NAVY,
                  align="center", size=24)

        # Cadre épais + séparation centrale
        p.setPen(QPen(GRID, 7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(XA, 0, XEND - XA, self._row_y(28)))
        p.drawLine(QPointF(XE, 0), QPointF(XE, self._row_y(28)))
        p.setPen(QPen(GRID, 5))
        p.drawLine(QPointF(XA, self._row_y(17)), QPointF(XEND, self._row_y(17)))

    # ================================================================ page 2
    def _section(self, x: float, y: float, w: float, title: str,
                 rows: list[tuple[str, str]], label_ratio: float = 0.62, rh: float = 50) -> float:
        hdr = QRectF(x, y, w, rh)
        self.box(hdr, QColor("#e8ebf7"))
        self.text(hdr, title, 28, bold=True, color=NAVY)
        y += rh
        for label, value in rows:
            lr = QRectF(x, y, w * label_ratio, rh)
            vr = QRectF(x + w * label_ratio, y, w * (1 - label_ratio), rh)
            self.box(lr)
            self.box(vr)
            self.text(lr, label, 24)
            self.text(vr, value or "—", 25, bold=bool(value), align="right",
                      color=QColor("black") if value else GREY)
            y += rh
        return y

    def _text_section(self, x: float, y: float, w: float, h: float, title: str, body: str,
                      size: float = 23, rh: float = 50) -> float:
        hdr = QRectF(x, y, w, rh)
        self.box(hdr, QColor("#e8ebf7"))
        self.text(hdr, title, 28, bold=True, color=NAVY)
        rect = QRectF(x, y + rh, w, max(rh, h - rh))
        self.box(rect)
        self.text(rect, body or "—", size, wrap=True, valign="top",
                  color=QColor("black") if body else GREY)
        return y + rh + rect.height()

    def _lbl(self, key: str) -> str:
        return self.tr(f"lbl_{key}")

    def _draw_annex(self):
        tr, v = self.tr, self.v
        W = PAGE_W - 2 * MARGIN
        # En-tête
        head_h = 140
        x_title = 0
        if self.logo is not None:
            img = self.logo
            h = head_h - 20
            w = min(300, h * img.width() / max(1, img.height()))
            h2 = w * img.height() / max(1, img.width())
            self.p.drawImage(QRectF(0, (head_h - h2) / 2, w, h2), img)
            x_title = w + 30
        self.text(QRectF(x_title, 0, 1500, head_h * 0.6), tr("an_title"), 48, bold=True,
                  color=NAVY, pad=0)
        sub = " — ".join(x for x in (v("rocket_name"), v("sim_name")) if x)
        self.text(QRectF(x_title, head_h * 0.55, 1500, head_h * 0.45), sub, 30, pad=0)
        pilot = " ".join(x for x in (v("pilot_firstname"), v("pilot_lastname").upper()) if x)
        right = "\n".join(x for x in (pilot, " — ".join(y for y in (self._date_text(),
                                                                    v("flight_location")) if y)) if x)
        self.text(QRectF(W - 1100, 0, 1100, head_h), right, 30, align="right", wrap=True, pad=0)
        self.p.setPen(QPen(NAVY, 6))
        self.p.drawLine(QPointF(0, head_h + 10), QPointF(W, head_h + 10))

        gap = 40
        cw = (W - 2 * gap) / 3
        x1, x2, x3 = 0, cw + gap, 2 * (cw + gap)
        top = head_h + 40

        rocket_rows = [(self._lbl(k), v(k)) for k in (
            "rocket_name", "rocket_length_cm", "rocket_diameter_mm", "rocket_mass_kg",
            "rocket_dry_mass_kg", "rocket_cg_cm", "rocket_cp_cm", "stability_cal", "stage_count",
            "flight_level", "sim_software")]
        y1 = self._section(x1, top, cw, tr("an_rocket"), rocket_rows)
        rec_txt = v("recovery_details")
        flags = [self._lbl(k) for k in ("ejection_charge", "ejection_electronic", "ejection_dual",
                                         "recovery_streamer", "recovery_parachute",
                                         "recovery_dual_parachute") if self.flag(k)]
        if v("recovery_other"):
            flags.append(v("recovery_other"))
        rec_body = "\n".join(x for x in (", ".join(flags), rec_txt) if x)
        y1 = self._text_section(x1, y1 + 30, cw, 280, tr("an_recovery"), rec_body)

        prop_rows = []
        for row, lbl in (("stage1", "row_stage1"), ("stage2", "row_stage2"), ("cluster", "row_cluster")):
            parts = [v(f"{row}_type"), v(f"{row}_manufacturer")]
            txt = " — ".join(x for x in parts if x)
            imp = v(f"{row}_impulse")
            if imp:
                txt += f"  ({imp} Ns)"
            prop_rows.append((tr(lbl), txt))
        prop_rows += [(self._lbl(k), v(k)) for k in ("total_impulse", "avg_thrust_n",
                                                     "thrust_weight_ratio", "sim_max_thrust")]
        y2 = self._section(x2, top, cw, tr("an_propulsion"), prop_rows, label_ratio=0.42)
        y2 = self._text_section(x2, y2, cw, 170, self._lbl("motor_details"), v("motor_details"), 21)
        cond_rows = [(self._lbl(k), v(k)) for k in (
            "sim_rod_length", "sim_rod_angle", "sim_wind_speed", "sim_launch_altitude",
            "sim_latitude", "sim_longitude", "sim_temperature", "sim_pressure")]
        y2 = self._section(x2, y2 + 30, cw, tr("an_conditions"), cond_rows)

        res_rows = [(self._lbl(k), v(k)) for k in (
            "sim_apogee_m", "sim_max_velocity", "sim_max_accel", "sim_max_mach",
            "sim_time_to_apogee", "sim_burnout_time", "sim_burnout_altitude",
            "sim_rail_exit_velocity", "sim_deployment_velocity", "sim_ground_hit_velocity",
            "sim_optimum_delay", "sim_flight_time")]
        y3 = self._section(x3, top, cw, tr("an_results"), res_rows)

        bottom = PAGE_H - 2 * MARGIN - 70
        # Colonne de droite : événements, avertissements, remarques
        remaining = bottom - (y3 + 30)
        ev_h = remaining * 0.45
        y3 = self._text_section(x3, y3 + 30, cw, ev_h, tr("an_events"), v("sim_events"), 21)
        rest = bottom - (y3 + 30)
        y3 = self._text_section(x3, y3 + 30, cw, rest * 0.45, tr("an_warnings"), v("sim_warnings"), 21)
        self._text_section(x3, y3 + 30, cw, bottom - (y3 + 30), tr("an_remarks"), v("remarks"), 22)

        chart_top = max(y1, y2) + 40
        self._draw_chart(QRectF(0, chart_top, 2 * cw + gap, bottom - chart_top))

    # ---------------------------------------------------------------- graphique
    @staticmethod
    def _nice_step(span: float, target: int = 6) -> float:
        if span <= 0:
            return 1.0
        raw = span / target
        mag = 10 ** math.floor(math.log10(raw))
        for m in (1, 2, 2.5, 5, 10):
            if raw <= m * mag:
                return m * mag
        return 10 * mag

    def _draw_chart(self, rect: QRectF):
        tr, p = self.tr, self.p
        hdr = QRectF(rect.left(), rect.top(), rect.width(), 50)
        self.box(hdr, QColor("#e8ebf7"))
        self.text(hdr, tr("an_chart"), 28, bold=True, color=NAVY)
        body = QRectF(rect.left(), rect.top() + 50, rect.width(), rect.height() - 50)
        self.box(body)
        s = self.card.series
        if s.is_empty() or body.height() < 200:
            self.text(body, tr("an_no_chart"), 26, color=GREY, align="center")
            return
        plot = body.adjusted(150, 40, -150, -100)
        t_max = max(s.time) or 1.0
        a_max = max(max(s.altitude), 1.0)
        v_vals = s.velocity or [0.0]
        v_min, v_max = min(min(v_vals), 0.0), max(max(v_vals), 1.0)

        def nice_max(m):
            st = self._nice_step(m, 5)
            return st * math.ceil(m / st), st

        t_top, t_step = nice_max(t_max)
        a_top, a_step = nice_max(a_max)
        v_span = v_max - v_min
        v_step = self._nice_step(v_span, 5)
        v_bot = v_step * math.floor(v_min / v_step)
        v_top = v_step * math.ceil(v_max / v_step)

        def X(t): return plot.left() + plot.width() * t / t_top
        def YA(a): return plot.bottom() - plot.height() * a / a_top
        def YV(vv): return plot.bottom() - plot.height() * (vv - v_bot) / max(1e-9, v_top - v_bot)

        p.setFont(make_font(21))
        grid_pen = QPen(QColor("#d5d8e3"), 1.5)
        # grille + graduations altitude
        n = int(round(a_top / a_step))
        for i in range(n + 1):
            a = i * a_step
            y = YA(a)
            p.setPen(grid_pen)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(NAVY)
            p.drawText(QRectF(plot.left() - 140, y - 20, 125, 40),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), f"{a:g}")
        # graduations vitesse
        nv = int(round((v_top - v_bot) / v_step))
        p.setPen(ORANGE)
        for i in range(nv + 1):
            vv = v_bot + i * v_step
            y = YV(vv)
            p.drawText(QRectF(plot.right() + 15, y - 20, 130, 40),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), f"{vv:g}")
        # graduations temps
        nt = int(round(t_top / t_step))
        for i in range(nt + 1):
            t = i * t_step
            x = X(t)
            p.setPen(grid_pen)
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            p.setPen(QColor("black"))
            p.drawText(QRectF(x - 70, plot.bottom() + 8, 140, 36),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), f"{t:g}")
        p.setPen(QPen(QColor("black"), 3))
        p.drawRect(plot)
        # courbes
        def poly(ys, mapper, color, width):
            path = QPainterPath()
            for i, (t, y) in enumerate(zip(s.time, ys)):
                pt = QPointF(X(t), mapper(y))
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            p.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        if s.velocity:
            poly(s.velocity, YV, ORANGE, 4)
        poly(s.altitude, YA, NAVY, 6)
        # apogée
        i_ap = max(range(len(s.altitude)), key=lambda i: s.altitude[i])
        ap = QPointF(X(s.time[i_ap]), YA(s.altitude[i_ap]))
        p.setBrush(NAVY)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(ap, 9, 9)
        label = f"{s.altitude[i_ap]:.0f} m @ {s.time[i_ap]:.1f} s"
        font = make_font(22, bold=True)
        p.setFont(font)
        tw = QFontMetricsF(font).horizontalAdvance(label) + 16
        lx = min(ap.x() + 15, plot.right() - tw)
        lrect = QRectF(lx, max(plot.top() + 2, ap.y() - 48), tw, 36)
        p.fillRect(lrect, QColor(255, 255, 255, 220))
        p.setPen(NAVY)
        p.drawText(lrect, int(Qt.AlignmentFlag.AlignCenter), label)
        # titres d'axes
        p.setFont(make_font(22, bold=True))
        p.setPen(QColor("black"))
        p.drawText(QRectF(plot.left(), plot.bottom() + 48, plot.width(), 40),
                   int(Qt.AlignmentFlag.AlignHCenter), tr("an_time_axis"))
        for label, color, x, angle in ((tr("an_alt_axis"), NAVY, body.left() + 20, -90),
                                       (tr("an_vel_axis"), ORANGE, body.right() - 20, 90)):
            p.save()
            p.translate(x, plot.center().y())
            p.rotate(angle)
            p.setPen(color)
            p.drawText(QRectF(-plot.height() / 2, -5, plot.height(), 40),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), label)
            p.restore()

    # ================================================================ pied de page
    def _draw_footer(self, page: int):
        W = PAGE_W - 2 * MARGIN
        y = PAGE_H - 2 * MARGIN - 50
        footer = self.tr("pc_footer", app=__app_name__,
                         date=self.tr.locale.toString(QDate.currentDate(), "d MMMM yyyy"))
        self.text(QRectF(0, y, W * 0.45, 50), footer, 20, color=GREY, pad=0)
        src = Path(self.card.source_file).name if self.card.source_file else ""
        if src or self.v("sim_name"):
            self.text(QRectF(W * 0.45, y, W * 0.47, 50),
                      self.tr("pc_source", file=src or "—", sim=self.v("sim_name") or "—"),
                      20, color=GREY, align="right", pad=0)
        if self.page_count() > 1:
            self.text(QRectF(W * 0.93, y, W * 0.07, 50), f"{page + 1}/{self.page_count()}", 20,
                      color=GREY, align="right", pad=0)

