; LastfmPresence - Inno Setup Installer Script
; Compile with: iscc installer.iss
; Requires Inno Setup 6.2+ / Inno Setup 7+

#define AppName "LastfmPresence"
#define AppVersion "1.0.1"
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
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=true
OutputDir=dist
OutputBaseFilename={#AppName}_Setup_v{#AppVersion}_x64
SetupIconFile=src/presentation/gui/assets/icon.ico
Compression=lzma2/ultra64
SolidCompression=true
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
AppMutex=Global\LastfmPresence_SingleInstance_Mutex_Guid_1029
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.StartupTask=Iniciar automáticamente al encender Windows
english.StartupTask=Start automatically with Windows

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "{cm:StartupTask}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Comment: "Last.fm to Discord Rich Presence"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Comment: "Last.fm to Discord Rich Presence"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#AppName}"; ValueType: string; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName,'&','&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('cmd.exe', '/c taskkill /f /im LastfmPresence.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;