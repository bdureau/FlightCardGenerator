@echo off
rem ============================================================================
rem  build_windows.bat - compile FlightCard Generator pour Windows
rem
rem  Utilisation : double-cliquer sur ce fichier, ou dans une invite de commandes :
rem      packaging\windows\build_windows.bat [options]
rem
rem  Options :
rem      /clean         recree l'environnement de compilation et efface build et dist
rem      /skiptests     ne lance pas les tests automatiques
rem      /noinstaller   ne cree pas l'installateur Setup.exe (meme si Inno Setup est present)
rem      /nopause       ne pas attendre une touche a la fin (usage en script)
rem      /python CHEMIN utiliser ce python.exe (sinon : lanceur "py", puis "python")
rem      /?             affiche cette aide
rem
rem  Resultats dans le dossier dist :
rem      dist\FlightCard\FlightCard.exe                  programme
rem      dist\FlightCard-VERSION-win64-portable.zip      version portable, sans installation
rem      dist\FlightCard-Setup-VERSION-win64.exe         installateur, si Inno Setup 6 est installe
rem
rem  Signature facultative : definir FC_SIGN_PFX (certificat .pfx) et FC_SIGN_PASS
rem  avant de lancer le script ; signtool.exe (Windows SDK) doit etre disponible.
rem ============================================================================
setlocal EnableExtensions
title FlightCard Generator - compilation Windows

set "OPT_CLEAN=0"
set "OPT_TESTS=1"
set "OPT_INSTALLER=1"
set "OPT_PAUSE=1"
set "PYEXE="

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="/clean"       (set "OPT_CLEAN=1"     & shift & goto :parse_args)
if /i "%~1"=="/skiptests"   (set "OPT_TESTS=0"     & shift & goto :parse_args)
if /i "%~1"=="/noinstaller" (set "OPT_INSTALLER=0" & shift & goto :parse_args)
if /i "%~1"=="/nopause"     (set "OPT_PAUSE=0"     & shift & goto :parse_args)
if /i "%~1"=="/python"      (set PYEXE="%~2"       & shift & shift & goto :parse_args)
if "%~1"=="/?" goto :usage
if /i "%~1"=="/h" goto :usage
echo Option inconnue : %~1
goto :usage

:args_done
rem ---------------------------------------------------------------- chemins
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\.." || (set "MSG=Dossier du projet introuvable." & goto :fail)
set "ROOT=%CD%"
set "VENV=%SCRIPT_DIR%.venv-build"
set "BUILD=%SCRIPT_DIR%build"
set "DIST=%ROOT%\dist"
set "SPEC=%SCRIPT_DIR%FlightCard_win.spec"
set "ISS=%SCRIPT_DIR%FlightCard.iss"
set "ICO=%BUILD%\FlightCard.ico"
set "VPY=%VENV%\Scripts\python.exe"

if not exist "%ROOT%\main.py" (set "MSG=main.py introuvable : ce script doit rester dans packaging\windows du projet." & goto :fail)

echo.
echo ============================================================
echo   FlightCard Generator - compilation Windows
echo   Projet : %ROOT%
echo ============================================================

rem ---------------------------------------------------------------- 1. Python
call :step "1/7  Recherche de Python 3.10 ou plus recent"
if defined PYEXE goto :check_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (set "PYEXE=py -3" & goto :check_python)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (set "PYEXE=python" & goto :check_python)
set "MSG=Python 3.10 ou plus recent est introuvable. Installez-le depuis https://www.python.org/downloads/windows/ en cochant la case 'Add python.exe to PATH', puis relancez ce script."
goto :fail

:check_python
%PYEXE% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (set "MSG=Le Python indique n'est pas utilisable ou est plus ancien que 3.10." & goto :fail)
%PYEXE% -c "import struct, sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
if errorlevel 1 (set "MSG=Ce Python est en 32 bits. PyQt6 exige Python 64 bits : installez la version 'Windows installer 64-bit' depuis python.org." & goto :fail)
set "PYVER="
%PYEXE% -c "import sys; print(sys.version.split()[0])" > "%TEMP%\fc_pyver.txt" 2>nul
set /p PYVER=<"%TEMP%\fc_pyver.txt"
del /q "%TEMP%\fc_pyver.txt" 2>nul
echo     Python %PYVER% trouve [%PYEXE%]

rem ---------------------------------------------------------------- 2. environnement
call :step "2/7  Preparation de l'environnement de compilation"
if "%OPT_CLEAN%"=="1" (
    echo     Nettoyage demande : suppression des anciens fichiers
    if exist "%VENV%" rmdir /s /q "%VENV%"
    if exist "%BUILD%" rmdir /s /q "%BUILD%"
    if exist "%DIST%" rmdir /s /q "%DIST%"
)
if not exist "%BUILD%" mkdir "%BUILD%"
if exist "%VPY%" goto :venv_ready
echo     Creation de l'environnement virtuel
%PYEXE% -m venv "%VENV%"
if errorlevel 1 (set "MSG=Impossible de creer l'environnement virtuel Python." & goto :fail)
:venv_ready
echo     Installation des composants - quelques minutes la premiere fois...
"%VPY%" -m pip install --quiet --disable-pip-version-check --upgrade pip wheel
if errorlevel 1 (set "MSG=Echec de la mise a jour de pip. Verifiez la connexion Internet." & goto :fail)
"%VPY%" -m pip install --quiet --disable-pip-version-check -r "%ROOT%\requirements.txt" "pyinstaller>=6.3" "pillow>=10"
if errorlevel 1 (set "MSG=Echec de l'installation de PyQt6 / PyInstaller. Verifiez la connexion Internet, ou relancez avec /clean." & goto :fail)

set "VERSION="
"%VPY%" -c "import flightcard; print(flightcard.__version__)" > "%BUILD%\version.txt" 2>nul
set /p VERSION=<"%BUILD%\version.txt"
if not defined VERSION (set "MSG=Version introuvable dans flightcard\__init__.py." & goto :fail)
echo     Version de FlightCard : %VERSION%

rem ---------------------------------------------------------------- 3. tests
call :step "3/7  Tests automatiques"
if "%OPT_TESTS%"=="0" (echo     Ignores - option /skiptests & goto :tests_done)
set "QT_QPA_PLATFORM=offscreen"
"%VPY%" -m unittest discover -s tests -q
if errorlevel 1 (set "QT_QPA_PLATFORM=" & set "MSG=Des tests echouent : compilation annulee. Relancez avec /skiptests pour forcer." & goto :fail)
set "QT_QPA_PLATFORM="
:tests_done

rem ---------------------------------------------------------------- 4. ressources
call :step "4/7  Ressources : manuels PDF et icone"
set "NEED_RES=0"
for %%L in (fr en es it) do if not exist "%ROOT%\flightcard\resources\manuals\manual_%%L.pdf" set "NEED_RES=1"
if not exist "%ROOT%\flightcard\resources\icons\app.png" set "NEED_RES=1"
if "%NEED_RES%"=="0" goto :res_ok
echo     Generation des ressources manquantes
set "QT_QPA_PLATFORM=offscreen"
"%VPY%" "%ROOT%\tools\build_resources.py"
set "RES_ERR=%ERRORLEVEL%"
set "QT_QPA_PLATFORM="
if not "%RES_ERR%"=="0" (set "MSG=Echec de la generation des manuels et de l'icone." & goto :fail)
:res_ok
"%VPY%" -c "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2], sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])" "%ROOT%\flightcard\resources\icons\app.png" "%ICO%"
if errorlevel 1 (set "MSG=Impossible de creer l'icone .ico." & goto :fail)
echo     Icone : %ICO%

rem ---------------------------------------------------------------- 5. PyInstaller
call :step "5/7  Compilation de FlightCard.exe - quelques minutes"
if exist "%DIST%\FlightCard" rmdir /s /q "%DIST%\FlightCard"
if exist "%DIST%\FlightCard" (set "MSG=Le dossier dist\FlightCard est verrouille : fermez FlightCard s'il est ouvert, puis relancez." & goto :fail)
set "FC_ICON=%ICO%"
"%VPY%" -m PyInstaller --noconfirm --clean --log-level WARN --distpath "%DIST%" --workpath "%BUILD%\pyinstaller" "%SPEC%"
if errorlevel 1 (set "MSG=La compilation PyInstaller a echoue : voir les messages ci-dessus." & goto :fail)
if not exist "%DIST%\FlightCard\FlightCard.exe" (set "MSG=FlightCard.exe n'a pas ete produit." & goto :fail)
if not exist "%DIST%\FlightCard\_internal\flightcard\resources\manuals\manual_fr.pdf" (set "MSG=Les manuels sont absents du programme compile." & goto :fail)
echo     Programme : %DIST%\FlightCard\FlightCard.exe

rem ---------------------------------------------------------------- 6. signature
call :step "6/7  Signature du code"
if not defined FC_SIGN_PFX (echo     Pas de certificat - FC_SIGN_PFX non defini : etape ignoree & goto :sign_done)
set "SIGNTOOL="
for /f "delims=" %%i in ('where signtool 2^>nul') do if not defined SIGNTOOL set "SIGNTOOL=%%i"
if not defined SIGNTOOL (echo     [!] signtool.exe introuvable : installez le Windows SDK. Etape ignoree. & goto :sign_done)
"%SIGNTOOL%" sign /f "%FC_SIGN_PFX%" /p "%FC_SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%DIST%\FlightCard\FlightCard.exe"
if errorlevel 1 (set "MSG=La signature de FlightCard.exe a echoue." & goto :fail)
:sign_done

rem ---------------------------------------------------------------- 7. paquets
call :step "7/7  Version portable et installateur"
set "ZIP=%DIST%\FlightCard-%VERSION%-win64-portable.zip"
if exist "%ZIP%" del /q "%ZIP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path (Join-Path $env:DIST 'FlightCard') -DestinationPath $env:ZIP -Force"
if errorlevel 1 (echo     [!] Impossible de creer le zip portable - le programme reste utilisable dans dist\FlightCard) else (echo     Portable : %ZIP%)

set "SETUP="
if "%OPT_INSTALLER%"=="0" (echo     Installateur ignore - option /noinstaller & goto :pack_done)
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%i in ('where iscc 2^>nul') do if not defined ISCC set "ISCC=%%i"
if not defined ISCC goto :no_inno
"%ISCC%" /Q "/DMyAppVersion=%VERSION%" "/DSourceDir=%DIST%\FlightCard" "/DOutputDir=%DIST%" "/DIconFile=%ICO%" "%ISS%"
if errorlevel 1 (set "MSG=La creation de l'installateur Inno Setup a echoue." & goto :fail)
set "SETUP=%DIST%\FlightCard-Setup-%VERSION%-win64.exe"
if defined FC_SIGN_PFX if defined SIGNTOOL "%SIGNTOOL%" sign /f "%FC_SIGN_PFX%" /p "%FC_SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%SETUP%"
echo     Installateur : %SETUP%
goto :pack_done
:no_inno
echo     Inno Setup 6 non trouve : pas d'installateur Setup.exe.
echo     Pour l'obtenir, installez Inno Setup depuis https://jrsoftware.org/isdl.php
echo     ou avec : winget install JRSoftware.InnoSetup  - puis relancez ce script.
:pack_done

rem ---------------------------------------------------------------- resume
echo.
echo ============================================================
echo   COMPILATION TERMINEE
echo ============================================================
echo   Programme    : %DIST%\FlightCard\FlightCard.exe
echo   Portable     : %ZIP%
if defined SETUP echo   Installateur : %SETUP%
echo.
echo   Au premier lancement sur un autre PC, Windows SmartScreen peut afficher
echo   "Windows a protege votre ordinateur" : cliquez sur "Informations
echo   complementaires" puis "Executer quand meme". C'est normal pour un
echo   programme qui n'est pas signe par un certificat commercial.
echo.
popd
if "%OPT_PAUSE%"=="1" (start "" explorer "%DIST%" & pause)
endlocal
exit /b 0

rem ---------------------------------------------------------------- sous-routines
:step
echo.
echo ==^> %~1
goto :eof

:fail
echo.
echo ************************************************************
echo   ERREUR : %MSG%
echo ************************************************************
echo.
popd 2>nul
if "%OPT_PAUSE%"=="1" pause
endlocal
exit /b 1

:usage
echo.
echo Utilisation : build_windows.bat [/clean] [/skiptests] [/noinstaller] [/nopause] [/python CHEMIN]
echo.
echo   /clean         recree l'environnement de compilation et efface build et dist
echo   /skiptests     ne lance pas les tests automatiques
echo   /noinstaller   ne cree pas l'installateur Setup.exe
echo   /nopause       ne pas attendre une touche a la fin
echo   /python CHEMIN utiliser ce python.exe
echo.
endlocal
exit /b 2
