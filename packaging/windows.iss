; Inno Setup script. Build with:  iscc /DAppVersion=0.1.0 packaging\windows.iss
; Expects the PyInstaller output in dist\ScreenCapture\ (see packaging\build_windows.ps1).
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{7B1D9C3E-4A56-4F0B-9E2D-5C8A1F3B6D70}
AppName=ScreenCapture
AppVersion={#AppVersion}
AppPublisher=Janusz Tylek
AppPublisherURL=https://github.com/jtylek/ScreenCapture
AppSupportURL=https://github.com/jtylek/ScreenCapture
AppUpdatesURL=https://github.com/jtylek/ScreenCapture/releases
DefaultDirName={autopf}\ScreenCapture
DefaultGroupName=ScreenCapture
UninstallDisplayIcon={app}\ScreenCapture.exe
SetupIconFile=screencapture.ico
OutputDir=..\dist
OutputBaseFilename=ScreenCapture-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start ScreenCapture when I sign in (tray icon)"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\ScreenCapture\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\ScreenCapture"; Filename: "{app}\ScreenCapture.exe"; Parameters: "--library"
Name: "{group}\Capture region"; Filename: "{app}\ScreenCapture.exe"; Parameters: "--capture"
Name: "{group}\Uninstall ScreenCapture"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ScreenCapture"; Filename: "{app}\ScreenCapture.exe"; Parameters: "--library"; Tasks: desktopicon

[Registry]
; same value the in-app Settings checkbox manages
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ScreenCapture"; ValueData: """{app}\ScreenCapture.exe"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\ScreenCapture.exe"; Parameters: "--library"; Description: "Launch ScreenCapture"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\ScreenCapture.exe"; Parameters: "--quit"; Flags: runhidden; RunOnceId: "StopScreenCapture"
