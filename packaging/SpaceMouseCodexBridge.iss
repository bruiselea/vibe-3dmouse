#define MyAppName "Vibe SpaceMouse Bridge for Codex"
#define MyAppVersion "0.1.0-beta.2"
#define MyAppExeName "VibeSpaceMouseBridgeForCodex.exe"

[Setup]
AppId={{65F015A2-15CB-4AC0-BE98-44CF9296F3B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Vibe SpaceMouse Community
DefaultDirName={autopf}\Vibe SpaceMouse Bridge for Codex
DefaultGroupName=Vibe SpaceMouse Bridge for Codex
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=VibeSpaceMouseBridgeForCodex-{#MyAppVersion}-x64-setup
SetupIconFile=..\spacemouse_input\assets\vibe-6dof.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=DRIVER_NOTICE.txt
WizardStyle=modern

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "autostart"; Description: "Windowsログイン時にタスクトレイへ自動起動"; GroupDescription: "起動設定:"; Flags: checkedonce

[Files]
Source: "..\dist\VibeSpaceMouseBridgeForCodex\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\native\vhidmini2\driver\umdf2\x64\Release\VhidminiUm\*"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\native\vhidmini2\driver\umdf2\x64\Release\CodexMicroHid.cer"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\native\swdevice_creator\x64\Release\swdevice_creator.exe"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "install_driver.ps1"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "uninstall_driver.ps1"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\BETA_README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_LICENSES\*"; DestDir: "{app}\THIRD_PARTY_LICENSES"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Vibe SpaceMouse Bridge for Codex"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\詳細設定"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--advanced"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VibeSpaceMouseBridgeForCodex"; ValueData: """{app}\{#MyAppExeName}"" --background"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "SpaceMouseCodexBridge"; Flags: deletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Vibe SpaceMouse Bridge for Codexを起動"; Flags: nowait postinstall skipifsilent

[InstallDelete]
Type: files; Name: "{app}\SpaceMouseCodexBridge.exe"

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\driver\uninstall_driver.ps1"" -InstallDirectory ""{app}"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveSpaceMouseCodexDriver"

[UninstallDelete]
Type: dirifempty; Name: "{app}\driver"
Type: dirifempty; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\driver\install_driver.ps1') + '" -DriverDirectory "' + ExpandConstant('{app}\driver') + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode
    ) or (ResultCode <> 0) then
      RaiseException(Format('仮想HIDドライバの導入に失敗しました (exit %d)。%s', [ResultCode, ExpandConstant('{commonappdata}\SpaceMouseCodex\install.log')]));
  end;
end;
