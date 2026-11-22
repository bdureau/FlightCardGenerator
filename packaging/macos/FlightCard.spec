# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller pour macOS (FlightCard.app).

Utilisée par build_macos.sh ; peut aussi être lancée directement :
    pyinstaller --noconfirm packaging/macos/FlightCard.spec

Variables d'environnement facultatives :
    FC_ARCH  : arm64 | x86_64 | universal2   (défaut : architecture de Python)
    FC_ICON  : chemin d'un fichier .icns
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
APP_NAME = "FlightCard"
DISPLAY_NAME = "FlightCard Generator"
BUNDLE_ID = "org.flightcard.generator"

with open(os.path.join(ROOT, "flightcard", "__init__.py"), encoding="utf-8") as fh:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read()).group(1)

ARCH = os.environ.get("FC_ARCH") or None
ICON = os.environ.get("FC_ICON") or os.path.join(SPECPATH, "build", f"{APP_NAME}.icns")
if not os.path.isfile(ICON):
    ICON = None

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "flightcard", "resources"), "flightcard/resources")],
    hiddenimports=["defusedxml", "defusedxml.ElementTree"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "_tkinter", "PyQt5", "PySide2", "PySide6", "IPython", "numpy",
              "matplotlib", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,                 # UPX casse la signature de code sous macOS
    console=False,
    argv_emulation=False,      # l'application gère elle-même QEvent.FileOpen
    target_arch=ARCH,
    codesign_identity=None,    # la signature est faite ensuite par build_macos.sh
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)


def _doc_type(name, uti, exts, role="Editor", rank="Owner"):
    return {
        "CFBundleTypeName": name,
        "CFBundleTypeRole": role,
        "LSHandlerRank": rank,
        "LSItemContentTypes": [uti],
        "CFBundleTypeExtensions": exts,
    }


def _imported_uti(uti, desc, ext, conforms):
    return {
        "UTTypeIdentifier": uti,
        "UTTypeDescription": desc,
        "UTTypeConformsTo": conforms,
        "UTTypeTagSpecification": {"public.filename-extension": [ext]},
    }


if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": DISPLAY_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "CFBundleDevelopmentRegion": "fr",
            "CFBundleLocalizations": ["fr", "en", "es", "it"],
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,      # mode sombre autorisé
            "NSHumanReadableCopyright": "FlightCard Generator",
            # Associations de fichiers : double-clic / « Ouvrir avec » dans le Finder
            "CFBundleDocumentTypes": [
                _doc_type("OpenRocket design", "org.flightcard.openrocket", ["ork"],
                          role="Viewer", rank="Alternate"),
                _doc_type("RockSim design", "org.flightcard.rocksim", ["rkt"],
                          role="Viewer", rank="Alternate"),
                _doc_type("Flight card (XML)", "public.xml", ["xml"], rank="Alternate"),
            ],
            "UTImportedTypeDeclarations": [
                _imported_uti("org.flightcard.openrocket", "OpenRocket design", "ork",
                              ["public.data", "public.archive"]),
                _imported_uti("org.flightcard.rocksim", "RockSim design", "rkt",
                              ["public.xml"]),
            ],
        },
    )
