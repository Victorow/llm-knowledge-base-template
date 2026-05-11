#define MyAppName "LLM Knowledge Base"
#define MyAppExeName "LLMKnowledgeBase.exe"
#define MyAppVersion "0.1.0"

[Setup]
AppId={{8F8D8C5A-BD54-45C1-A5C3-4AC5F0E01234}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\LLM Knowledge Base
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=LLMKnowledgeBaseSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\..\dist\LLMKnowledgeBase\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "ui"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "ui"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "ui"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
