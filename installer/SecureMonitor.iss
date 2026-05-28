; Inno Setup script — build with: iscc SecureMonitor.iss
; Requires PyInstaller output: ..\secure_monitor_daemon\dist\SecureMonitor.exe

#define MyAppName "Secure Monitor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Secure Monitor"
#define MyAppExeName "SecureMonitor.exe"

[Setup]
AppId={{A7B3C9E1-5F24-4D8A-9C2E-1B4F6A8D0E3C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=DISCLAIMER.txt
; User must accept disclaimer (I Agree) or setup exits (I Do Not Accept)
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=SecureMonitor-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\secure_monitor_daemon\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "DISCLAIMER.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\Fix-SecurityLog-Admin.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\Fix-SecurityLog-Admin.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Fix Security Log (Admin)"; Filename: "{app}\scripts\Fix-SecurityLog-Admin.bat"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
