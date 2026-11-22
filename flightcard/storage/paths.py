"""Chemins multiplateformes : ressources embarquées et répertoire de données utilisateur."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths


def resource_dir() -> Path:
    """Dossier des ressources (compatible PyInstaller via sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "flightcard" / "resources"
    return Path(__file__).resolve().parent.parent / "resources"


def manual_path(lang: str) -> Path:
    return resource_dir() / "manuals" / f"manual_{lang}.pdf"


def user_data_dir() -> Path:
    """%APPDATA%\\FlightCard\\FlightCard Generator, ~/Library/Application Support/…,
    ~/.local/share/… selon l'OS (QApplication doit avoir un nom d'organisation/app)."""
    loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    path = Path(loc) if loc else Path.home() / ".flightcard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def documents_dir() -> Path:
    loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(loc) if loc else Path.home()
