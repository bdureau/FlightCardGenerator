"""Initialisation de l'application Qt."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from . import __app_name__, __org_name__, __version__
from .i18n import LANGUAGES, LanguageManager, detect_system_language
from .storage.settings import SettingsStore


class FlightCardApplication(QApplication):
    """QApplication gérant l'ouverture de fichiers par le système.

    Sous macOS, un double-clic sur un .ork / .rkt / .xml dans le Finder (ou un dépôt sur
    l'icône du Dock) n'arrive pas dans ``sys.argv`` mais sous forme de ``QEvent.FileOpen``,
    parfois avant même la création de la fenêtre : les chemins sont donc mis en attente.
    """
    fileOpenRequested = pyqtSignal(str)

    def __init__(self, argv):
        super().__init__(argv)
        self.pending_files: list[str] = []
        self._ready = False

    def event(self, ev):
        if ev.type() == QEvent.Type.FileOpen:
            path = ev.file() or ev.url().toLocalFile()
            if path:
                if self._ready:
                    self.fileOpenRequested.emit(path)
                else:
                    self.pending_files.append(path)
            return True
        return super().event(ev)

    def set_ready(self):
        self._ready = True
        for path in self.pending_files:
            self.fileOpenRequested.emit(path)
        self.pending_files.clear()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = FlightCardApplication(argv)
    # Nom d'organisation / d'application : détermine le dossier de données de l'OS
    QCoreApplication.setOrganizationName(__org_name__)
    QCoreApplication.setApplicationName(__app_name__)
    QCoreApplication.setApplicationVersion(__version__)
    if sys.platform.startswith("win"):
        app.setStyle("Fusion")

    store = SettingsStore()
    s = store.settings
    ui_lang = s.ui_language if s.ui_language in LANGUAGES else detect_system_language()
    print_lang = s.print_language if s.print_language in LANGUAGES else ui_lang
    s.ui_language, s.print_language = ui_lang, print_lang

    from .ui.main_window import MainWindow   # import tardif : QApplication doit exister
    lang = LanguageManager(ui_lang)
    window = MainWindow(store, lang, print_lang)
    window.show()

    # Ouverture différée (une fois la boucle d'événements lancée) pour que les
    # boîtes de dialogue éventuelles (choix de simulation) s'affichent correctement.
    app.fileOpenRequested.connect(lambda p: QTimer.singleShot(0, lambda: window.open_path(p)))
    # Fichier passé en argument (Windows / Linux, ou « open -a … fichier » sous macOS).
    # Les arguments « -psn_… » ajoutés par d'anciens macOS sont ignorés.
    for arg in argv[1:]:
        if not arg.startswith("-") and Path(arg).is_file():
            app.pending_files.append(arg)
            break
    QTimer.singleShot(0, app.set_ready)
    return app.exec()
