#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\ChaosticTool"
#endif
#ifndef ReleaseDir
  #define ReleaseDir "..\..\release"
#endif
#ifndef AppIdentity
  #define AppIdentity "{{1DBE58AE-AF15-4FBC-B610-E4D6AD047EB1}"
#endif

#ifndef AppArch
  #define AppArch "x64"
#endif

[Setup]
AppId={#AppIdentity}
AppName=ChaosticTool Desktop
AppVersion={#AppVersion}
AppPublisher=Chaos-Tic
AppPublisherURL=https://github.com/Chaos-Tic/Chaostic-Tool
DefaultDirName={localappdata}\Programs\ChaosticTool
DefaultGroupName=ChaosticTool
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
#if AppArch == "arm64"
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
#else
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=ChaosticTool-Setup-{#AppVersion}-windows-{#AppArch}
SetupIconFile=..\..\desktop\assets\icon.ico
UninstallDisplayIcon={app}\ChaosticTool.exe
UninstallDisplayName=ChaosticTool Desktop
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ChaosticTool Desktop"; Filename: "{app}\ChaosticTool.exe"
Name: "{autodesktop}\ChaosticTool Desktop"; Filename: "{app}\ChaosticTool.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ChaosticTool.exe"; Description: "Ouvrir ChaosticTool Desktop"; Flags: nowait postinstall skipifsilent

; No UninstallDelete entry: personal data and third-party tools are deliberately preserved.
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('ChaosticTool Desktop a été désinstallé.' + #13#10 + #13#10 +
      'Vos cibles et résultats sont conservés dans :' + #13#10 +
      ExpandConstant('{localappdata}\ChaosticTool\Desktop') + #13#10 + #13#10 +
      'Les outils externes installés séparément sont conservés.', mbInformation, MB_OK);
end;
