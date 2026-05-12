# LLM Knowledge Base

Uma base de conhecimento pessoal que aprende sozinha enquanto você usa o Claude Code ou Codex.

> **Novo usuário?** Siga o [Guia de Início Rápido](#guia-de-início-rápido) — leva menos de 5 minutos.

---

## O que é isso?

Imagine um caderno de anotações que se escreve sozinho. Toda vez que você trabalha com o Claude Code, o app registra automaticamente o que foi feito e aprendido naquela sessão. Com o tempo, ele monta uma **wiki pessoal** com tudo que você já descobriu — e coloca esse conhecimento de volta no contexto do Claude automaticamente na próxima sessão.

**Na prática:**
- Você trabalha normalmente com o Claude Code
- O app captura e organiza tudo em segundo plano
- Na próxima sessão, o Claude já sabe o que você aprendeu antes
- Você pode perguntar para sua base de conhecimento: *"Como eu fiz X no mês passado?"*
- Quando o Claude compacta o contexto, a conversa é salva automaticamente (opcional)

---

## Guia de Início Rápido

### Windows

**Passo 1 — Instale o app**

Baixe o instalador na [página de releases](../../releases) e execute `LLMKnowledgeBaseSetup.exe`.

Durante a instalação:
1. **"Onde instalar o programa?"** — deixe o padrão
2. **"Onde salvar sua base de conhecimento?"** — escolha uma pasta (ex: `Documentos\LLM Knowledge Base`)
3. **"Conectar ao Claude Code automaticamente?"** — deixe marcado ✓

**Passo 2 — Crie seu perfil**

Na primeira abertura, um assistente aparece pedindo nome e pasta da base de conhecimento. Preencha e clique em **Criar Perfil e Continuar**.

**Passo 3 — Instale os hooks**

No painel, vá em **Hooks**, selecione **Claude Code** e clique em **Install Hooks**.

**Passo 4 — Reinicie o Claude Code**

Feche e abra o Claude Code novamente. Pronto — o app captura tudo em segundo plano.

---

### Linux

**Passo 1 — Baixe e instale**

Baixe a pasta `LLMKnowledgeBase` da [página de releases](../../releases), extraia e rode:

```bash
sh packaging/linux/install.sh ~/Downloads/LLMKnowledgeBase
```

O instalador pergunta onde salvar a KB e se deve conectar ao Claude Code via MCP.

**Passo 2 — Instale os hooks no painel**

```bash
llm-knowledge-base ui
```

Vá em **Hooks → Install Hooks**.

**Passo 3 — Reinicie o Claude Code**

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
- [Painel de Controle Desktop](#painel-de-controle-desktop)
- [Comandos CLI](#comandos-cli)
- [Configuração de Hooks](#configuração-de-hooks)
- [Automação Diária](#automação-diária)
- [Múltiplos Perfis](#múltiplos-perfis)
- [Integração MCP](#integração-mcp)
- [Ferramentas MCP](#ferramentas-mcp)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Estrutura de Arquivos](#estrutura-de-arquivos)
- [Empacotamento](#empacotamento)
- [Uso do Backend LLM](#uso-do-backend-llm)

---

## Como Funciona

```
Sua sessão Claude Code / Codex
        │
        ▼
  hook session-end
  (captura transcript)
        │
        ├─── App instalado (sys.frozen) ──────────────────────┐
        │    Escreve direto em kb/daily/YYYY-MM-DD.md         │
        │                                                      │
        └─── Desenvolvimento (uv disponível) ─────────────────┤
             Spawna scripts/flush.py                          │
             (resume via LLM → daily log)                     │
                                                              ▼
                                                 kb/daily/YYYY-MM-DD.md
                                                 (memória bruta do dia)
                                                              │
                                                              ▼
                                                 Compile Changed (manual ou agendado)
                                                 (LLM extrai artigos)
                                                              │
                                                              ▼
                                                 kb/knowledge/
                                                 ├── index.md
                                                 ├── concepts/
                                                 ├── connections/
                                                 └── qa/
```

Na próxima sessão, `hook session-start` injeta o índice do wiki e o log recente diretamente no contexto do Claude — sem precisar pesquisar manualmente.

**Quando o Claude compacta o contexto** (PostCompact), o app opcionalmente enfileira uma compilação automática (configurável em Settings).

---

## Clientes Suportados

| Superfície | Status | Hooks registrados |
|---|---|---|
| Claude Code CLI | ✅ Suportado | `SessionStart`, `SessionEnd`, `PreCompact`, `PostCompact` |
| Claude Desktop | ✅ MCP configurado | — (MCP sem hooks diretos) |
| Codex | ✅ Suportado | `SessionStart`, `Stop` |
| Painel Desktop (Windows/Linux) | ✅ Suportado | UI PySide6, bandeja do sistema, fila de jobs |

---

## Pré-requisitos

- **Python 3.12+** e [`uv`](https://docs.astral.sh/uv/getting-started/installation/) *(apenas para instalação a partir do código-fonte)*
- Claude Code instalado e autenticado **ou** Codex instalado

---

## Instalação

### Opção 1 — Instalador Windows (recomendado)

Baixe `LLMKnowledgeBaseSetup.exe` na [página de releases](../../releases) e execute. Não requer administrador.

Instala em `%LOCALAPPDATA%\Programs\LLM Knowledge Base` e cria atalhos no menu Iniciar.

### Opção 2 — A partir do código-fonte (para desenvolvedores)

```bash
git clone https://github.com/Victorow/llm-knowledge-base-template.git
cd llm-knowledge-base-template
uv sync
uv run python -m kb_app ui
```

---

## Painel de Controle Desktop

O painel é o "cockpit" do app — você não precisa dele no dia a dia, mas está disponível para instalar hooks, compilar, consultar e monitorar tudo.

O app fica na **bandeja do sistema** (ícone roxo com grafo neural). Fechar a janela não encerra o app — ele continua rodando em segundo plano. Para reabrir, clique no ícone na bandeja. Para encerrar completamente, clique com o botão direito → **Fechar Aplicação**.

### Páginas do Painel

| Página | O que faz |
|---|---|
| **Tutorial** | Guia passo a passo de configuração inicial com status ao vivo (perfil, hooks, MCP) |
| **Dashboard** | Resumo de status: perfil ativo, backend, último job executado |
| **Setup** | Smoke test do backend, flush de teste |
| **Profiles** | Criar, renomear e alternar entre múltiplas bases de conhecimento |
| **Hooks** | Instalar / reparar / remover hooks no Claude Code e no Codex |
| **Daily Logs** | Navegar logs diários capturados; adicionar memória manual |
| **Knowledge** | Navegar artigos da wiki (`concepts/`, `connections/`, `qa/`) |
| **Operations** | Compilar, fazer query, lint — manualmente |
| **Jobs** | Histórico de jobs em background com status e erros |
| **Settings** | Compilação diária agendada, compilar após compactação, autostart |
| **Diagnostics** | Exportar bundle ZIP com dados do sistema (segredos redatados) |

### Bandeja do sistema

- **Clique simples** → abre o painel
- **Botão direito** → menu com "Abrir Painel" e "Fechar Aplicação"
- **Botão X da janela** → oculta para a bandeja (app continua rodando)

---

## Comandos CLI

Disponíveis via `uv run python -m kb_app` (código-fonte) ou `LLMKnowledgeBase.exe` (instalado).

### Parâmetros globais

```
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
llm-knowledge-base --kb-root /minha/kb compile

# Forçar recompilação de tudo
llm-knowledge-base --kb-root /minha/kb compile --all

# Compilar um log específico
llm-knowledge-base --kb-root /minha/kb compile --file 2026-05-10.md

# Visualizar o que seria compilado sem executar
llm-knowledge-base --kb-root /minha/kb compile --dry-run
```

---

### `query` — Consultar a base de conhecimento

```bash
# Consulta simples (resposta no terminal)
llm-knowledge-base --kb-root /minha/kb query "Como eu estruturo autenticação JWT?"

# Gravar a resposta como artigo Q&A em kb/knowledge/qa/
llm-knowledge-base --kb-root /minha/kb query "Qual padrão de retry eu uso?" --file-back
```

---

### `lint` — Verificar saúde da base de conhecimento

```bash
# Lint completo (estrutural + verificação LLM de contradições)
llm-knowledge-base --kb-root /minha/kb lint

# Apenas checks estruturais (gratuito, sem LLM)
llm-knowledge-base --kb-root /minha/kb lint --structural-only
```

| Check | Severidade | Descrição |
|---|---|---|
| `broken_link` | Erro | Wikilinks apontando para artigos inexistentes |
| `orphan_page` | Aviso | Artigos sem nenhum inbound link |
| `orphan_source` | Aviso | Daily logs não compilados |
| `stale_article` | Aviso | Logs modificados após a última compilação |
| `missing_backlink` | Sugestão | Links unidirecionais |
| `contradiction` | Aviso | Contradições entre artigos (verificação LLM) |

---

### `hook` — Executar evento de hook

Chamado automaticamente pelos clientes AI via hooks configurados.

```bash
# Retorna JSON de contexto para injetar na sessão
llm-knowledge-base --kb-root /minha/kb hook session-start

# Processar fim de sessão (lê JSON do stdin)
llm-knowledge-base --kb-root /minha/kb hook session-end

# Hook de pré-compactação (salva contexto antes de compactar)
llm-knowledge-base --kb-root /minha/kb hook pre-compact

# Hook pós-compactação (enfileira compilação se habilitado)
llm-knowledge-base --kb-root /minha/kb hook post-compact
```

---

### `setup-mcp` — Configurar integração MCP

```bash
# Configurar para Claude Code (Desktop + CLI)
llm-knowledge-base --kb-root /minha/kb setup-mcp --client claude

# Configurar para Codex
llm-knowledge-base --kb-root /minha/kb setup-mcp --client codex

# Configurar para ambos (padrão)
llm-knowledge-base --kb-root /minha/kb setup-mcp

# Verificar status
llm-knowledge-base --kb-root /minha/kb setup-mcp --status

# Remover
llm-knowledge-base --kb-root /minha/kb setup-mcp --remove
```

---

### `profiles` — Gerenciar múltiplas KBs

```bash
llm-knowledge-base profiles list
llm-knowledge-base profiles create "Trabalho" /caminho/kb-trabalho
llm-knowledge-base profiles activate 2
```

---

### `jobs` — Gerenciar fila de jobs

```bash
llm-knowledge-base jobs enqueue compile_changed --profile-id 1
llm-knowledge-base jobs enqueue query --profile-id 1 \
  --payload-json '{"question": "O que sei sobre Docker?"}'
```

**Tipos de job disponíveis:**

| job_type | Payload | Descrição |
|---|---|---|
| `compile_changed` | — | Compila logs com mudanças |
| `compile_all` | — | Recompila todos os logs |
| `compile_file` | `{"file": "nome.md"}` | Compila arquivo específico |
| `query` | `{"question": "..."}` | Consulta sem gravar |
| `query_file_back` | `{"question": "..."}` | Consulta e grava como artigo Q&A |
| `lint_structural` | — | Lint sem LLM |
| `lint_full` | — | Lint com verificação de contradições |
| `manual_memory` | `{"content": "..."}` | Adiciona memória manual ao log do dia |
| `install_hooks` | `{"client": "claude"}` | Instala hooks no config do cliente AI |
| `repair_hooks` | `{"client": "claude"}` | Repara hooks existentes |
| `remove_hooks` | `{"client": "claude"}` | Remove hooks do config |
| `install_autostart` | — | Cria launcher no Startup do Windows |
| `remove_autostart` | — | Remove o launcher de autostart |
| `diagnostics_export` | `{"output_dir": "..."}` | Exporta diagnósticos |
| `configure_daily_schedule` | `{"enabled": true, "time": "17:00"}` | Configura agendamento |
| `backend_smoke_test` | — | Testa conectividade do backend |

---

## Configuração de Hooks

### Via painel (recomendado)

1. Abra o painel → **Hooks**
2. Selecione o cliente (**Claude Code** ou **Codex**)
3. Clique em **Install Hooks**

Os hooks são instalados com backup automático do arquivo original.

### Via CLI

```bash
# Instalar hooks para Claude Code
llm-knowledge-base --kb-root /minha/kb jobs enqueue install_hooks \
  --profile-id 1 --payload-json '{"client": "claude"}'
```

### Hooks instalados por cliente

**Claude Code** (`~/.claude/settings.json`):

| Hook | Quando dispara | O que faz |
|---|---|---|
| `SessionStart` | Início de cada sessão | Injeta índice da wiki + log recente no contexto |
| `SessionEnd` | Fim de cada sessão | Captura transcript e salva no log diário |
| `PreCompact` | Antes de compactar contexto | Salva contexto antes da compactação |
| `PostCompact` | Após compactar contexto | Enfileira compilação (se "Compilar após compactação" estiver ativo) |

**Codex** (`~/.codex/hooks.json`):

| Hook | Quando dispara | O que faz |
|---|---|---|
| `SessionStart` | Início/retomada de sessão | Injeta contexto da KB |
| `Stop` | Fim de sessão | Captura transcript e salva no log diário |

---

## Automação Diária

### Via painel

Em **Settings**:
- Marque **"Compilar diariamente"** e defina o horário (ex: `17:00`)
- Marque **"Compilar após compactação de contexto"** para compilar sempre que o Claude Code compactar uma conversa
- Clique em **Salvar Configurações**

### Autostart (Windows)

Em **Settings** → **Install Autostart**: cria um launcher em `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` para o app iniciar junto com o Windows.

### Automação manual (Windows — Task Scheduler)

```powershell
# Testar sem agendar
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\compile-daily.ps1 -DryRun

# Registrar tarefa diária às 17:00
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\register-windows-task.ps1 -At 17:00
```

### Automação manual (Linux — Systemd)

```bash
# compile-daily.sh chama o binário instalado automaticamente
systemctl --user enable --now kb-compile.timer
```

---

## Múltiplos Perfis

Cada perfil tem seu próprio diretório de KB, backend e configurações. Útil para separar contextos de trabalho e pessoal.

```bash
# Criar dois perfis
llm-knowledge-base profiles create "Trabalho" /projetos/kb-trabalho
llm-knowledge-base profiles create "Pessoal" /home/user/kb-pessoal

# Ver lista (o * indica o ativo)
llm-knowledge-base profiles list

# Ativar
llm-knowledge-base profiles activate 2
```

O perfil ativo é usado pela UI e pelo agendador. A flag `--kb-root` ignora o perfil ativo e aponta para qualquer KB.

---

## Integração MCP

O MCP (Model Context Protocol) permite que o Claude acesse sua KB diretamente durante uma conversa — sem precisar pedir explicitamente.

### Via instalador (zero configuração)

Se você usou o `LLMKnowledgeBaseSetup.exe` com a opção MCP marcada, a integração já está ativa. Basta **reiniciar o Claude Code**.

O instalador configura **dois arquivos** automaticamente:
- `%APPDATA%\Claude\claude_desktop_config.json` → Claude Desktop
- `%USERPROFILE%\.claude.json` → Claude Code CLI

### Configuração manual

```powershell
# Windows
& "$env:LOCALAPPDATA\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" `
  --kb-root "C:\Sua\KB" setup-mcp --client claude
```

```bash
# Linux
llm-knowledge-base --kb-root "$HOME/Documents/LLM Knowledge Base" setup-mcp
```

### Verificar

```powershell
# Windows
& "$env:LOCALAPPDATA\Programs\LLM Knowledge Base\LLMKnowledgeBase.exe" setup-mcp --status
```

```bash
# Linux
llm-knowledge-base setup-mcp --status
```

**Saída esperada:**
```
Claude Desktop config : C:\Users\...\claude_desktop_config.json
  MCP configured: yes
Claude Code CLI config: C:\Users\...\.claude.json
  MCP configured: yes
Codex config          : C:\Users\...\.codex\config.toml
  MCP configured: yes
```

---

## Ferramentas MCP

Com o MCP ativo, o Claude pode usar as seguintes ferramentas durante uma conversa:

### Ferramentas de consulta e contexto

| Ferramenta | Para que serve |
|---|---|
| `kb_get_context` | Injeta o índice da wiki + log do dia no contexto da sessão |
| `kb_query` | Responde perguntas usando os artigos da KB; `file_back=true` salva a resposta como artigo Q&A |
| `kb_list_articles` | Lista todos os artigos organizados por categoria |
| `kb_read_article` | Lê o conteúdo completo de um artigo específico |
| `kb_wiki_index` | Retorna a tabela de índice completa (nome, resumo, fontes, data) |

### Ferramentas de manutenção

| Ferramenta | Para que serve |
|---|---|
| `kb_compile` | Enfileira compilação de logs como job de background; `dry_run` lista arquivos sem rodar LLM |
| `kb_lint` | Verifica saúde da wiki: links quebrados, órfãos, contradições |
| `kb_add_memory` | Adiciona uma anotação manual ao log do dia atual |
| `kb_pending_logs` | Lista logs diários ainda não compilados |

### Ferramentas de diagnóstico

| Ferramenta | Para que serve |
|---|---|
| `kb_status` | Mostra root, contagem de logs, artigos compilados, pendentes, custo total e data da última compilação |
| `kb_diagnostics` | Exporta bundle ZIP de diagnósticos (segredos redatados) |

### Exemplos de uso pelo Claude

```
"Claude, compila meus logs"
→ kb_compile()

"O que eu sei sobre Docker networks?"
→ kb_query("O que sei sobre Docker networks?")

"Quais logs ainda não foram compilados?"
→ kb_pending_logs()

"Como está minha KB?"
→ kb_status()

"Anota aí: decidi usar Redis para cache"
→ kb_add_memory("Decisão: usar Redis para cache de sessões...")
```

---

## Guia de referência rápida

| Situação | O que usar |
|---|---|
| Primeira instalação | Painel → **Tutorial** |
| Verificar se tudo funciona | Painel → **Tutorial** → Atualizar Status |
| Captura parou de funcionar | Painel → **Hooks** → Install Hooks |
| Ver logs do dia | Painel → **Daily Logs** |
| Ler artigos da wiki | Painel → **Knowledge** |
| Compilar agora | Painel → **Operations** → Compile Changed |
| Ver erros do app | Painel → **Jobs** |
| Ativar compilar após compactação | Painel → **Settings** → marcar PostCompact → Salvar |
| Algo deu errado | Painel → **Diagnostics** → Export Support Bundle |
| Usar via Claude Code | MCP ativo → ferramentas `kb_*` disponíveis automaticamente |

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `KB_AGENT_BACKEND` | `claude` | Backend LLM: `claude` ou `codex` |
| `KB_CODEX_MODEL` | `gpt-5.3-codex` | Modelo usado pelo Codex |
| `KB_COMPILE_TIMEOUT_SECONDS` | `3600` | Timeout na compilação (1h) |
| `KB_QUERY_TIMEOUT_SECONDS` | `1800` | Timeout na query (30min) |
| `KB_LINT_TIMEOUT_SECONDS` | `900` | Timeout no lint (15min) |
| `KB_FLUSH_TIMEOUT_SECONDS` | `300` | Timeout no flush (5min) |
| `CLAUDE_INVOKED_BY` | — | Guard anti-recursão (hooks ignoram se setado) |
| `KB_INVOKED_BY` | — | Guard anti-recursão para o Codex |

---

## Estrutura de Arquivos

```
llm-knowledge-base/
├── AGENTS.md              # Schema da KB (instrução para o compilador LLM)
├── CONTEXT.md             # Vocabulário e limites do projeto
├── pyproject.toml
│
├── kb_app/                # Pacote Python principal
│   ├── __main__.py        # CLI unificada (hook, compile, query, lint, ui, mcp, setup-mcp...)
│   ├── core/              # Operações LLM, paths, wiki helpers, transcrições, mcp_setup
│   ├── hooks/             # Lógica dos hooks (captura, session-start, flush direto)
│   ├── profiles/          # Store SQLite de perfis e configurações
│   ├── jobs/              # Fila de jobs durável (SQLite) + runner (thread de background)
│   ├── agent/             # Agente de background e agendador diário
│   ├── diagnostics/       # Exportação com redação de segredos
│   └── ui/
│       ├── app.py         # Painel PySide6 (não-bloqueante, jobs em background thread)
│       ├── tray.py        # Bandeja do sistema com ícone personalizado
│       └── resources/     # Ícone embutido em base64 (icon_data.py)
│
├── kb_mcp/
│   └── server.py          # Servidor MCP com 10 ferramentas (FastMCP, async)
│
├── scripts/
│   ├── flush.py           # Flush via LLM (modo desenvolvimento, requer uv)
│   ├── compile.py / query.py / lint.py  # Wrappers standalone
│   └── compile-daily.{sh,ps1}           # Scripts de automação
│
├── packaging/
│   ├── icon/              # Ícone da aplicação (generate_icon.py, icon.png, icon.ico)
│   ├── pyinstaller/       # Spec do PyInstaller (inclui ícone)
│   ├── inno/              # Script Inno Setup — Windows installer user-level
│   └── linux/             # install.sh / uninstall.sh
│
└── kb/                    # Sua base de conhecimento (gitignored)
    ├── daily/             # Logs diários (YYYY-MM-DD.md)
    └── knowledge/
        ├── index.md
        ├── log.md
        ├── concepts/
        ├── connections/
        └── qa/
```

---

## Empacotamento

### Windows

```powershell
# Só o executável
uv run pyinstaller packaging\pyinstaller\llm-knowledge-base.spec --noconfirm

# Instalador completo
& "C:\...\Inno Setup 6\ISCC.exe" packaging\inno\llm-knowledge-base.iss
```

O instalador é user-level (`%LOCALAPPDATA%\Programs\LLM Knowledge Base`), não requer administrador e configura MCP automaticamente se o usuário marcar a opção.

### Linux

```bash
sh packaging/linux/install.sh dist/LLMKnowledgeBase

# Instalação silenciosa (CI)
sh packaging/linux/install.sh dist/LLMKnowledgeBase \
  --kb-root "$HOME/minha-kb" --silent

# Sem MCP
sh packaging/linux/install.sh dist/LLMKnowledgeBase --no-mcp
```

Instala apenas em diretórios de usuário — sem `sudo`.

---

## Uso do Backend LLM

| Operação | Uso típico do backend LLM |
|---|---|
| Session flush (app instalado) | Gratuito — escrita direta, sem LLM |
| Session flush (desenvolvimento) | Pequena requisição de resumo |
| Compile Changed | Requisição de extração por log modificado |
| Query | Depende do tamanho da wiki |
| Lint estrutural | Gratuito (sem LLM) |
| Lint completo | Requisição de verificação de contradições |

A métrica exibida como custo é uma estimativa de uso reportada pelo backend LLM
(por exemplo, Claude Agent SDK), não uma cobrança feita por este aplicativo.
Ela serve para dar visibilidade de consumo/cota do provedor. O app não processa
pagamentos e não cobra nada diretamente.

Essa estimativa acumulada fica disponível via `kb_status` no MCP ou no arquivo
de estado da KB como uso reportado pelo backend LLM.

---

## Arquitetura

Leia [`AGENTS.md`](AGENTS.md) para o schema do daily-log, formato dos artigos, convenções de wikilink e comportamento do compilador.

Leia [`CONTEXT.md`](CONTEXT.md) para o vocabulário do projeto e decisões de limites.

---

## Licença

MIT.
