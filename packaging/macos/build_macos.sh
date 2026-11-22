#!/usr/bin/env bash
# =============================================================================
#  build_macos.sh — compile FlightCard Generator en application macOS (.app + .dmg)
#
#  Usage :  ./packaging/macos/build_macos.sh [options]
#
#  Options :
#    --arch ARCH        native (défaut) | arm64 | x86_64 | universal2
#    --python PATH      interpréteur Python à utiliser (défaut : python3, ≥ 3.10)
#    --sign "IDENTITÉ"  signe avec un certificat « Developer ID Application: … »
#                       (sans cette option : signature ad hoc, usage local)
#    --notarize PROFIL  notarise le DMG (profil créé par « xcrun notarytool
#                       store-credentials PROFIL … ») ; nécessite --sign
#    --no-dmg           ne crée que le .app
#    --skip-tests       ne lance pas les tests unitaires avant la compilation
#    --clean            recrée l'environnement virtuel et supprime build/ et dist/
#    -h, --help         affiche cette aide
#
#  Résultat : dist/FlightCard.app  et  dist/FlightCard-<version>-<arch>.dmg
#  Compatible avec le bash 3.2 fourni par macOS.
# =============================================================================
set -euo pipefail

# ----------------------------------------------------------------- utilitaires
if [ -t 1 ]; then
    B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
else
    B=""; G=""; Y=""; R=""; N=""
fi
step() { printf '\n%s==> %s%s\n' "$B" "$*" "$N"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '%s[!] %s%s\n' "$Y" "$*" "$N" >&2; }
die()  { printf '%s[x] %s%s\n' "$R" "$*" "$N" >&2; exit 1; }
usage() { sed -n '3,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

# ----------------------------------------------------------------- arguments
ARCH="native"
PYTHON_BIN="${PYTHON:-python3}"
SIGN_ID=""
NOTARY_PROFILE=""
MAKE_DMG=1
RUN_TESTS=1
CLEAN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --arch)       ARCH="${2:?--arch attend une valeur}"; shift 2 ;;
        --python)     PYTHON_BIN="${2:?--python attend un chemin}"; shift 2 ;;
        --sign)       SIGN_ID="${2:?--sign attend une identité}"; shift 2 ;;
        --notarize)   NOTARY_PROFILE="${2:?--notarize attend un profil}"; shift 2 ;;
        --no-dmg)     MAKE_DMG=0; shift ;;
        --skip-tests) RUN_TESTS=0; shift ;;
        --clean)      CLEAN=1; shift ;;
        -h|--help)    usage ;;
        *)            die "Option inconnue : $1 (voir --help)" ;;
    esac
done

case "$ARCH" in native|arm64|x86_64|universal2) ;; *) die "Architecture invalide : $ARCH" ;; esac
[ -n "$NOTARY_PROFILE" ] && [ -z "$SIGN_ID" ] && die "--notarize nécessite --sign \"Developer ID Application: …\""

[ "$(uname -s)" = "Darwin" ] || die "Ce script doit être exécuté sous macOS."
for tool in sips iconutil codesign hdiutil ditto; do
    command -v "$tool" >/dev/null 2>&1 || die "Outil macOS introuvable : $tool (installez les Command Line Tools : xcode-select --install)"
done

# ----------------------------------------------------------------- chemins
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"          # fichiers intermédiaires (icns, PyInstaller)
VENV="$SCRIPT_DIR/.venv-build"
DIST="$ROOT/dist"
APP_NAME="FlightCard"
APP="$DIST/$APP_NAME.app"
SPEC="$SCRIPT_DIR/FlightCard.spec"
ENTITLEMENTS="$SCRIPT_DIR/entitlements.plist"
ICON_PNG="$ROOT/flightcard/resources/icons/app.png"
ICNS="$BUILD_DIR/$APP_NAME.icns"

cd "$ROOT"
VERSION="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' flightcard/__init__.py)"
[ -n "$VERSION" ] || die "Version introuvable dans flightcard/__init__.py"

if [ "$ARCH" = "native" ]; then
    TARGET_ARCH="$(uname -m)"
else
    TARGET_ARCH="$ARCH"
fi
printf '%sFlightCard Generator %s — build macOS (%s)%s\n' "$B" "$VERSION" "$TARGET_ARCH" "$N"

# ----------------------------------------------------------------- 1. Python
step "Vérification de Python"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python introuvable : $PYTHON_BIN (installez-le depuis python.org ou Homebrew)"
"$PYTHON_BIN" - <<'PY' || die "Python 3.10 ou plus récent est requis."
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
PY_EXE="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
PY_ARCHS="$(lipo -archs "$PY_EXE" 2>/dev/null || uname -m)"
info "$("$PYTHON_BIN" --version) — $PY_EXE ($PY_ARCHS)"

if [ "$ARCH" = "universal2" ]; then
    case "$PY_ARCHS" in *x86_64*arm64*|*arm64*x86_64*) ;;
        *) die "universal2 exige un Python « universal2 » (installeur python.org). Python actuel : $PY_ARCHS" ;;
    esac
elif [ "$TARGET_ARCH" != "$(uname -m)" ]; then
    case "$PY_ARCHS" in *"$TARGET_ARCH"*) ;;
        *) die "Ce Python ne contient pas l'architecture $TARGET_ARCH ($PY_ARCHS)." ;;
    esac
    warn "Compilation croisée $TARGET_ARCH : les dépendances doivent aussi exister pour cette architecture."
fi

# ----------------------------------------------------------------- 2. venv
step "Environnement virtuel de compilation"
if [ "$CLEAN" -eq 1 ]; then
    info "Nettoyage (--clean)"
    rm -rf "$VENV" "$BUILD_DIR" "$DIST"
fi
if [ ! -x "$VENV/bin/python" ]; then
    info "Création de $VENV"
    "$PYTHON_BIN" -m venv "$VENV"
fi
VPY="$VENV/bin/python"
"$VPY" -m pip install --quiet --upgrade pip wheel
"$VPY" -m pip install --quiet -r "$ROOT/requirements.txt" "pyinstaller>=6.3"
info "PyQt6 $("$VPY" -c 'from PyQt6.QtCore import PYQT_VERSION_STR as v; print(v)') — PyInstaller $("$VPY" -m PyInstaller --version)"

if [ "$ARCH" = "universal2" ]; then
    QTCORE="$("$VPY" -c 'import os, PyQt6; p = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "lib", "QtCore.framework", "QtCore"); print(p if os.path.exists(p) else "")')"
    if [ -n "$QTCORE" ]; then
        QT_ARCHS="$(lipo -archs "$QTCORE")"
        case "$QT_ARCHS" in *x86_64*arm64*|*arm64*x86_64*) ;;
            *) die "Les bibliothèques Qt installées ne sont pas universal2 ($QT_ARCHS). Compilez séparément avec --arch arm64 sur un Mac Apple Silicon et --arch x86_64 sur un Mac Intel." ;;
        esac
    fi
fi

# ----------------------------------------------------------------- 3. tests
if [ "$RUN_TESTS" -eq 1 ]; then
    step "Tests unitaires"
    QT_QPA_PLATFORM=offscreen "$VPY" -m unittest discover -s tests -q \
        || die "Des tests échouent : compilation annulée (--skip-tests pour forcer)."
fi

# ----------------------------------------------------------------- 4. ressources
step "Ressources (manuels PDF, icône)"
missing=0
for lang in fr en es it; do
    [ -f "$ROOT/flightcard/resources/manuals/manual_$lang.pdf" ] || missing=1
done
if [ "$missing" -eq 1 ] || [ ! -f "$ICON_PNG" ]; then
    info "Génération des ressources manquantes"
    QT_QPA_PLATFORM=offscreen "$VPY" "$ROOT/tools/build_resources.py"
fi

mkdir -p "$BUILD_DIR"
ICONSET="$BUILD_DIR/$APP_NAME.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
    double=$((size * 2))
    sips -z "$size" "$size" "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    sips -z "$double" "$double" "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"
rm -rf "$ICONSET"
info "Icône : $ICNS"

# ----------------------------------------------------------------- 5. PyInstaller
step "Compilation PyInstaller"
rm -rf "$APP" "${DIST:?}/${APP_NAME:?}"
PYI_ARCH=""
[ "$ARCH" != "native" ] && PYI_ARCH="$ARCH"
FC_ARCH="$PYI_ARCH" FC_ICON="$ICNS" "$VPY" -m PyInstaller \
    --noconfirm --clean \
    --distpath "$DIST" \
    --workpath "$BUILD_DIR/pyinstaller" \
    "$SPEC"
[ -d "$APP" ] || die "Le bundle $APP n'a pas été produit."
rm -rf "${DIST:?}/${APP_NAME:?}"                   # dossier « onedir » intermédiaire
xattr -cr "$APP" 2>/dev/null || true         # attributs étendus gênant la signature

# ----------------------------------------------------------------- 6. signature
step "Signature du code"
if [ -n "$SIGN_ID" ]; then
    info "Identité : $SIGN_ID (hardened runtime)"
    codesign --force --deep --timestamp --options runtime \
        --entitlements "$ENTITLEMENTS" --sign "$SIGN_ID" "$APP"
else
    info "Signature ad hoc (application utilisable sur ce Mac ; voir la note Gatekeeper ci-dessous)"
    codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict "$APP" || die "La vérification de la signature a échoué."

# ----------------------------------------------------------------- 7. contrôle rapide
step "Contrôle du bundle"
BIN="$APP/Contents/MacOS/$APP_NAME"
info "Architecture(s) : $(lipo -archs "$BIN")"
RES_MANUAL="$(find "$APP/Contents" -name 'manual_fr.pdf' -print -quit)"
[ -n "$RES_MANUAL" ] || die "Manuels absents du bundle."
info "Ressources : OK"
info "Taille : $(du -sh "$APP" | cut -f1)"

# ----------------------------------------------------------------- 8. DMG
DMG=""
if [ "$MAKE_DMG" -eq 1 ]; then
    step "Création de l'image disque"
    DMG="$DIST/$APP_NAME-$VERSION-$TARGET_ARCH.dmg"
    STAGE="$BUILD_DIR/dmg"
    rm -rf "$STAGE" "$DMG"
    mkdir -p "$STAGE"
    ditto "$APP" "$STAGE/$APP_NAME.app"
    ln -s /Applications "$STAGE/Applications"
    hdiutil create -volname "FlightCard Generator $VERSION" -srcfolder "$STAGE" \
        -fs HFS+ -format UDZO -ov "$DMG" >/dev/null
    rm -rf "$STAGE"
    if [ -n "$SIGN_ID" ]; then
        codesign --force --timestamp --sign "$SIGN_ID" "$DMG"
    fi
    info "$DMG ($(du -h "$DMG" | cut -f1))"
fi

# ----------------------------------------------------------------- 9. notarisation
if [ -n "$NOTARY_PROFILE" ]; then
    step "Notarisation Apple"
    TARGET="$DMG"
    if [ -z "$TARGET" ]; then
        TARGET="$BUILD_DIR/$APP_NAME-notarize.zip"
        ditto -c -k --keepParent "$APP" "$TARGET"
    fi
    xcrun notarytool submit "$TARGET" --keychain-profile "$NOTARY_PROFILE" --wait
    xcrun stapler staple "$APP"
    [ -n "$DMG" ] && xcrun stapler staple "$DMG"
    spctl --assess --type execute --verbose "$APP" || warn "spctl n'a pas validé l'application."
fi

# ----------------------------------------------------------------- résumé
printf '\n%s✔ Compilation terminée%s\n' "$G" "$N"
info "Application : $APP"
[ -n "$DMG" ] && info "Image disque : $DMG"
info "Lancer :      open \"$APP\""
if [ -z "$SIGN_ID" ]; then
    cat <<EOF

${Y}Note Gatekeeper${N} — l'application n'est pas signée avec un certificat Apple :
  • sur ce Mac elle se lance directement ;
  • sur un autre Mac, faites clic droit › Ouvrir la première fois
    (ou Réglages Système › Confidentialité et sécurité › « Ouvrir quand même »),
    ou retirez la quarantaine :  xattr -dr com.apple.quarantine /Applications/$APP_NAME.app
  • pour une distribution publique : --sign "Developer ID Application: …" --notarize PROFIL
EOF
fi
