; Inno Setup script - builds RVTripVisualizer-Setup.exe from the PyInstaller
; onedir build at dist\RVTripVisualizer (run `pyinstaller packaging\pyinstaller.spec`
; from the repo root first). Build with: iscc packaging\windows\setup.iss

#define MyAppName "RV Trip Visualizer"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "RV Trip Visualizer"
#define MyAppExeName "RVTripVisualizer.exe"

[Setup]
AppId={{B6C1F2B0-6C2E-4C1A-9F3E-7B7D4B6B9A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\..\dist\installer
OutputBaseFilename=RVTripVisualizer-Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=..\icons\icon.ico
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\RVTripVisualizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
