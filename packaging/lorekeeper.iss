; Inno Setup script: wraps dist\Lorekeeper (PyInstaller) into one installer, Lorekeeper-Setup-<version>.exe.
;   iscc /DAppVersion=0.1.0 packaging\lorekeeper.iss
; Per-user install (no admin prompt) into %LOCALAPPDATA%\Programs\Lorekeeper. Your notes, gear and settings live in
; %APPDATA%\Lorekeeper and are kept on uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{27FCD19A-01DD-440D-A0DD-EFB72B18928D}
AppName=Lorekeeper
AppVersion={#AppVersion}
AppVerName=Lorekeeper {#AppVersion}
AppPublisher=FindlayHi
AppPublisherURL=https://lorekeeper-cgv.pages.dev/
AppSupportURL=https://github.com/FindlayHi/lorekeeper/issues
AppUpdatesURL=https://github.com/FindlayHi/lorekeeper/releases
DefaultDirName={localappdata}\Programs\Lorekeeper
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Lorekeeper-Setup-{#AppVersion}
SetupIconFile=..\assets\lorekeeper.ico
UninstallDisplayIcon={app}\Lorekeeper.exe
UninstallDisplayName=Lorekeeper
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "startup"; Description: "Start Lorekeeper when Windows starts"; GroupDescription: "Options:"

[Files]
Source: "..\dist\Lorekeeper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Lorekeeper"; Filename: "{app}\Lorekeeper.exe"; Comment: "A voice companion for PC games"
Name: "{userstartup}\Lorekeeper"; Filename: "{app}\Lorekeeper.exe"; Tasks: startup

[Run]
Filename: "{app}\Lorekeeper.exe"; Description: "Start Lorekeeper now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM Lorekeeper.exe /F"; Flags: runhidden; RunOnceId: "StopLorekeeper"

[Messages]
WelcomeLabel2=This installs Lorekeeper, a voice companion for PC games: hold a key in a game, ask out loud, hear the answer.%n%nYou'll need a Claude Pro or Max plan. If Claude Code isn't installed yet, Lorekeeper offers to set it up the first time it starts.

[Code]
// Lorekeeper answers through Claude Code: say on the last page whether it's here yet (the app offers to install it).
function ClaudeCodeFound(): Boolean;
begin
  Result := FileExists(ExpandConstant('{%USERPROFILE}\.local\bin\claude.exe'))
    or (FileSearch('claude.exe', GetEnv('PATH')) <> '')
    or (FileSearch('claude.cmd', GetEnv('PATH')) <> '');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
    if ClaudeCodeFound() then
      WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
        'Claude Code is installed, so Lorekeeper is ready. Hold Ctrl+Alt+Space in a game and ask.'
    else
      WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
        'One more step: Lorekeeper needs Claude Code (with a Claude Pro or Max plan). It isn''t installed yet, ' +
        'so when Lorekeeper starts it will offer to install it and help you sign in.';
end;
