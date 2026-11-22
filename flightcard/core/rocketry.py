"""Règles métier de fuséologie : classes d'impulsion, niveaux Tripoli, rapport poussée/poids."""
from __future__ import annotations

import re
from typing import Optional

G0 = 9.81

# Bornes supérieures d'impulsion totale (Ns) par classe (NAR/TRA)
IMPULSE_CLASSES = [
    ("1/4A", 0.625), ("1/2A", 1.25), ("A", 2.5), ("B", 5), ("C", 10), ("D", 20),
    ("E", 40), ("F", 80), ("G", 160), ("H", 320), ("I", 640), ("J", 1280),
    ("K", 2560), ("L", 5120), ("M", 10240), ("N", 20480), ("O", 40960),
]

_DESIG_RE = re.compile(r"(?:^|[^A-Z])((?:1/[24])?[A-O])\s*-?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)


def impulse_class_from_designation(designation: str) -> str:
    m = _DESIG_RE.search((designation or "").upper())
    return m.group(1).upper() if m else ""


def avg_thrust_from_designation(designation: str) -> Optional[float]:
    """« H128W-14A » → 128.0 ; « C6-5 » → 6.0."""
    m = _DESIG_RE.search((designation or "").upper())
    if not m:
        return None
    try:
        return float(m.group(2).replace(",", "."))
    except ValueError:
        return None


def impulse_class_range(cls: str) -> Optional[tuple[float, float]]:
    prev = 0.0
    for name, upper in IMPULSE_CLASSES:
        if name == cls:
            return prev, upper
        prev = upper
    return None


def impulse_class_from_value(impulse: float) -> str:
    for name, upper in IMPULSE_CLASSES:
        if impulse <= upper + 1e-9:
            return name
    return "P+"


def certification_level_for_impulse(total_impulse: Optional[float]) -> str:
    """Niveau de certification Tripoli requis : '' (petite fusée), 'l1', 'l2', 'l3'."""
    if total_impulse is None:
        return ""
    if total_impulse <= 160.0:
        return "lp"            # faible puissance (pas de certification HPR)
    if total_impulse <= 640.0:
        return "l1"
    if total_impulse <= 5120.0:
        return "l2"
    return "l3"


def thrust_to_weight(avg_thrust_n: Optional[float], mass_kg: Optional[float]) -> Optional[float]:
    if not avg_thrust_n or not mass_kg or mass_kg <= 0:
        return None
    return avg_thrust_n / (mass_kg * G0)


def thrust_to_weight_verdict(ratio: Optional[float]) -> str:
    """'ok' (≥5), 'rso' (3..5), 'forbidden' (<3), '' inconnu."""
    if ratio is None:
        return ""
    if ratio >= 5.0:
        return "ok"
    if ratio >= 3.0:
        return "rso"
    return "forbidden"


def to_float(text) -> Optional[float]:
    """Convertit une saisie utilisateur (virgule ou point, unités éventuelles) en float."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None
