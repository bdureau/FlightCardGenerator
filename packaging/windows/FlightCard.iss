; =============================================================================
;  Script Inno Setup 6 — installateur Windows de FlightCard Generator
;  Compilé automatiquement par build_windows.bat si Inno Setup est installé
;  (https://jrsoftware.org/isinfo.php). Compilation manuelle :
;    ISCC.exe /DMyAppVersion=1.0.0 /DSourceDir=..\..\dist\FlightCard /DOutputDir=..\..\dist FlightCard.iss
; =============================================================================

#define MyAppName "FlightCard Generator"
#define MyAppExe "FlightCard.exe"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\FlightCard"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif
#ifndef IconFile
  #define IconFile "build\FlightCard.ico"
#endif

[Setup]
AppId={{6F2B8F1E-3C4A-4E7B-9D21-5A0C8E4F7B13}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=FlightCard
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=FlightCard-Setup-{#MyAppVersion}-win64
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Installation sans droits administrateur par défaut (l'utilisateur peut choisir « pour tous »)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
MinVersion=10.0

[Languages]
Name: "french";  MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[CustomMessages]
french.AssocTask=Proposer FlightCard pour ouvrir les fichiers .ork et .rkt
english.AssocTask=Offer FlightCard to open .ork and .rkt files
spanish.AssocTask=Proponer FlightCard para abrir los archivos .ork y .rkt
italian.AssocTask=Proporre FlightCard per aprire i file .ork e .rkt

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocTask}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; « Ouvrir avec » : FlightCard est proposé sans remplacer OpenRocket / RockSim comme programme par défaut
Root: HKA; Subkey: "Software\Classes\.ork\OpenWithProgids"; ValueType: string; ValueName: "FlightCard.ork"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightCard.ork"; ValueType: string; ValueName: ""; ValueData: "OpenRocket design"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightCard.ork\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightCard.ork\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.rkt\OpenWithProgids"; ValueType: string; ValueName: "FlightCard.rkt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightCard.rkt"; ValueType: string; ValueName: ""; ValueData: "RockSim design"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightCard.rkt\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightCard.rkt\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".ork"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".rkt"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".xml"; ValueData: ""

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
