; Inno Setup script for Sarku AI Voice Assistant
; Compile with Inno Setup 6+ to produce SarkuSetup.exe

[Setup]
AppName=Sarku AI Voice Assistant
AppVersion=1.0.0
AppPublisher=Sarku Project
DefaultDirName={autopf}\Sarku
DefaultGroupName=Sarku
OutputBaseFilename=SarkuSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "..\dist\Sarku.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\\.env.example";   DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "..\README.md";       DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\Sarku";        Filename: "{app}\Sarku.exe"
Name: "{group}\Uninstall";    Filename: "{uninstallexe}"
Name: "{commondesktop}\Sarku"; Filename: "{app}\Sarku.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\Sarku.exe"; Description: "Launch Sarku"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'Sarku is a Jarvis-like AI Voice Assistant for Windows.' + #13#10 +
    'After installation, edit {app}\.env and add your OPENAI_API_KEY.';
end;
