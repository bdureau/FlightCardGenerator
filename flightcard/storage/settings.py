"""Persistance locale (JSON) : profil pilote, historique des lieux, logo, préférences."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .paths import user_data_dir

MAX_LOCATIONS = 30


@dataclass
class PilotProfile:
    lastname: str = ""
    firstname: str = ""
    license: str = ""
    level: str = ""          # "", "junior", "l1", "l2", "l3"


@dataclass
class AppSettings:
    ui_language: str = ""
    print_language: str = ""
    print_annex: bool = True
    pilot: PilotProfile = field(default_factory=PilotProfile)
    locations: list[str] = field(default_factory=list)
    last_location: str = ""
    logo_file: str = ""      # nom du fichier copié dans le dossier de données
    last_dir: str = ""
    window_geometry: str = ""
    window_state: str = ""
    splitter_state: str = ""


class SettingsStore:
    """Lit / écrit ``settings.json`` dans le répertoire de données standard de l'OS."""

    FILE_NAME = "settings.json"

    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory) if directory else user_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / self.FILE_NAME
        self.settings = self._load()

    # ------------------------------------------------------------------ E/S
    def _load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return AppSettings()
        s = AppSettings()
        for k, v in data.items():
            if k == "pilot" and isinstance(v, dict):
                s.pilot = PilotProfile(**{pk: str(pv) for pk, pv in v.items()
                                          if pk in PilotProfile.__dataclass_fields__})
            elif k == "locations" and isinstance(v, list):
                s.locations = [str(x) for x in v if str(x).strip()][:MAX_LOCATIONS]
            elif k in AppSettings.__dataclass_fields__:
                setattr(s, k, v)
        return s

    def save(self) -> None:
        payload = json.dumps(asdict(self.settings), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".settings-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)       # écriture atomique
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------ lieux
    def remember_location(self, place: str) -> None:
        place = place.strip()
        if not place:
            return
        locs = [p for p in self.settings.locations if p.casefold() != place.casefold()]
        self.settings.locations = [place] + locs[:MAX_LOCATIONS - 1]
        self.settings.last_location = place

    def forget_location(self, place: str) -> None:
        self.settings.locations = [p for p in self.settings.locations if p != place]
        if self.settings.last_location == place:
            self.settings.last_location = ""

    # ------------------------------------------------------------------ logo
    @property
    def logo_path(self) -> Optional[Path]:
        if not self.settings.logo_file:
            return None
        p = self.directory / self.settings.logo_file
        return p if p.is_file() else None

    def set_logo(self, source: Optional[Path]) -> Optional[Path]:
        """Copie le logo dans le dossier de données (l'original peut ensuite être déplacé)."""
        for old in self.directory.glob("logo.*"):
            try:
                old.unlink()
            except OSError:
                pass
        if source is None:
            self.settings.logo_file = ""
            return None
        ext = Path(source).suffix.lower() or ".png"
        dest = self.directory / f"logo{ext}"
        shutil.copyfile(source, dest)
        self.settings.logo_file = dest.name
        return dest

    def set_logo_bytes(self, data: bytes, ext: str = ".png") -> Path:
        for old in self.directory.glob("logo.*"):
            try:
                old.unlink()
            except OSError:
                pass
        dest = self.directory / f"logo{ext}"
        dest.write_bytes(data)
        self.settings.logo_file = dest.name
        return dest
