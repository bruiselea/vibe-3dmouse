#define MyAppName "SpaceMouse Codex Bridge"
#define MyAppVersion "0.1.0-beta.1"
#define MyAppExeName "SpaceMouseCodexBridge.exe"

[Setup]
AppId={{65F015A2-15CB-4AC0-BE98-44CF9296F3B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=SpaceMouse Codex Community
DefaultDirName={autopf}\SpaceMouse Codex Bridge
DefaultGroupName=SpaceMouse Codex Bridge
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=SpaceMouseCodexBridge-{#MyAppVersion}-x64-setup
SetupIconFile=..\spacemouse_input\assets\spacemouse-controller.ico
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
Source: "..\dist\SpaceMouseCodexBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\native\vhidmini2\driver\umdf2\x64\Release\VhidminiUm\*"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\native\vhidmini2\driver\umdf2\x64\Release\CodexMicroHid.cer"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\native\swdevice_creator\x64\Release\swdevice_creator.exe"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "install_driver.ps1"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "uninstall_driver.ps1"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\BETA_README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SpaceMouse Codex Bridge"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\詳細設定"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--advanced"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SpaceMouseCodexBridge"; ValueData: """{app}\{#MyAppExeName}"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "SpaceMouse Codex Bridgeを起動"; Flags: nowait postinstall skipifsilent

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
