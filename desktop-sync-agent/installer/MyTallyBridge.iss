; MyTally Bridge installer (Inno Setup 6). Built in CI by .github/workflows/agent-exe.yml after the exe, with
;   iscc /DAppVersion=2.0.0 /DSourceExe=dist\SnehDistribuorsSync.exe installer\MyTallyBridge.iss
;
; Per-user: installs under the person's own profile, needs no administrator rights, writes only to HKCU.
; Deliberately NOT here: a scheduled task (schtasks), a Run-key entry or any service. Starting with Windows is
; the agent's own setting (Settings > Start with Windows); the installer neither enables nor removes it.
; Uninstall removes the program only; the person's sign-in, settings and backups folder are left alone.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceExe
  #define SourceExe "..\dist\SnehDistribuorsSync.exe"
#endif

[Setup]
AppId={{6F1C2E4B-8B1D-4E0B-9C57-3D2A7B6A1F10}
AppName=MyTally Bridge
AppVersion={#AppVersion}
AppPublisher=MyTally
DefaultDirName={autopf}\MyTally Bridge
DefaultGroupName=MyTally Bridge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=MyTallyBridge-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SnehDistribuorsSync.exe
SetupIconFile=..\assets\icon.ico
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MyTally Bridge"; Filename: "{app}\SnehDistribuorsSync.exe"
Name: "{autodesktop}\MyTally Bridge"; Filename: "{app}\SnehDistribuorsSync.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\SnehDistribuorsSync.exe"; Description: "Open MyTally Bridge"; Flags: nowait postinstall skipifsilent
