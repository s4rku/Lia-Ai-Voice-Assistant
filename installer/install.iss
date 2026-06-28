; Inno Setup script for Lia AI Voice Assistant
; Compile with Inno Setup 6+ to produce LiaSetup.exe

[Setup]
AppName=Lia AI Voice Assistant
AppVersion=1.0.0
AppPublisher=Lia Project
DefaultDirName={autopf}\Lia
DefaultGroupName=Lia
OutputBaseFilename=LiaSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "..\dist\lia.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\\.env.example";   DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "..\README.md";       DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\lia";        Filename: "{app}\lia.exe"
Name: "{group}\Uninstall";    Filename: "{uninstallexe}"
Name: "{commondesktop}\lia"; Filename: "{app}\lia.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\lia.exe"; Description: "Launch lia"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'Lia is a Jarvis-like AI Voice Assistant for Windows.' + #13#10 +
    'After installation, edit {app}\.env and add your OPENAI_API_KEY.';
end;
