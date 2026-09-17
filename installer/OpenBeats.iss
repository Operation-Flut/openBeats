#define MyAppName "OpenBeats"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "OpenBeats contributors"
#define MyAppExeName "OpenBeats.exe"

[Setup]
AppId={{A97D542D-18B7-4ED1-961E-70B17B384DBA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\OpenBeats
DefaultGroupName=OpenBeats
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=OpenBeatsSetup-{#MyAppVersion}-dev-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=OpenBeats
LicenseFile=..\LICENSE
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{localappdata}\OpenBeats\Exchange"; Flags: uninsneveruninstall
Name: "{localappdata}\OpenBeats\Sessions"; Flags: uninsneveruninstall

[Files]
Source: "..\dist\OpenBeats\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\resolve\OpenBeats.lua"; DestDir: "{userappdata}\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"; Flags: ignoreversion
Source: "..\resolve\OpenBeats.lua"; DestDir: "{userappdata}\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "OpenBeats Agent"; ValueData: """{app}\{#MyAppExeName}"" --agent"; Flags: uninsdeletevalue

[Icons]
Name: "{group}\Uninstall OpenBeats"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--agent"; Flags: nowait runhidden skipifsilent

[UninstallDelete]
Type: files; Name: "{userappdata}\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\OpenBeats.lua"
Type: files; Name: "{userappdata}\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility\OpenBeats.lua"

[Code]
function InitializeSetup(): Boolean;
var
  ResolveExe: String;
begin
  ResolveExe := ExpandConstant('{pf}\Blackmagic Design\DaVinci Resolve\Resolve.exe');
  Result := True;
  if not FileExists(ResolveExe) then
    MsgBox(
      'DaVinci Resolve 21.1 or newer was not found. OpenBeats can still be installed, but its Resolve script cannot be used until Resolve is installed.',
      mbInformation,
      MB_OK
    );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    MsgBox(
      'OpenBeats is installed for DaVinci Resolve Free and Studio.' + #13#10 + #13#10 +
      'Fully quit and restart DaVinci Resolve so Workspace > Scripts is refreshed.' + #13#10 + #13#10 +
      'Then use Workspace > Scripts > OpenBeats, choose an audio track, and generate beat markers.',
      mbInformation,
      MB_OK
    );
end;
