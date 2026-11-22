"""Sauvegarde / chargement d'une fiche de vol au format XML.

Exemple ::

    <flightcard version="1" generator="FlightCard Generator 1.0.0">
      <meta><source>fusee.ork</source><saved>2026-11-19T20:00:00</saved></meta>
      <fields><field name="rocket_name">Ariane</field>…</fields>
      <series columns="t,alt,vel">0,0,0;0.1,0.5,9.8;…</series>
      <logo format="png">iVBORw0…</logo>
    </flightcard>
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from .. import __app_name__, __version__
from ..core.card import FIELD_BY_KEY, FlightCard
from ..core.models import TimeSeries
from ..parsers.xmlutil import ParseError, child, children, parse_xml_bytes

FORMAT_VERSION = "1"


def save_card(card: FlightCard, path: str | Path) -> None:
    root = ET.Element("flightcard", version=FORMAT_VERSION,
                      generator=f"{__app_name__} {__version__}")
    meta = ET.SubElement(root, "meta")
    ET.SubElement(meta, "source").text = card.source_file
    ET.SubElement(meta, "saved").text = datetime.now().isoformat(timespec="seconds")

    fields = ET.SubElement(root, "fields")
    for key in FIELD_BY_KEY:              # ordre du schéma, champs connus uniquement
        value = card.values.get(key, "")
        el = ET.SubElement(fields, "field", name=key)
        el.text = value
    if not card.series.is_empty():
        s = card.series
        rows = []
        for i, t in enumerate(s.time):
            alt = s.altitude[i] if i < len(s.altitude) else 0.0
            vel = s.velocity[i] if i < len(s.velocity) else 0.0
            rows.append(f"{t:.4g},{alt:.5g},{vel:.5g}")
        ET.SubElement(root, "series", columns="t,alt,vel").text = ";".join(rows)
    if card.logo_png:
        ET.SubElement(root, "logo", format="png").text = base64.b64encode(card.logo_png).decode("ascii")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


def load_card(path: str | Path) -> FlightCard:
    root = parse_xml_bytes(Path(path).read_bytes())
    if root.tag != "flightcard":
        raise ParseError("err_card_xml")
    card = FlightCard()
    meta = child(root, "meta")
    src = child(meta, "source") if meta is not None else None
    card.source_file = (src.text or "") if src is not None else ""
    for el in children(child(root, "fields"), "field"):
        name = el.get("name", "")
        if name in FIELD_BY_KEY:
            card.values[name] = el.text or ""
    series = child(root, "series")
    if series is not None and series.text:
        ts = TimeSeries()
        for row in series.text.split(";"):
            parts = row.split(",")
            if len(parts) >= 3:
                try:
                    t, a, v = (float(x) for x in parts[:3])
                except ValueError:
                    continue
                ts.time.append(t)
                ts.altitude.append(a)
                ts.velocity.append(v)
        card.series = ts
    logo = child(root, "logo")
    if logo is not None and logo.text:
        try:
            card.logo_png = base64.b64decode(logo.text.strip(), validate=True)
        except (binascii.Error, ValueError):
            card.logo_png = None
    return card
