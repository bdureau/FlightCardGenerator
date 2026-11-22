"""Outils XML communs : parsing sécurisé (defusedxml si disponible) et accès tolérant."""
from __future__ import annotations

import re
from typing import Iterable, Optional
from xml.etree.ElementTree import Element

try:  # protection contre les « billion laughs » et entités externes
    from defusedxml.ElementTree import fromstring as _fromstring  # type: ignore
except ImportError:  # pragma: no cover
    from xml.etree.ElementTree import fromstring as _fromstring

_NUM_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


class ParseError(Exception):
    """Erreur de lecture d'un fichier de simulation (message = clé i18n)."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


def parse_xml_bytes(data: bytes) -> Element:
    try:
        return _fromstring(data)
    except Exception as exc:  # ParseError, DefusedXmlException, ...
        raise ParseError("err_invalid_xml", str(exc)) from exc


def local(tag: str) -> str:
    """Supprime l'espace de noms éventuel : '{ns}name' → 'name'."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child(elem: Optional[Element], *names: str) -> Optional[Element]:
    """Premier enfant direct dont le nom (insensible à la casse) correspond."""
    if elem is None:
        return None
    wanted = {n.lower() for n in names}
    for c in elem:
        if local(c.tag).lower() in wanted:
            return c
    return None


def children(elem: Optional[Element], *names: str) -> list[Element]:
    if elem is None:
        return []
    wanted = {n.lower() for n in names}
    return [c for c in elem if local(c.tag).lower() in wanted]


def text(elem: Optional[Element], *names: str, default: str = "") -> str:
    """Texte d'un enfant direct, ou d'un attribut du même nom."""
    if elem is None:
        return default
    c = child(elem, *names)
    if c is not None and c.text is not None:
        return c.text.strip()
    lower_attrs = {k.lower(): v for k, v in elem.attrib.items()}
    for n in names:
        if n.lower() in lower_attrs:
            return lower_attrs[n.lower()].strip()
    return default


def num(value: Optional[str]) -> Optional[float]:
    """Premier nombre trouvé dans une chaîne (« auto 0.0125 » → 0.0125, « NaN » → None)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "auto", "none", "null", "-"}:
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        v = float(m.group(0))
    except ValueError:
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def child_num(elem: Optional[Element], *names: str) -> Optional[float]:
    return num(text(elem, *names, default=""))


def iter_local(elem: Element, *names: str) -> Iterable[Element]:
    wanted = {n.lower() for n in names}
    for e in elem.iter():
        if local(e.tag).lower() in wanted:
            yield e
