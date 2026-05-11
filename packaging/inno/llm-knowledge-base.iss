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
Name: "desktopicon";    Description: "Criar atalho na área de trabalho";         GroupDescription: "Atalhos:"; Flags: unchecked
Name: "configure_mcp";  Description: "Conectar ao Claude Code automaticamente (recomendado)"; GroupDescription: "Claude Code:"; Flags: checked

[Run]
; Lança o app ao final da instalação
Filename: "{app}\{#MyAppExeName}"; Parameters: "ui"; \
  Description: "Abrir {#MyAppName} agora"; \
  Flags: nowait postinstall skipifsilent

; Configura o MCP no Claude Code (executado silenciosamente se o usuário marcou a opção)
Filename: "{app}\{#MyAppExeName}"; \
  Parameters: "setup-mcp --exe-path ""{app}\{#MyAppExeName}"" --kb-root ""{code:GetKbRoot}"""; \
  Tasks: configure_mcp; \
  Description: "Configurar integração com Claude Code"; \
  Flags: runhidden

[UninstallRun]
; Remove a entrada do MCP ao desinstalar
Filename: "{app}\{#MyAppExeName}"; Parameters: "setup-mcp --remove"; Flags: runhidden

[Code]
var
  KbRootPage: TInputDirWizardPage;

{ ------------------------------------------------------------------ }
{ Cria a página extra no wizard pedindo onde salvar a base de conhecimento }
{ ------------------------------------------------------------------ }
procedure InitializeWizard;
var
  DefaultKbRoot: String;
begin
  DefaultKbRoot := ExpandConstant('{userdocs}\LLM Knowledge Base');

  KbRootPage := CreateInputDirPage(
    wpSelectDir,
    'Pasta da Base de Conhecimento',
    'Onde o app vai guardar seus registros e artigos?',
    'O app precisa de uma pasta para salvar automaticamente um resumo de cada sessão ' +
    'com o Claude Code e os artigos de wiki gerados a partir delas.' + #13#10 + #13#10 +
    'Você pode usar qualquer pasta. Se não tiver certeza, deixe o valor padrão.',
    False,
    'Nova pasta'
  );
  KbRootPage.Add('');
  KbRootPage.Values[0] := DefaultKbRoot;
end;

{ ------------------------------------------------------------------ }
{ Valida que o usuário escolheu uma pasta antes de prosseguir        }
{ ------------------------------------------------------------------ }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = KbRootPage.ID then
  begin
    if Trim(KbRootPage.Values[0]) = '' then
    begin
      MsgBox(
        'Por favor, escolha uma pasta para a base de conhecimento.',
        mbError, MB_OK
      );
      Result := False;
    end;
  end;
end;

{ ------------------------------------------------------------------ }
{ Expõe o valor da pasta para a seção [Run]                          }
{ ------------------------------------------------------------------ }
function GetKbRoot(Param: String): String;
begin
  Result := KbRootPage.Values[0];
end;

{ ------------------------------------------------------------------ }
{ Cria a pasta da KB na primeira instalação se ela não existir       }
{ ------------------------------------------------------------------ }
procedure CurStepChanged(CurStep: TSetupStep);
var
  KbRoot, DailyDir, KnowledgeDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    KbRoot      := KbRootPage.Values[0];
    DailyDir    := KbRoot + '\kb\daily';
    KnowledgeDir := KbRoot + '\kb\knowledge\concepts';

    if not DirExists(KbRoot) then
      CreateDir(KbRoot);
    if not DirExists(KbRoot + '\kb') then
      CreateDir(KbRoot + '\kb');
    if not DirExists(KbRoot + '\kb\daily') then
      CreateDir(DailyDir);
    if not DirExists(KbRoot + '\kb\knowledge') then
      CreateDir(KbRoot + '\kb\knowledge');
    if not DirExists(KbRoot + '\kb\knowledge\concepts') then
      CreateDir(KnowledgeDir);
    if not DirExists(KbRoot + '\kb\knowledge\connections') then
      CreateDir(KbRoot + '\kb\knowledge\connections');
    if not DirExists(KbRoot + '\kb\knowledge\qa') then
      CreateDir(KbRoot + '\kb\knowledge\qa');
  end;
end;
