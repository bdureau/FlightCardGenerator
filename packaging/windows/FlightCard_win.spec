# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller pour Windows (dossier dist\\FlightCard\\FlightCard.exe).

Utilisée par build_windows.bat ; peut aussi être lancée directement :
    pyinstaller --noconfirm packaging\\windows\\FlightCard_win.spec

Variable d'environnement facultative :
    FC_ICON : chemin d'un fichier .ico (sinon le PNG de l'application, converti par Pillow)
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
APP_NAME = "FlightCard"

with open(os.path.join(ROOT, "flightcard", "__init__.py"), encoding="utf-8") as fh:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read()).group(1)

ICON = os.environ.get("FC_ICON") or os.path.join(ROOT, "flightcard", "resources", "icons", "app.png")
if not os.path.isfile(ICON):
    ICON = None

# --- Informations de version affichées dans Propriétés › Détails de l'exécutable
VERSION_INFO = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct,
                                                     StringTable, VarFileInfo, VarStruct,
                                                     VSVersionInfo)
    nums = tuple((list(map(int, re.findall(r"\d+", VERSION))) + [0, 0, 0, 0])[:4])
    VERSION_INFO = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums, mask=0x3F, flags=0x0, OS=0x40004,
                          fileType=0x1, subtype=0x0, date=(0, 0)),
        kids=[
            StringFileInfo([StringTable("040C04B0", [
                StringStruct("CompanyName", "FlightCard"),
                StringStruct("FileDescription", "FlightCard Generator — fiches de vol"),
                StringStruct("FileVersion", VERSION),
                StringStruct("InternalName", APP_NAME),
                StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                StringStruct("ProductName", "FlightCard Generator"),
                StringStruct("ProductVersion", VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
        ],
    )

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
    exclude_binaries=True,          # mode « dossier » : démarrage rapide, moins de faux positifs antivirus
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,                  # pas de fenêtre de console noire
    icon=ICON,
    version=VERSION_INFO,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
