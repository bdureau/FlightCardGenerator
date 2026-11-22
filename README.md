# FlightCard Generator

Application de bureau (Python 3.10+ / PyQt6) qui génère, prévisualise et imprime une
**carte de vol** (format Rocketry France / Tripoli) à partir de simulations
**OpenRocket (`.ork`)** ou **RockSim (`.rkt`)**. Windows, macOS, Linux.

## Démarrage rapide

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate     macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
python main.py                      # ou : python main.py ma_fusee.ork
```

Des fichiers d'exemple sont fournis dans `samples/` (régénérables avec
`python tools/make_samples.py`).

## Fonctionnalités

- Import par glisser-déposer ou *Fichier › Ouvrir* : `.ork` (ZIP, GZIP ou XML brut), `.rkt`,
  et fiches `.xml` sauvegardées.
- Choix de la simulation quand le fichier en contient plusieurs (et *Choisir une autre
  simulation* ensuite, Ctrl+R).
- Extraction : nom, longueur, diamètre, masse au décollage, CG, CP, marge statique, moteurs
  (étages / cluster), impulsion, récupération, conditions, résultats, événements, avertissements,
  courbe altitude / vitesse.
- Tous les champs restent modifiables ; impulsion totale, Level, poussée moyenne, rapport
  poussée/poids et marge statique se recalculent tant qu'ils ne sont pas modifiés à la main.
- Profil pilote, historique des lieux et logo d'association sauvegardés dans le dossier de
  données standard de l'OS (`settings.json`).
- Interface FR / EN / ES / IT, détection de la langue système, changement à chaud ; langue
  d'impression indépendante.
- Aperçu en direct, aperçu avant impression, impression, export PDF ; page 1 = carte de vol,
  page 2 (optionnelle) = annexe détaillée avec graphique.
- Aide › Manuel utilisateur : ouvre le PDF de la langue active dans le lecteur PDF du système.

## Arborescence

```
flightcard_app/
├── main.py                     # lanceur
├── requirements.txt
├── README.md
├── flightcard/
│   ├── __init__.py / __main__.py / app.py
│   ├── core/                   # métier, sans interface
│   │   ├── models.py           # dataclasses issues du parsing
│   │   ├── card.py             # schéma des champs + modèle FlightCard
│   │   ├── mapping.py          # simulation → champs, calculs automatiques
│   │   └── rocketry.py         # classes d'impulsion, niveaux Tripoli, poussée/poids
│   ├── parsers/                # lecture .ork / .rkt
│   │   ├── xmlutil.py  openrocket.py  rocksim.py
│   ├── i18n/                   # catalog.py (FR/EN/ES/IT) + LanguageManager
│   ├── storage/                # paths.py, settings.py (JSON), card_xml.py (fiches XML)
│   ├── printing/renderer.py    # rendu QPainter : aperçu, impression, PDF
│   ├── ui/                     # main_window.py, field_editors.py, widgets.py
│   └── resources/
│       ├── manuals/manual_{fr,en,es,it}.pdf
│       └── icons/app.png
├── packaging/windows/
│   ├── build_windows.bat       # compilation .exe + zip portable + installateur
│   ├── FlightCard_win.spec     # spécification PyInstaller (icône, infos de version)
│   └── FlightCard.iss          # script de l'installateur Inno Setup
├── packaging/macos/
│   ├── build_macos.sh          # compilation .app + .dmg (signature, notarisation)
│   ├── FlightCard.spec         # spécification PyInstaller (Info.plist, types de fichiers)
│   └── entitlements.plist      # droits pour le hardened runtime
├── tools/
│   ├── build_resources.py      # régénère manuels PDF + icône
│   ├── manual_content.py       # texte des manuels
│   └── make_samples.py         # fichiers d'exemple
├── samples/                    # demo_phenix.ork, demo_vega.rkt
└── tests/test_core.py          # python -m unittest discover -s tests
```

## Notes techniques

- **OpenRocket** : la masse, le CG, le CP et la stabilité viennent des données de vol
  enregistrées (valeurs au décollage / à la sortie de rampe). Si le fichier a été enregistré
  sans données détaillées, l'application le signale et ces champs sont à saisir.
  L'impulsion totale est intégrée sur la courbe de poussée quand l'échantillonnage le permet.
- **RockSim** : format non documenté publiquement ; lecture tolérante (unités internes mm, g,
  mm/s). Vérifiez les valeurs importées.
- Les XML sont lus avec `defusedxml` (protection contre les entités malveillantes) et la
  taille décompressée des archives `.ork` est plafonnée.
- Chemins gérés via `pathlib` et `QStandardPaths` ; polices avec repli
  Arial → Helvetica → Liberation Sans → DejaVu Sans → Segoe UI.
- Ajouter une langue : ajouter une colonne à chaque entrée de `i18n/catalog.py` et le code
  dans `LANGUAGES` ; les tests signalent toute traduction manquante.

## Compilation macOS (.app + .dmg)

À exécuter **sur un Mac** (macOS 12 ou plus, Python 3.10+ de python.org ou Homebrew,
Command Line Tools : `xcode-select --install`) :

```bash
chmod +x packaging/macos/build_macos.sh
./packaging/macos/build_macos.sh                 # architecture du Mac, signature ad hoc
```

Résultat : `dist/FlightCard.app` et `dist/FlightCard-<version>-<arch>.dmg`.

| Option | Effet |
|---|---|
| `--arch arm64 \| x86_64 \| universal2` | architecture cible (universal2 : Python et Qt universels requis) |
| `--sign "Developer ID Application: Nom (TEAMID)"` | signature avec « hardened runtime » |
| `--notarize PROFIL` | notarisation Apple + agrafage du ticket (après `xcrun notarytool store-credentials PROFIL`) |
| `--no-dmg`, `--skip-tests`, `--clean`, `--python /chemin/python3` | variantes |

Le script crée son propre environnement virtuel (`packaging/macos/.venv-build`), lance les
tests, génère l'icône `.icns`, compile avec `packaging/macos/FlightCard.spec`, signe, vérifie
le bundle puis crée le DMG. Le bundle déclare les types `.ork`, `.rkt` et `.xml` : double-clic
ou « Ouvrir avec » dans le Finder ouvre directement le fichier dans l'application.

Sans certificat Apple, l'application se lance sur le Mac qui l'a compilée ; sur un autre Mac,
faire clic droit › Ouvrir la première fois (ou
`xattr -dr com.apple.quarantine /Applications/FlightCard.app`).

## Compilation Windows (.exe, portable, installateur)

Sur un PC Windows 10/11 avec Python 3.10+ **64 bits** (python.org, case « Add python.exe to
PATH » cochée), double-cliquer sur `packaging\windows\build_windows.bat`, ou :

```bat
packaging\windows\build_windows.bat            :: options : /clean /skiptests /noinstaller /nopause /python CHEMIN
```

Résultats dans `dist\` :

- `FlightCard\FlightCard.exe` : le programme (avec son dossier `_internal`) ;
- `FlightCard-<version>-win64-portable.zip` : version portable, à décompresser n'importe où ;
- `FlightCard-Setup-<version>-win64.exe` : installateur (menu Démarrer, icône de bureau,
  « Ouvrir avec » pour `.ork` / `.rkt`, désinstallation), si
  [Inno Setup 6](https://jrsoftware.org/isdl.php) est installé (`winget install JRSoftware.InnoSetup`).

Signature facultative : définir `FC_SIGN_PFX` et `FC_SIGN_PASS` (certificat `.pfx`, `signtool`
du Windows SDK). Sans signature, SmartScreen demande « Informations complémentaires ›
Exécuter quand même » au premier lancement.

## Exécutable Linux (optionnel)

```bash
pip install pyinstaller
pyinstaller --name FlightCard --windowed --add-data "flightcard/resources:flightcard/resources" main.py
```
