# LLM Knowledge Base

Uma base de conhecimento pessoal que aprende sozinha enquanto você usa o Claude Code.

> **Novo usuário?** Siga o [Guia de Início Rápido](#guia-de-início-rápido) abaixo — leva menos de 5 minutos.

---

## O que é isso?

Imagine um caderno de anotações que se escreve sozinho. Toda vez que você trabalha com o Claude Code, o app registra automaticamente o que foi feito e aprendido naquela sessão. Com o tempo, ele monta uma **wiki pessoal** com tudo que você já descobriu — e coloca esse conhecimento de volta no contexto do Claude automaticamente na próxima sessão.

**Na prática:**
- Você trabalha normalmente com o Claude Code
- O app captura e organiza tudo em segundo plano
- Na próxima sessão, o Claude já sabe o que você aprendeu antes
- Você pode perguntar para sua base de conhecimento: *"Como eu fiz X no mês passado?"*

---

## Guia de Início Rápido

### Windows

**Passo 1 — Instale o app**

Baixe o instalador na [página de releases](../../releases) e execute `LLMKnowledgeBaseSetup.exe`.

Durante a instalação você vai ver perguntas simples:
1. **"Onde instalar o programa?"** — deixe o padrão
2. **"Onde salvar sua base de conhecimento?"** — escolha uma pasta (ex: `Documentos\LLM Knowledge Base`)
3. **"Conectar ao Claude Code automaticamente?"** — deixe marcado ✓

**Passo 2 — Reinicie o Claude Code**

Feche e abra o Claude Code novamente.

**Passo 3 — Trabalhe normalmente**

O app captura tudo em segundo plano. Abra o painel pelo atalho no menu Iniciar.

---

### Linux

**Passo 1 — Baixe e instale**

Baixe a pasta `LLMKnowledgeBase` da [página de releases](../../releases), extraia e rode:

```bash
sh packaging/linux/install.sh ~/Downloads/LLMKnowledgeBase
```

O instalador vai perguntar:
- **"Onde salvar sua base de conhecimento?"** — pressione Enter para usar o padrão (`~/Documents/LLM Knowledge Base`)
- **"Conectar ao Claude Code automaticamente?"** — pressione Enter para confirmar

Ele instala tudo sem precisar de senha (`sudo`).

**Passo 2 — Reinicie o Claude Code**

Feche e abra o Claude Code novamente.

**Passo 3 — Trabalhe normalmente**

O app aparece no menu de aplicativos. Para abrir pelo terminal:
```bash
llm-knowledge-base ui
```

**Desinstalar:**
```bash
sh ~/Applications/llm-knowledge-base/uninstall.sh
```

---

## Índice

- [Como Funciona](#como-funciona)
- [Clientes Suportados](#clientes-suportados)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Início Rápido](#início-rápido)
- [Painel de Controle Desktop](#painel-de-controle-desktop)
- [Comandos CLI](#comandos-cli)
- [Configuração de Hooks](#configuração-de-hooks)
- [Automação Diária](#automação-diária)
- [Múltiplos Perfis](#múltiplos-perfis)
- [Backend de Agente](#backend-de-agente)
- [Guia de Início Rápido](#guia-de-início-rápido)
- [Integração com o Claude Code (MCP)](#integração-com-o-claude-code-mcp)
- [Guia Completo das Funcionalidades](#guia-completo-das-funcionalidades)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Estrutura de Arquivos](#estrutura-de-arquivos)
- [Empacotamento](#empacotamento)
- [Custos](#custos)
- [Arquitetura](#arquitetura)

---

## Como Funciona

```
Sua sessão Claude Code/Codex
        │
        ▼
  hooks/session-end.py
  (captura transcript)
        │
        ▼
  scripts/flush.py
  (resume para daily log)
        │
        ▼
  kb/daily/YYYY-MM-DD.md
  (memória estruturada do dia)
        │
        ▼
  scripts/compile.py
  (LLM extrai artigos)
        │
        ▼
  kb/knowledge/
  ├── index.md
  ├── concepts/
  ├── connections/
  └── qa/
```

Na próxima sessão, `hooks/session-start.py` injeta o índice do wiki e o log recente diretamente no contexto do Claude Code — sem precisar pesquisar manualmente.

---

## Clientes Suportados

| Superfície | Status | Como funciona |
|---|---|---|
| Claude Code | Suportado | Hooks `SessionStart`, `SessionEnd` e `PreCompact` |
| Codex | Suportado | Hooks `SessionStart` e `Stop` com `features.codex_hooks = true` |
| Painel Desktop | Suportado | UI PySide6, fila de jobs, diagnósticos, entrypoint de hook empacotado |
| Automação macOS/Linux | Suportado | `scripts/compile-daily.sh` com launchd ou systemd |
| Automação Windows | Suportado | `scripts/compile-daily.ps1` com Task Scheduler |

---

## Pré-requisitos

- **Python 3.12+** e [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Um cliente AI:
  - Claude Code instalado e autenticado, **ou**
  - Codex CLI/App instalado e autenticado
- Um backend de agente:
  - Padrão: Claude Agent SDK (usa credenciais do Claude Code)
  - Alternativo: `KB_AGENT_BACKEND=codex`

---

## Instalação

### Opção 1 — Instalador Windows (recomendado para usuários finais)

Baixe `LLMKnowledgeBaseSetup.exe` na [página de releases](../../releases) e execute. Não requer administrador.

O instalador coloca o app em `%LOCALAPPDATA%\Programs\LLM Knowledge Base` e cria atalhos no menu Iniciar.

### Opção 2 — A partir do código-fonte (recomendado para desenvolvedores)

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/llm-knowledge-base.git
cd llm-knowledge-base

# 2. Instale as dependências
uv sync
```

PowerShell:
```powershell
git clone https://github.com/seu-usuario/llm-knowledge-base.git
cd llm-knowledge-base
uv sync
```

---

## Início Rápido

### 1. Configure os hooks do Claude Code

**macOS/Linux:**
```bash
cat .claude/settings.example.json
# Copie o conteúdo para ~/.claude/settings.json
# Substitua /ABSOLUTE/PATH/TO/llm-knowledge-base pelo caminho real do clone
```

**Windows PowerShell:**
```powershell
Get-Content .claude\settings.windows.example.json
# Copie o conteúdo para %USERPROFILE%\.claude\settings.json
# Substitua C:\ABSOLUTE\PATH\TO\llm-knowledge-base pelo caminho real
```

Se você já tem hooks configurados, **mescle os arrays** em vez de substituir o arquivo.

### 2. Inicie uma sessão e trabalhe normalmente

O hook `session-start` injeta automaticamente o índice do wiki e o log recente. O hook `session-end` captura o transcript e inicia o flush em background.

### 3. Compile seus logs em artigos

```bash
uv run python scripts/compile.py
```

### 4. Consulte sua base de conhecimento

```bash
uv run python scripts/query.py "Como eu lido com autenticação JWT?"
```

### 5. (Opcional) Abra o painel desktop

```bash
uv run python -m kb_app ui
```

---

## Painel de Controle Desktop

O app desktop é um painel de controle sobre o pipeline KB existente. Ele não substitui o Claude Code ou Codex, e não os inclui. Expõe perfis, configuração de hooks, logs diários, navegação do conhecimento, operações de compile/query/lint, histórico de jobs, configurações do agendador e diagnósticos através de uma UI PySide6 local.

### Executar

**A partir do código-fonte:**
```bash
uv run python -m kb_app ui
```

**A partir do instalador:**
Abra pelo menu Iniciar ou atalho da área de trabalho.

**Flags disponíveis:**
```bash
uv run python -m kb_app ui --no-tray   # desativa ícone na bandeja do sistema
```

### Páginas do Painel

| Página | O que faz |
|---|---|
| **Dashboard** | Resumo de status: perfil ativo, backend, último job |
| **Setup** | Wizard de primeira execução, smoke test do backend |
| **Profiles** | Criar e alternar entre múltiplas bases de conhecimento |
| **Hooks** | Instalar/remover/reparar hooks nos clientes AI |
| **Daily Logs** | Navegar e visualizar os logs diários capturados |
| **Knowledge** | Navegar artigos do wiki (`concepts/`, `connections/`, `qa/`) |
| **Operations** | Executar compile, query, lint manualmente |
| **Jobs** | Histórico e status dos jobs em background |
| **Settings** | Backend padrão, agendamento diário, autostart |
| **Diagnostics** | Exportar bundle ZIP de diagnósticos com redação de segredos |

### Separação de dados

O app separa três locais de dados:
- **Diretório de instalação:** executável e bibliotecas
- **App data:** banco SQLite, configuração da UI, histórico de jobs, logs (`%APPDATA%\LLM Knowledge Base\`)
- **KB data:** `AGENTS.md`, `CONTEXT.md`, `kb/daily/`, `kb/knowledge/` (o seu repositório clonado)

---

## Comandos CLI

Todos os comandos estão disponíveis via `uv run python -m kb_app` (código-fonte) ou `LLMKnowledgeBase.exe` (instalado).

### Parâmetros globais

```bash
llm-knowledge-base [--kb-root DIR] [--app-db PATH] <subcomando>
```

| Flag | Padrão | Descrição |
|---|---|---|
| `--kb-root DIR` | diretório atual | Raiz da knowledge base |
| `--app-db PATH` | `~/.../app.db` | Caminho do banco SQLite do app |

---

### `compile` — Compilar logs diários em artigos

```bash
# Compilar apenas logs com mudanças (mais comum)
uv run python -m kb_app compile

# Forçar recompilação de tudo
uv run python -m kb_app compile --all

# Compilar um log específico
uv run python -m kb_app compile --file kb/daily/2026-05-10.md

# Visualizar o que seria compilado sem executar
uv run python -m kb_app compile --dry-run
```

**Output:**
```
Files to compile (2):
  - 2026-05-10.md
  - 2026-05-11.md
Total cost: $0.03
```

O compilador detecta mudanças por hash SHA-256. Apenas logs modificados desde a última compilação são reprocessados.

---

### `query` — Consultar a base de conhecimento

```bash
# Consulta simples (resposta no terminal)
uv run python -m kb_app query "Como eu estruturo autenticação JWT?"

# Gravar a resposta como artigo Q&A em kb/knowledge/qa/
uv run python -m kb_app query "Qual padrão de retry eu uso?" --file-back
```

**Output:**
```
Com base nos seus logs de sessão, você usa JWT com refresh tokens armazenados
em httpOnly cookies... [[concepts/auth-patterns]]
```

---

### `lint` — Verificar saúde da base de conhecimento

```bash
# Lint completo (estrutural + verificação LLM de contradições)
uv run python -m kb_app lint

# Apenas checks estruturais (gratuito, sem LLM)
uv run python -m kb_app lint --structural-only
```

**Checks realizados:**

| Check | Severidade | Descrição |
|---|---|---|
| `broken_link` | Erro | Wikilinks que apontam para artigos inexistentes |
| `orphan_page` | Aviso | Artigos sem nenhum inbound link |
| `orphan_source` | Aviso | Daily logs não compilados |
| `stale_article` | Aviso | Logs modificados após a última compilação |
| `missing_backlink` | Sugestão | Links unidirecionais (auto-corrigível) |
| `sparse_article` | Sugestão | Artigos com menos de 200 palavras |
| `contradiction` | Aviso | Contradições entre artigos (verificação LLM) |

**Output:**
```
Report saved to: reports/lint-2026-05-11.md
Results: 0 errors, 2 warnings, 3 suggestions
```

Exit code `1` se houver erros.

---

### `hook` — Executar evento de hook

Normalmente chamado pelos clientes AI via hooks configurados, não diretamente.

```bash
# Retorna JSON de contexto para injetar na sessão
uv run python -m kb_app hook session-start

# Processar fim de sessão (lê JSON do stdin)
uv run python -m kb_app hook session-end

# Hook de pré-compactação do Claude Code
uv run python -m kb_app hook pre-compact
```

---

### `diagnostics export` — Exportar diagnósticos

```bash
# Exportar para o diretório padrão (diagnostics/)
uv run python -m kb_app diagnostics export

# Exportar para diretório específico
uv run python -m kb_app diagnostics export --output reports/
```

**Output:** arquivo `.zip` com metadados do sistema, configurações e logs com segredos redatados (chaves API, tokens, senhas são substituídos por `[REDACTED]`).

---

### `profiles` — Gerenciar múltiplas KBs

```bash
# Listar perfis
uv run python -m kb_app profiles list

# Criar perfil
uv run python -m kb_app profiles create "Trabalho" /caminho/para/kb-trabalho

# Criar com backend específico
uv run python -m kb_app profiles create "Pessoal" /caminho/kb-pessoal --backend codex

# Ativar perfil
uv run python -m kb_app profiles activate 2
```

---

### `jobs` — Gerenciar fila de jobs

```bash
# Enfileirar compilação
uv run python -m kb_app jobs enqueue compile_changed --profile-id 1

# Enfileirar query com payload
uv run python -m kb_app jobs enqueue query --profile-id 1 \
  --payload-json '{"question": "O que sei sobre Docker?"}'

# Enfileirar com prioridade alta (número menor = mais prioritário)
uv run python -m kb_app jobs enqueue compile_all --profile-id 1 --priority 10
```

**Tipos de job disponíveis:**

| job_type | Payload | Descrição |
|---|---|---|
| `compile_changed` | — | Compila logs com mudanças |
| `compile_all` | — | Recompila todos os logs |
| `compile_file` | `{"file": "caminho"}` | Compila arquivo específico |
| `query` | `{"question": "..."}` | Consulta sem gravar |
| `query_file_back` | `{"question": "..."}` | Consulta e grava como artigo Q&A |
| `lint_structural` | — | Lint sem LLM |
| `lint_full` | — | Lint com verificação de contradições |
| `manual_memory` | `{"content": "..."}` | Adiciona memória manual ao log do dia |
| `install_hooks` | `{"client": "claude"}` | Instala hooks no config do cliente AI |
| `remove_hooks` | `{"client": "claude"}` | Remove hooks do config |
| `install_autostart` | — | Cria launcher no Startup do Windows |
| `diagnostics_export` | `{"output_dir": "..."}` | Exporta diagnósticos |
| `backend_smoke_test` | — | Testa conectividade do backend |

---

### Scripts standalone (legado)

Os scripts em `scripts/` são wrappers sobre `kb_app` e continuam funcionando:

```bash
uv run python scripts/compile.py [--all] [--file FILE] [--dry-run]
uv run python scripts/query.py "pergunta" [--file-back]
uv run python scripts/lint.py [--structural-only]
```

---

## Configuração de Hooks

### Claude Code

**macOS/Linux:**
```bash
cat .claude/settings.example.json
```

Copie para `~/.claude/settings.json` e substitua `/ABSOLUTE/PATH/TO/llm-knowledge-base` pelo caminho real.

**Windows:**
```powershell
Get-Content .claude\settings.windows.example.json
```

Copie para `%USERPROFILE%\.claude\settings.json` e substitua `C:\ABSOLUTE\PATH\TO\llm-knowledge-base`.

Se já tiver hooks configurados, mescle os arrays `hooks` em vez de substituir o arquivo.

### Codex

Ative a feature flag no config:

```toml
# ~/.codex/config.toml ou <repo>/.codex/config.toml
[features]
codex_hooks = true
```

Copie o template de hooks:

**macOS/Linux:**
```bash
cp .codex/hooks.example.json .codex/hooks.json
```

**Windows:**
```powershell
Copy-Item .codex\hooks.windows.example.json .codex\hooks.json
```

Substitua os caminhos placeholder pelo caminho absoluto do projeto.

---

## Automação Diária

### Windows — Task Scheduler

```powershell
# Testar sem agendar
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\compile-daily.ps1 -DryRun

# Registrar tarefa diária às 17:00
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\register-windows-task.ps1 -At 17:00

# Verificar
Get-ScheduledTask -TaskName LLMKnowledgeBaseDailyCompile

# Executar manualmente
Start-ScheduledTask -TaskName LLMKnowledgeBaseDailyCompile

# Ver logs
Get-Content scripts\compile.log -Tail 80
```

### macOS — Launchd

```bash
cp scripts/com.user.kb-daily-compile.plist.example \
   ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

sed -i '' "s|/ABSOLUTE/PATH/TO/llm-knowledge-base|$PWD|g" \
   ~/Library/LaunchAgents/com.user.kb-daily-compile.plist

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.kb-daily-compile.plist
```

### Linux — Systemd

Crie `~/.config/systemd/user/kb-compile.service`:
```ini
[Unit]
Description=Compile LLM knowledge base

[Service]
Type=oneshot
ExecStart=%h/llm-knowledge-base/scripts/compile-daily.sh
```

Crie `~/.config/systemd/user/kb-compile.timer`:
```ini
[Unit]
Description=Daily KB compile às 17:00

[Timer]
OnCalendar=*-*-* 17:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-compile.timer
```

---

## Múltiplos Perfis

O app suporta múltiplas bases de conhecimento isoladas via perfis. Cada perfil tem seu próprio diretório de KB e backend.

```bash
# Criar dois perfis
uv run python -m kb_app profiles create "Trabalho" /projetos/kb-trabalho
uv run python -m kb_app profiles create "Pessoal" /home/user/kb-pessoal

# Ver lista (o * indica o ativo)
uv run python -m kb_app profiles list
# * 1: Trabalho [claude] /projetos/kb-trabalho
#   2: Pessoal [claude] /home/user/kb-pessoal

# Ativar o segundo
uv run python -m kb_app profiles activate 2
```

O perfil ativo é usado pela UI e pelo agendador automático. A CLI aceita `--kb-root` para apontar para qualquer KB independentemente do perfil ativo.

---

## Backend de Agente

O cliente que produziu o transcript e o backend que executa o trabalho LLM são deliberadamente separados.

### Claude (padrão)

```bash
uv run python -m kb_app compile
uv run python -m kb_app query "O que sei sobre Docker?"
```

Usa o Claude Agent SDK com as credenciais do Claude Code instalado localmente.

### Codex

```bash
# Linux/macOS
KB_AGENT_BACKEND=codex uv run python -m kb_app compile

# Windows PowerShell
$env:KB_AGENT_BACKEND = "codex"
uv run python -m kb_app compile
```

O backend Codex executa `codex exec` de forma não-interativa via subprocess. Recursão infinita é prevenida pela variável `KB_INVOKED_BY`.

**Modelo padrão do Codex:** `gpt-5.3-codex`. Para outro modelo:

```powershell
$env:KB_CODEX_MODEL = "gpt-5.5"
$env:KB_AGENT_BACKEND = "codex"
uv run python -m kb_app compile
```

---

## Integração com o Claude Code (MCP)

O app se conecta ao Claude Code via MCP (Model Context Protocol). Isso permite que o Claude acesse sua base de conhecimento diretamente — sem você precisar fazer nada a mais.

### Via instalador (recomendado — zero configuração)

**Windows:** Se usou o `LLMKnowledgeBaseSetup.exe` com a opção **"Conectar ao Claude Code automaticamente"** marcada, a integração já foi configurada. Basta **reiniciar o Claude Code**.

**Linux:** Se usou o `install.sh` e respondeu "sim" à pergunta do MCP, a integração já foi configurada. Basta **reiniciar o Claude Code**.

### Configuração manual

Se precisar configurar ou reconfigurar, um único comando detecta e atualiza o arquivo do Claude automaticamente:

**Windows (app instalado):**
```powershell
& "$env:LOCALAPPDATA\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" `
  setup-mcp --kb-root "C:\Pasta\Da\Sua\KB"
```

**Linux (app instalado):**
```bash
llm-knowledge-base setup-mcp --kb-root "$HOME/Documents/LLM Knowledge Base"
```

**macOS/Linux (código-fonte):**
```bash
uv run python -m kb_app setup-mcp --kb-root /pasta/da/sua/kb
```

Após rodar, **reinicie o Claude Code**.

### Verificar se está funcionando

```bash
# Windows
& "$env:LOCALAPPDATA\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" setup-mcp --status

# Linux
llm-knowledge-base setup-mcp --status
```

### O que o Claude pode fazer com a integração ativa

| O que faz | Ferramenta técnica |
|---|---|
| Ver seu histórico de conhecimento | `kb_get_context` |
| Responder sobre o que você aprendeu | `kb_query` |
| Compilar sessões em artigos de wiki | `kb_compile` |
| Verificar saúde da wiki | `kb_lint` |
| Adicionar uma anotação manual | `kb_add_memory` |
| Listar artigos existentes | `kb_list_articles` |
| Ler um artigo específico | `kb_read_article` |
| Exportar diagnósticos | `kb_diagnostics` |

### Remover a integração

```powershell
& "$env:LOCALAPPDATA\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" setup-mcp --remove
```

### Para desenvolvedores (sem o instalador)

```bash
uv sync  # já inclui a dependência mcp
uv run python -m kb_app setup-mcp --kb-root /pasta/da/sua/kb
```

---

## Guia Completo das Funcionalidades

Esta seção explica **o que cada parte do app faz e por que ela existe** — tanto o painel visual quanto as ferramentas que o Claude usa automaticamente. Se você está usando pela primeira vez, leia isso antes de qualquer coisa técnica.

---

### O Painel de Controle (UI)

O painel é uma janela que você abre no seu computador para ver e controlar tudo o que a base de conhecimento está fazendo. Pense nele como o "cockpit" do app: você não precisa mexer nele todo dia, mas ele está lá quando você precisa entender o que aconteceu, ajustar algo ou disparar uma operação manualmente.

---

#### Dashboard — Visão geral em tempo real

> **Para que serve:** Te mostra, de relance, se tudo está funcionando.

Quando você abre o app, a primeira tela é o Dashboard. Ele exibe:

- **Perfil ativo** — qual base de conhecimento está sendo usada no momento (útil se você tiver uma KB para trabalho e outra pessoal)
- **Backend configurado** — se está usando Claude ou Codex como "cérebro" que processa seus logs
- **Último job executado** — o que o app fez por último e se terminou com sucesso ou erro

**Por que isso importa:** Sem essa tela, você não saberia se a captura automática está de fato funcionando ou se há algum problema silencioso. É seu primeiro ponto de verificação.

---

#### Setup — Assistente de configuração inicial

> **Para que serve:** Te guia pela configuração na primeira vez que você usa o app.

O Setup é um wizard (assistente passo a passo) que:

1. Verifica se o Python e o `uv` estão instalados corretamente
2. Te pede para escolher a pasta onde sua KB vai ficar
3. Testa a conexão com o backend (Claude ou Codex) para confirmar que suas credenciais funcionam
4. Instala os hooks no Claude Code automaticamente

**Por que isso importa:** Sem passar pelo Setup, o app pode estar instalado mas sem capturar nada — porque os hooks ainda não foram configurados. O Setup garante que tudo está ligado e funcionando antes de você começar a trabalhar.

---

#### Profiles — Múltiplas bases de conhecimento

> **Para que serve:** Te permite ter bases de conhecimento separadas — por exemplo, uma para trabalho e outra pessoal.

Cada "perfil" tem seu próprio diretório de KB e pode usar um backend diferente. Exemplos de uso:

- **Perfil "Trabalho"** → KB em `/projetos/kb-trabalho`, backend Claude
- **Perfil "Pessoal"** → KB em `~/kb-pessoal`, backend Codex

Você cria, renomeia e alterna entre perfis nessa tela.

**Por que isso importa:** Se você misturar projetos pessoais e profissionais na mesma KB, o Claude vai cruzar contextos que não têm nada a ver. Perfis separam isso de forma limpa.

---

#### Hooks — Conectar o app ao Claude Code / Codex

> **Para que serve:** Liga e desliga a captura automática de sessões.

Os hooks são pequenos scripts que o Claude Code ou Codex chama automaticamente em dois momentos:

- **Ao iniciar uma sessão** (`session-start`) → o app injeta no contexto do Claude tudo que você já aprendeu antes, sem você precisar colar nada
- **Ao terminar uma sessão** (`session-end`) → o app captura o que aconteceu e salva no log do dia

Nessa tela você pode:

- **Instalar** os hooks com um clique (em vez de editar arquivos JSON manualmente)
- **Verificar** se os hooks estão presentes e configurados corretamente
- **Remover** os hooks se quiser desativar a captura temporariamente
- **Reparar** hooks quebrados (por exemplo, se o caminho do app mudou após uma reinstalação)

**Por que isso importa:** Sem os hooks, o app não captura nada. É literalmente o que conecta o Claude Code à sua base de conhecimento. Se a captura automática parar de funcionar, esta é a primeira tela para verificar.

---

#### Daily Logs — Seus diários de sessão

> **Para que serve:** Te permite ver o que foi registrado em cada dia de trabalho.

Cada vez que você termina uma sessão de trabalho com o Claude, o app cria ou atualiza um arquivo chamado `YYYY-MM-DD.md` (ex: `2026-05-11.md`). Esse arquivo é o "diário do dia" — um resumo estruturado do que foi feito, aprendido e decidido naquela sessão.

Nessa tela você pode:

- **Navegar** pelos logs de cada dia em um calendário
- **Ler** o conteúdo de qualquer log diário
- **Ver** quantas sessões foram capturadas em cada dia

**Por que isso importa:** É a sua memória bruta. Antes de virar um artigo de wiki, o conhecimento fica aqui. Se você quiser saber "o que eu fiz na quinta-feira passada?", a resposta está nessa tela. Os logs também são a matéria-prima que o compilador usa para gerar os artigos.

---

#### Knowledge — Sua wiki pessoal

> **Para que serve:** Te mostra os artigos que foram gerados automaticamente a partir dos seus logs.

Depois que o compilador processa seus logs, ele cria artigos organizados em três categorias:

| Categoria | Conteúdo |
|---|---|
| `concepts/` | Conceitos técnicos que você aprendeu ou usou (ex: "autenticação JWT", "Docker networks") |
| `connections/` | Como diferentes conceitos se relacionam (ex: "Como JWT se conecta com sessions") |
| `qa/` | Perguntas e respostas que você fez à sua própria KB |

Nessa tela você pode **navegar e ler** qualquer artigo gerado.

**Por que isso importa:** É aqui que você vê o valor acumulado do app. Com o tempo, essa wiki cresce e se torna um repositório do seu conhecimento técnico pessoal — escrito na sua linguagem, baseado nos seus projetos reais.

---

#### Operations — Executar operações manualmente

> **Para que serve:** Te dá controle direto sobre as três operações principais do app.

As três operações que você pode executar por aqui:

**Compile** — Processa os logs diários e gera/atualiza os artigos da wiki
- Útil quando você quer atualizar a wiki imediatamente sem esperar o agendamento automático
- Você pode compilar tudo, só os logs novos, ou um log específico

**Query** — Faz uma pergunta à sua base de conhecimento
- Ex: "Como eu lidei com paginação no mês passado?"
- O app lê todos os artigos e responde citando as fontes
- Opcionalmente salva a resposta como um novo artigo Q&A

**Lint** — Verifica se a wiki está saudável
- Detecta links quebrados (um artigo aponta para outro que não existe)
- Detecta artigos "órfãos" (ninguém aponta para eles)
- Detecta contradições entre artigos (ex: dois artigos dizem coisas opostas sobre o mesmo tópico)

**Por que isso importa:** A automação cuida do dia a dia, mas às vezes você quer disparar uma compilação agora mesmo, ou fazer uma pergunta específica, ou checar se a wiki está consistente. Esta tela substitui a linha de comando para quem prefere a UI.

---

#### Jobs — Histórico de operações em background

> **Para que serve:** Te mostra tudo que o app executou, está executando ou vai executar.

Cada vez que o app faz algo (compilar, fazer query, instalar hooks, etc.), isso é registrado como um "job". Nessa tela você vê:

- **Jobs em andamento** — com barra de progresso
- **Jobs concluídos** — com tempo de execução e custo em USD
- **Jobs com erro** — com o log de erro completo para diagnóstico

**Por que isso importa:** Sem essa tela, quando o app faz algo em background (como processar o fim de uma sessão), você não teria como saber se funcionou ou se deu erro silencioso. O histórico de jobs é o seu "log de auditoria" do que o app realmente fez.

---

#### Settings — Configurações gerais

> **Para que serve:** Ajustar o comportamento padrão do app.

| Configuração | O que faz |
|---|---|
| **Backend padrão** | Qual LLM usar: Claude ou Codex |
| **Agendamento diário** | Horário em que o compilador roda automaticamente (ex: 17:00) |
| **Autostart** | Se o app deve iniciar junto com o sistema operacional |

**Por que isso importa:** O app foi projetado para funcionar sem você precisar abrir nada — mas para isso, o autostart e o agendamento precisam estar ligados. Se você instalou o app e esqueceu de ligar o autostart, o app não vai capturar nada depois que você reiniciar o computador.

---

#### Diagnostics — Exportar diagnósticos para suporte

> **Para que serve:** Gerar um arquivo ZIP com informações do sistema para diagnóstico de problemas.

Quando algo dá errado e você precisa de ajuda, em vez de mandar capturas de tela, você clica em "Exportar Diagnósticos" e o app gera um arquivo `.zip` com:

- Versão do Python, sistema operacional, versão do app
- Configurações relevantes (com chaves de API e tokens **removidos automaticamente**)
- Logs recentes de erros

**Por que isso importa:** Facilita o suporte técnico sem expor informações sensíveis. Você envia o ZIP e quem está ajudando tem contexto suficiente para diagnosticar o problema.

---

### As Ferramentas do MCP

O MCP é o que permite que o **Claude use sua base de conhecimento automaticamente**, sem você precisar fazer nada. Quando o MCP está ativo, o Claude tem acesso a um conjunto de "ferramentas" que ele pode chamar durante uma conversa.

Pense assim: normalmente o Claude só sabe o que você digita na conversa atual. Com o MCP, ele também pode consultar tudo que você já aprendeu e registrou na sua KB — como se ele tivesse acesso à sua memória de longo prazo.

---

#### `kb_get_context` — Carregar o contexto atual da KB

> **Para que serve:** Dar ao Claude uma visão geral do que está na sua base de conhecimento agora.

Quando você inicia uma sessão, esta ferramenta injeta automaticamente:
- O índice da wiki (lista de todos os artigos com resumos de uma linha)
- O log do dia atual (o que você já fez hoje)

**Exemplo de uso pelo Claude:**
> "Deixa eu ver o que você já tem registrado sobre este projeto antes de continuar..."
> *[Claude chama `kb_get_context` e lê o contexto]*
> "Certo, vi que você já trabalhou com autenticação JWT aqui antes. Vou seguir o mesmo padrão..."

**Por que isso importa:** Sem isso, o Claude começa cada sessão do zero, esquecendo tudo que foi feito antes. Com isso, ele "lembra" do seu histórico sem você precisar explicar nada.

---

#### `kb_query` — Perguntar à sua base de conhecimento

> **Para que serve:** Responder perguntas usando apenas o que está na sua KB.

Você (ou o Claude) pode fazer perguntas em linguagem natural:

- "Como eu implementei paginação naquele projeto?"
- "Qual biblioteca de autenticação eu prefiro usar?"
- "O que eu sei sobre Docker networks?"

O app lê todos os seus artigos e responde citando as fontes com links (`[[concepts/auth-patterns]]`).

O parâmetro `file_back: true` salva a resposta como um novo artigo na pasta `qa/`, para que ela fique disponível em consultas futuras.

**Por que isso importa:** Sua KB acumula meses de trabalho. Sem `kb_query`, você teria que lembrar onde guardou cada coisa. Com ela, você simplesmente pergunta e recebe a resposta contextualizada.

---

#### `kb_compile` — Transformar logs em artigos de wiki

> **Para que serve:** Processar os diários de sessão brutos e gerar artigos organizados.

Esta ferramenta dispara o compilador LLM que:
1. Lê os logs diários em `kb/daily/`
2. Extrai conceitos, conexões e aprendizados
3. Cria ou atualiza artigos em `kb/knowledge/`

Parâmetros úteis:
- `force_all: true` → recompila tudo, mesmo artigos que não mudaram
- `file_name: "2026-05-11.md"` → compila apenas aquele dia específico
- `dry_run: true` → mostra o que seria compilado sem executar (sem custo)

**Por que isso importa:** Os logs diários são texto bruto. É o compilador que transforma esse texto em conhecimento estruturado, pesquisável e organizado. Sem compilar, a wiki fica desatualizada.

---

#### `kb_lint` — Verificar a saúde da wiki

> **Para que serve:** Detectar problemas na sua base de conhecimento antes que eles virem dores de cabeça.

Tipos de problema que o lint detecta:

| Problema | Gravidade | Explicação |
|---|---|---|
| Link quebrado | Erro | Artigo A menciona artigo B, mas B não existe |
| Artigo órfão | Aviso | Artigo existe mas nenhum outro aponta para ele |
| Log não compilado | Aviso | Você tem logs novos que ainda não viraram artigos |
| Artigo desatualizado | Aviso | Um log foi modificado depois que o artigo foi gerado |
| Contradição | Aviso | Dois artigos dizem coisas opostas sobre o mesmo assunto |

O parâmetro `structural_only: true` faz apenas as verificações gratuitas (sem usar LLM), o que é útil para checar rapidamente.

**Por que isso importa:** Uma wiki com links quebrados e contradições é menos confiável do que nenhuma wiki. O lint é como uma revisão automática de qualidade que mantém o conhecimento consistente.

---

#### `kb_add_memory` — Adicionar uma anotação manual

> **Para que serve:** Registrar algo que aconteceu fora de uma sessão de AI.

Às vezes você aprende algo em uma reunião, lendo documentação, ou pensando sozinho — e quer registrar isso na KB sem precisar abrir um editor de texto. Com `kb_add_memory`, você fala para o Claude o que quer guardar:

> "Anota aí: decidi usar Redis para cache de sessões em vez de armazenar no banco. O motivo é performance em leituras frequentes."

O Claude chama `kb_add_memory` e isso fica registrado no log do dia atual.

**Por que isso importa:** O conhecimento não vem só de sessões de programação. Decisões de arquitetura, aprendizados em reuniões, insights do dia a dia — tudo pode e deve entrar na KB.

---

#### `kb_list_articles` — Listar todos os artigos

> **Para que serve:** Ver o que existe na sua wiki antes de decidir o que consultar ou atualizar.

Retorna uma lista categorizada de todos os artigos:

```
Total: 47 artigos

## concepts/ (31)
  - concepts/auth-patterns.md
  - concepts/docker-networks.md
  ...

## connections/ (9)
  - connections/jwt-and-sessions.md
  ...

## qa/ (7)
  - qa/como-eu-faco-paginacao.md
  ...
```

**Por que isso importa:** Antes de perguntar "o que eu sei sobre X?", o Claude verifica se existe um artigo sobre X. Isso evita consultas desnecessárias e ajuda a identificar lacunas no conhecimento.

---

#### `kb_read_article` — Ler um artigo específico

> **Para que serve:** Acessar o conteúdo completo de um artigo da wiki.

Você pode pedir pelo caminho exato (`concepts/auth-patterns`) ou por parte do nome — o app encontra o artigo mesmo sem o caminho completo.

**Por que isso importa:** Permite que o Claude consulte um artigo específico em profundidade, em vez de ler apenas o resumo do índice. Quando uma decisão técnica precisa de detalhes, o Claude busca o artigo completo antes de responder.

---

#### `kb_wiki_index` — Ver o índice da wiki

> **Para que serve:** Obter uma visão geral de toda a base de conhecimento em formato de tabela.

O índice contém, para cada artigo:
- Nome e caminho
- Resumo de uma linha
- Fontes (quais logs diários geraram aquele artigo)
- Data da última atualização

É o mesmo índice que é injetado automaticamente no início de cada sessão pelo hook `session-start`.

**Por que isso importa:** É a "mesa de conteúdos" da sua KB. Com ele, o Claude sabe o que existe antes de decidir o que buscar. É mais rápido e barato do que ler todos os artigos para encontrar algo.

---

#### `kb_diagnostics` — Exportar diagnósticos

> **Para que serve:** Gerar um bundle de diagnósticos para resolver problemas.

Equivalente ao botão "Exportar Diagnósticos" da UI, mas acessível diretamente pelo Claude. Útil quando você está num problema e quer que o Claude ajude a diagnosticar sem precisar sair da conversa.

O bundle gerado **nunca contém chaves de API, tokens ou senhas** — todos são substituídos por `[REDACTED]` antes de qualquer exportação.

**Por que isso importa:** Permite que o Claude ajude ativamente a diagnosticar problemas com a KB sem precisar que você copie e cole logs manualmente.

---

### Resumo: o que fazer e quando usar cada coisa

| Situação | O que usar |
|---|---|
| Acabei de instalar, quero configurar tudo | Painel → **Setup** |
| Quero saber se está tudo funcionando | Painel → **Dashboard** |
| A captura parou de funcionar | Painel → **Hooks** |
| Quero ver o que foi registrado hoje | Painel → **Daily Logs** |
| Quero ler um artigo da minha wiki | Painel → **Knowledge** |
| Quero compilar agora sem esperar | Painel → **Operations** |
| Quero saber o que o app fez ontem | Painel → **Jobs** |
| Quero ativar o início automático | Painel → **Settings** |
| Algo deu errado, preciso de ajuda | Painel → **Diagnostics** |
| Quero que o Claude use meu histórico | MCP → `kb_get_context` (automático) |
| "Claude, o que eu sei sobre X?" | MCP → `kb_query` |
| "Claude, compila meus logs" | MCP → `kb_compile` |
| "Claude, verifica a wiki" | MCP → `kb_lint` |
| "Claude, anota essa decisão" | MCP → `kb_add_memory` |
| "Claude, quais artigos eu tenho?" | MCP → `kb_list_articles` |
| "Claude, lê o artigo sobre Y" | MCP → `kb_read_article` |

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `KB_AGENT_BACKEND` | `claude` | Backend LLM: `claude` ou `codex` |
| `KB_CODEX_MODEL` | `gpt-5.3-codex` | Modelo usado pelo Codex |
| `KB_COMPILE_TIMEOUT_SECONDS` | `3600` | Timeout do agente na compilação (1h) |
| `KB_QUERY_TIMEOUT_SECONDS` | `1800` | Timeout do agente na query (30min) |
| `KB_LINT_TIMEOUT_SECONDS` | `900` | Timeout do agente no lint (15min) |
| `KB_FLUSH_TIMEOUT_SECONDS` | `300` | Timeout do agente no flush (5min) |
| `CLAUDE_INVOKED_BY` | — | Guard anti-recursão (hooks ignoram se setado) |
| `KB_INVOKED_BY` | — | Guard anti-recursão para o Codex |

---

## Estrutura de Arquivos

```
llm-knowledge-base/
├── AGENTS.md              # Schema da KB (instrução para o compilador)
├── CONTEXT.md             # Vocabulário e limites do projeto
├── pyproject.toml         # Dependências Python
│
├── kb_app/                # Pacote Python principal
│   ├── __main__.py        # CLI unificada
│   ├── core/              # Operações, paths, wiki helpers, transcripts
│   ├── hooks/             # Implementação dos hooks de AI client
│   ├── profiles/          # Store SQLite de perfis
│   ├── jobs/              # Fila de jobs durável e runner
│   ├── agent/             # Agente de background + agendador
│   ├── ui/                # Interface PySide6 + bandeja do sistema
│   └── diagnostics/       # Exportação e redação de diagnósticos
│
├── kb_mcp/                # Servidor MCP
│   ├── __init__.py
│   └── server.py
│
├── hooks/                 # Scripts de hook para os AI clients
│   ├── session-start.py
│   ├── session-end.py
│   └── pre-compact.py
│
├── scripts/               # Scripts standalone (wrappers sobre kb_app)
│   ├── compile.py
│   ├── query.py
│   ├── lint.py
│   ├── flush.py           # Chamado em background pelos hooks
│   ├── compile-daily.sh   # Wrapper para automação macOS/Linux
│   ├── compile-daily.ps1  # Wrapper para automação Windows
│   └── register-windows-task.ps1
│
├── packaging/
│   ├── pyinstaller/       # Spec do PyInstaller
│   └── inno/              # Script do Inno Setup (Windows)
│
├── .claude/               # Templates de hook para Claude Code
└── .codex/                # Templates de hook para Codex
│
└── kb/                    # Sua base de conhecimento (gitignored em produção)
    ├── daily/             # Logs diários (YYYY-MM-DD.md)
    └── knowledge/
        ├── index.md       # Tabela de artigos
        ├── log.md         # Log de compilações
        ├── concepts/      # Artigos de conceitos
        ├── connections/   # Artigos de conexões entre conceitos
        └── qa/            # Artigos de Q&A
```

---

## Empacotamento

### Windows

```powershell
# Build completo (exe + instalador)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build-windows.ps1

# Só o executável (sem instalador)
uv run pyinstaller packaging\pyinstaller\llm-knowledge-base.spec --noconfirm --clean

# Smoke test
uv run python scripts\smoke-packaged.py --exe dist\LLMKnowledgeBase\LLMKnowledgeBase.exe
```

O instalador é user-level (`%LOCALAPPDATA%\Programs\LLM Knowledge Base`) e não requer administrador. Ele não modifica os hooks do Claude/Codex durante a instalação — a configuração de hooks pertence ao wizard/fluxo de configuração do app.

### Linux

```bash
# Build
sh scripts/build-linux.sh

# Instalação interativa (pergunta KB root e configura MCP)
sh packaging/linux/install.sh dist/LLMKnowledgeBase

# Instalação silenciosa (CI / scripts de provisionamento)
sh packaging/linux/install.sh dist/LLMKnowledgeBase \
  --kb-root "$HOME/minha-kb" \
  --silent

# Sem integração MCP
sh packaging/linux/install.sh dist/LLMKnowledgeBase --no-mcp

# Desinstalar
sh ~/Applications/llm-knowledge-base/uninstall.sh
```

O instalador escreve apenas em diretórios de usuário (`~/Applications`, `~/.local/bin`, `~/.local/share/applications`, `~/.config/autostart`) e não requer `sudo`.

Após a instalação, reconfigurar o MCP:
```bash
llm-knowledge-base setup-mcp --kb-root ~/minha-kb
llm-knowledge-base setup-mcp --status   # verificar
llm-knowledge-base setup-mcp --remove   # remover
```

---

## Fluxo de Trabalho Diário

1. Inicie uma sessão Claude Code ou Codex.
2. `session-start.py` injeta o índice atual da KB e o log diário recente.
3. Trabalhe normalmente.
4. O hook de fim captura o transcript e inicia `flush.py` em background.
5. `flush.py` escreve memória estruturada em `kb/daily/YYYY-MM-DD.md`.
6. A automação diária executa `compile.py`, criando ou atualizando artigos em `kb/knowledge/`.

---

## Custos

Os custos dependem do backend selecionado e do tamanho do wiki.

| Operação | Custo típico |
|---|---|
| Flush | Pequena requisição de resumo |
| Compile | Requisição maior de extração/edição |
| Query | Depende do tamanho do wiki |
| Lint estrutural | Gratuito (sem LLM) |

O backend Claude registra o custo reportado pelo SDK em `scripts/state.json`. O backend Codex não expõe custo por este wrapper — o arquivo de estado registra `0.0` para essas execuções.

---

## Arquitetura

Leia [`AGENTS.md`](AGENTS.md) para o schema do daily-log, formato dos artigos, convenções de wikilink, detalhes dos hooks e comportamento do compilador.

Leia [`CONTEXT.md`](CONTEXT.md) para o vocabulário do projeto e decisões de limites.

Os ADRs em [`docs/adr/`](docs/adr/) documentam cada decisão de arquitetura relevante.

---

## Licença

MIT.
