; LastfmPresence - Inno Setup Installer Script
; Compile with: iscc installer.iss
; Requires Inno Setup 6.2+

#define AppName "LastfmPresence"
#define AppVersion "1.0.0"
#define AppPublisher "dygeraldino"
#define AppURL "https://github.com/dygeraldino/lastfm-discord-rpc"
#define AppExeName "LastfmPresence.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={userappdata}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=true
OutputDir=dist
OutputBaseFilename={#AppName}_Setup_{#AppVersion}
SetupIconFile=src/presentation/gui/assets/icon.ico
Compression=lzma/ultra
SolidCompression=true
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Comment: "Last.fm to Discord Rich Presence"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: startup; IconFilename: "{app}\{#AppExeName}"

[Tasks]
Name: "startup"; Description: "{cm:CreateDesktopIcon} Iniciar automáticamente con Windows"; GroupDescription: "Opciones adicionales:"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#AppName}"; ValueType: string; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName,&,'&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\{#AppName}"

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.CreateDesktopIcon=Iniciar al encender Windows
english.CreateDesktopIcon=Start with Windows