# AGENTS.md - Personal Knowledge Base Schema

> Adapted from [Andrej Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture.
> Instead of ingesting external articles, this system compiles knowledge from your own AI conversations.

## The Compiler Analogy

```
kb/daily/       = source code    (your conversations - the raw material)
LLM             = compiler       (extracts and organizes knowledge)
kb/knowledge/   = executable     (structured, queryable knowledge base)
lint            = test suite     (health checks for consistency)
queries         = runtime        (using the knowledge)
```

You don't manually organize your knowledge. You have conversations, and the LLM handles the synthesis, cross-referencing, and maintenance.

---

## Architecture

### Layer 1: `kb/daily/` - Conversation Logs (Immutable Source)

Daily logs capture what happened in your AI coding sessions. These are the "raw sources" - append-only, never edited after the fact.

```
kb/daily/
├── 2026-04-01.md
├── 2026-04-02.md
├── ...
```

Each file follows this format:

```markdown
# Daily Log: YYYY-MM-DD

## Sessions

### Session (HH:MM) - Brief Title

**Context:** What the user was working on.

**Key Exchanges:**
- User asked about X, assistant explained Y
- Decided to use Z approach because...
- Discovered that W doesn't work when...

**Decisions Made:**
- Chose library X over Y because...
- Architecture: went with pattern Z

**Lessons Learned:**
- Always do X before Y to avoid...
- The gotcha with Z is that...

**Action Items:**
- [ ] Follow up on X
- [ ] Refactor Y when time permits
```

### Layer 2: `kb/knowledge/` - Compiled Knowledge (LLM-Owned)

The LLM owns this directory entirely. Humans read it but rarely edit it directly.

```
kb/knowledge/
├── index.md              # Master catalog - every article with one-line summary
├── log.md                # Append-only chronological build log
├── concepts/             # Atomic knowledge articles
├── connections/          # Cross-cutting insights linking 2+ concepts
└── qa/                   # Filed query answers (compounding knowledge)
```

### Layer 3: This File (AGENTS.md)

The schema that tells the LLM how to compile and maintain the knowledge base. This is the "compiler specification."

---

## Structural Files

### `kb/knowledge/index.md` - Master Catalog

A table listing every knowledge article. This is the primary retrieval mechanism - the LLM reads this FIRST when answering any query, then selects relevant articles to read in full.

Format:

```markdown
# Knowledge Base Index

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[concepts/supabase-auth]] | Row-level security patterns and JWT gotchas | daily/2026-04-02.md | 2026-04-02 |
| [[connections/auth-and-webhooks]] | Token verification patterns shared across Supabase auth and Stripe webhooks | daily/2026-04-02.md, daily/2026-04-04.md | 2026-04-04 |
```

### `kb/knowledge/log.md` - Build Log

Append-only chronological record of every compile, query, and lint operation.

Format:

```markdown
# Build Log

## [2026-04-01T14:30:00] compile | Daily Log 2026-04-01
- Source: daily/2026-04-01.md
- Articles created: [[concepts/nextjs-project-structure]], [[concepts/tailwind-setup]]
- Articles updated: (none)

## [2026-04-02T09:00:00] query | "How do I handle auth redirects?"
- Consulted: [[concepts/supabase-auth]], [[concepts/nextjs-middleware]]
- Filed to: [[qa/auth-redirect-handling]]
```

---

## Article Formats

### Concept Articles (`kb/knowledge/concepts/`)

One article per atomic piece of knowledge. These are facts, patterns, decisions, preferences, and lessons extracted from your conversations.

```markdown
---
title: "Concept Name"
aliases: [alternate-name, abbreviation]
tags: [domain, topic]
sources:
  - "daily/2026-04-01.md"
  - "daily/2026-04-03.md"
created: 2026-04-01
updated: 2026-04-03
---

# Concept Name

[2-4 sentence core explanation]

## Key Points

- [Bullet points, each self-contained]

## Details

[Deeper explanation, encyclopedia-style paragraphs]

## Related Concepts

- [[concepts/related-concept]] - How it connects

## Sources

- [[daily/2026-04-01.md]] - Initial discovery during project setup
- [[daily/2026-04-03.md]] - Updated after debugging session
```

### Connection Articles (`kb/knowledge/connections/`)

Cross-cutting synthesis linking 2+ concepts. Created when a conversation reveals a non-obvious relationship.

```markdown
---
title: "Connection: X and Y"
connects:
  - "concepts/concept-x"
  - "concepts/concept-y"
sources:
  - "daily/2026-04-04.md"
created: 2026-04-04
updated: 2026-04-04
---

# Connection: X and Y

## The Connection

[What links these concepts]

## Key Insight

[The non-obvious relationship discovered]

## Evidence

[Specific examples from conversations]

## Related Concepts

- [[concepts/concept-x]]
- [[concepts/concept-y]]
```

### Q&A Articles (`kb/knowledge/qa/`)

Filed answers from queries. Every complex question answered by the system can be permanently stored, making future queries smarter.

```markdown
---
title: "Q: Original Question"
question: "The exact question asked"
consulted:
  - "concepts/article-1"
  - "concepts/article-2"
filed: 2026-04-05
---

# Q: Original Question

## Answer

[The synthesized answer with [[wikilinks]] to sources]

## Sources Consulted

- [[concepts/article-1]] - Relevant because...
- [[concepts/article-2]] - Provided context on...

## Follow-Up Questions

- What about edge case X?
- How does this change if Y?
```

---

## Core Operations

### 1. Compile (`kb/daily/` -> `kb/knowledge/`)

When processing a daily log:

1. Read the daily log file
2. Read `kb/knowledge/index.md` to understand current knowledge state
3. Read existing articles that may need updating
4. For each piece of knowledge found in the log:
   - If an existing concept article covers this topic: UPDATE it with new information, add the daily log as a source
   - If it's a new topic: CREATE a new `concepts/` article
5. If the log reveals a non-obvious connection between 2+ existing concepts: CREATE a `connections/` article
6. UPDATE `kb/knowledge/index.md` with new/modified entries
7. APPEND to `kb/knowledge/log.md`

**Important guidelines:**
- A single daily log may touch 3-10 knowledge articles
- Prefer updating existing articles over creating near-duplicates
- Use Obsidian-style `[[wikilinks]]` with full relative paths from knowledge/
- Write in encyclopedia style - factual, concise, self-contained
- Every article must have YAML frontmatter
- Every article must link back to its source daily logs

### 2. Query (Ask the Knowledge Base)

1. Read `kb/knowledge/index.md` (the master catalog)
2. Based on the question, identify 3-10 relevant articles from the index
3. Read those articles in full
4. Synthesize an answer with `[[wikilink]]` citations
5. If `--file-back` is specified: create a `kb/knowledge/qa/` article and update index.md and log.md

**Why this works without RAG:** At personal knowledge base scale (50-500 articles), the LLM reading a structured index outperforms cosine similarity. The LLM understands what the question is really asking and selects pages accordingly. Embeddings find similar words; the LLM finds relevant concepts.

### 3. Lint (Health Checks)

Seven checks, run periodically:

1. **Broken links** - `[[wikilinks]]` pointing to non-existent articles
2. **Orphan pages** - Articles with zero inbound links from other articles
3. **Orphan sources** - Daily logs that haven't been compiled yet
4. **Stale articles** - Source daily log changed since article was last compiled
5. **Contradictions** - Conflicting claims across articles (requires LLM judgment)
6. **Missing backlinks** - A links to B but B doesn't link back to A
7. **Sparse articles** - Below 200 words, likely incomplete

Output: a markdown report with severity levels (error, warning, suggestion).

---

## Conventions

- **Wikilinks:** Use Obsidian-style `[[path/to/article]]` without `.md` extension
- **Writing style:** Encyclopedia-style, factual, third-person where appropriate
- **Dates:** ISO 8601 (YYYY-MM-DD for dates, full ISO for timestamps in log.md)
- **File naming:** lowercase, hyphens for spaces (e.g., `supabase-row-level-security.md`)
- **Frontmatter:** Every article must have YAML frontmatter with at minimum: title, sources, created, updated
- **Sources:** Always link back to the daily log(s) that contributed to an article

---

## Full Project Structure

```
llm-personal-kb/
|-- .claude/
|   |-- settings.example.json        # Claude Code hook template for macOS/Linux
|   |-- settings.windows.example.json # Claude Code hook template for Windows
|-- .codex/
|   |-- config.example.toml          # Codex hook feature flag template
|   |-- hooks.example.json           # Codex hook template for macOS/Linux
|   |-- hooks.windows.example.json   # Codex hook template for Windows
|-- .gitignore                       # Excludes runtime state, temp files, caches
|-- AGENTS.md                        # This file - schema + full technical reference
|-- CONTEXT.md                       # Project vocabulary and boundaries
|-- README.md                        # Concise overview + quick start
|-- pyproject.toml                   # Dependencies (at root so hooks can find it)
|-- kb/
|   |-- daily/                       #   "Source code" - conversation logs (immutable)
|   |-- knowledge/                   #   "Executable" - compiled knowledge (LLM-owned)
|       |-- index.md                 #     Master catalog - THE retrieval mechanism
|       |-- log.md                   #     Append-only build log
|       |-- concepts/                #     Atomic knowledge articles
|       |-- connections/             #     Cross-cutting insights linking 2+ concepts
|       |-- qa/                      #     Filed query answers (compounding knowledge)
|-- scripts/                         # CLI tools
|   |-- agent_backend.py             #   Claude/Codex LLM execution abstraction
|   |-- transcripts.py               #   Claude Code/Codex transcript normalization
|   |-- compile.py                   #   Compile daily logs -> knowledge articles
|   |-- query.py                     #   Ask questions (index-guided, no RAG)
|   |-- lint.py                      #   7 health checks
|   |-- flush.py                     #   Extract memories from conversations (background)
|   |-- compile-daily.sh             #   macOS/Linux scheduled compile wrapper
|   |-- compile-daily.ps1            #   Windows scheduled compile wrapper
|   |-- register-windows-task.ps1    #   Windows Task Scheduler helper
|   |-- config.py                    #   Path constants
|   |-- utils.py                     #   Shared helpers
|-- hooks/                           # Claude Code and Codex capture hooks
|   |-- session-start.py             #   Injects knowledge into every session
|   |-- session-end.py               #   Extracts conversation -> daily log
|   |-- pre-compact.py               #   Safety net: captures context before compaction
|-- docs/adr/                        # Architecture decision records
|-- reports/                         # Lint reports (gitignored)
```

---

## Hook System (Automatic Capture)

Hooks are configured per AI client:

- Claude Code: merge `.claude/settings.example.json` or `.claude/settings.windows.example.json` into `~/.claude/settings.json`.
- Codex: enable `features.codex_hooks = true` and copy `.codex/hooks.example.json` or `.codex/hooks.windows.example.json` to `.codex/hooks.json` or `~/.codex/hooks.json`.

Codex project-local hooks load only when the project `.codex/` layer is trusted.

### `.claude/settings.json` Format

```json
{
  "hooks": {
    "SessionStart": [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run python hooks/session-start.py", "timeout": 15 }] }],
    "PreCompact": [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run python hooks/pre-compact.py", "timeout": 10 }] }],
    "SessionEnd": [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run python hooks/session-end.py", "timeout": 10 }] }]
  }
}
```

Claude Code commands can use absolute paths or `uv run --directory`. Empty `matcher` catches all events.

### `.codex/hooks.json` Format

```json
{
  "hooks": {
    "SessionStart": [{ "matcher": "startup|resume", "hooks": [{ "type": "command", "command": "uv run --directory /ABSOLUTE/PATH/TO/llm-knowledge-base python /ABSOLUTE/PATH/TO/llm-knowledge-base/hooks/session-start.py", "timeout": 15 }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "uv run --directory /ABSOLUTE/PATH/TO/llm-knowledge-base python /ABSOLUTE/PATH/TO/llm-knowledge-base/hooks/session-end.py", "timeout": 10 }] }]
  }
}
```

### Hook Details

**`session-start.py`** (SessionStart)
- Pure local I/O, no API calls, runs in under 1 second
- Reads `kb/knowledge/index.md` and the most recent daily log
- Outputs JSON to stdout: `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}`
- Claude Code and Codex see the knowledge base index at the start of every session
- Max context: 20,000 characters

**`session-end.py`** (Claude Code SessionEnd / Codex Stop)
- Reads hook input from stdin (JSON with `session_id`, `transcript_path`, `cwd`)
- Extracts recent user/assistant turns from Claude Code or Codex JSONL via `scripts/transcripts.py`
- Writes the extracted context to a temp file and spawns `flush.py`
- Recursion guard: exits immediately if `CLAUDE_INVOKED_BY` or `KB_INVOKED_BY` is set

**`pre-compact.py`** (PreCompact)
- Same architecture as session-end.py
- Fires before Claude Code auto-compacts the context window
- Guards against empty `transcript_path` (known Claude Code bug #13668)
- Critical for long sessions: captures context before summarization discards it

**Why both PreCompact and SessionEnd?** Long-running sessions may trigger multiple auto-compactions before you close the session. Without PreCompact, intermediate context is lost to summarization before SessionEnd ever fires.

### Background Flush Process (`flush.py`)

Spawned by capture hooks as a background process:
- **Windows:** `CREATE_NO_WINDOW` to avoid console flashes while preserving Agent SDK subprocess I/O
- **Mac/Linux:** `start_new_session=True`

This keeps hook execution fast and prevents long LLM calls from blocking the client lifecycle event.

**What flush.py does:**
1. Sets `CLAUDE_INVOKED_BY=memory_flush` and `KB_INVOKED_BY=memory_flush` env vars (prevents recursive hook firing)
2. Reads the pre-extracted conversation context from the temp `.md` file
3. Skips if context is empty or if same session was flushed within 60 seconds (deduplication)
4. Calls the selected agent backend (`KB_AGENT_BACKEND=claude|codex`)
5. The backend decides what's worth saving - returns structured bullet points or `FLUSH_OK`
6. Appends result to `kb/daily/YYYY-MM-DD.md`
7. Cleans up temp context file

### JSONL Transcript Format

Claude Code stores messages under a `message` key:

```python
entry = json.loads(line)
msg = entry.get("message", {})
role = msg.get("role", "")     # "user" or "assistant"
content = msg.get("content", "")  # string or list of content blocks
```

Content can be a string or a list of blocks (`{"type": "text", "text": "..."}` dicts).

Codex rollout transcripts store messages as `response_item` records:

```python
entry = json.loads(line)
payload = entry.get("payload", {})
role = payload.get("role", "")        # "user" or "assistant"
content = payload.get("content", "")  # blocks such as input_text/output_text
```

`scripts/transcripts.py` is the canonical parser. Do not duplicate transcript parsing inside hooks.

---

## Script Details

### compile.py - The Compiler

Uses `scripts/agent_backend.py` to run either Claude Agent SDK or Codex CLI:

```python
result = await run_agent_text(
    prompt=compile_prompt,
    cwd=ROOT_DIR,
    writable=True,
    claude_allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
    claude_max_turns=30,
)
```

- Builds a prompt with: AGENTS.md schema, current index, all existing articles, and the daily log
- The selected backend reads the daily log, decides what concepts to extract, and writes files directly
- Claude backend uses `permission_mode="acceptEdits"`; Codex backend uses `codex exec --sandbox workspace-write`
- Incremental: tracks SHA-256 hashes of daily logs in `state.json`, skips unchanged files
- Cost tracking is available for Claude backend; Codex CLI runs record `0.0` because the wrapper does not receive cost data

**CLI:**
```bash
uv run python scripts/compile.py              # compile new/changed only
uv run python scripts/compile.py --all        # force recompile everything
uv run python scripts/compile.py --file kb/daily/2026-04-01.md
uv run python scripts/compile.py --dry-run
```

### query.py - Index-Guided Retrieval

Loads the entire knowledge base into context (index + all articles). No RAG.

At personal KB scale (50-500 articles), the LLM reading a structured index outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words.

**CLI:**
```bash
uv run python scripts/query.py "What auth patterns do I use?"
uv run python scripts/query.py "What's my error handling strategy?" --file-back
```

With `--file-back`, creates a Q&A article in `kb/knowledge/qa/` and updates the index and log. This is the compounding loop - every question makes the KB smarter.

### lint.py - Health Checks

Seven checks:

| Check | Type | Catches |
|-------|------|---------|
| Broken links | Structural | `[[wikilinks]]` to non-existent articles |
| Orphan pages | Structural | Articles with zero inbound links |
| Orphan sources | Structural | Daily logs not yet compiled |
| Stale articles | Structural | Source logs changed since compilation |
| Missing backlinks | Structural | A links to B but B doesn't link back |
| Sparse articles | Structural | Under 200 words |
| Contradictions | LLM | Conflicting claims across articles |

**CLI:**
```bash
uv run python scripts/lint.py                    # all checks
uv run python scripts/lint.py --structural-only  # skip LLM check (free)
```

Reports saved to `reports/lint-YYYY-MM-DD.md`.

---

## State Tracking

`scripts/state.json` tracks:
- `ingested` - map of daily log filenames to SHA-256 hashes, compilation timestamps, and costs
- `query_count` - total queries run
- `last_lint` - timestamp of most recent lint
- `total_cost` - cumulative API cost

`scripts/last-flush.json` tracks flush deduplication (session_id + timestamp).

Both are gitignored and regenerated automatically.

---

## Dependencies

`pyproject.toml` (at project root):
- `claude-agent-sdk>=0.1.29` - Claude Agent SDK for LLM calls with tool use
- `python-dotenv>=1.0.0` - Environment variable management
- `tzdata>=2024.1` - Timezone data
- Python 3.12+, managed by [uv](https://docs.astral.sh/uv/)

For Claude backend, no separate API key is needed if Claude Code is authenticated because the Agent SDK uses Claude Code credentials.

For Codex backend, install and authenticate Codex CLI, then set:

```bash
export KB_AGENT_BACKEND=codex
```

PowerShell:

```powershell
$env:KB_AGENT_BACKEND = "codex"
```

Codex backend defaults to `KB_CODEX_MODEL=gpt-5.3-codex` to avoid inheriting an incompatible model from `~/.codex/config.toml` on older Codex CLI builds. Users can override `KB_CODEX_MODEL` when their installed Codex supports a newer model.

---

## Costs

| Operation | Cost behavior |
|-----------|---------------|
| Compile one daily log | Backend/model dependent |
| Query (no file-back) | Backend/model dependent |
| Query (with file-back) | Backend/model dependent |
| Full lint (with contradictions) | Backend/model dependent |
| Structural lint only | $0.00 |
| Memory flush (per session) | Small summary request |

Claude backend stores SDK-reported cost in `scripts/state.json`. Codex backend currently records `0.0` because `codex exec` does not expose cost through this wrapper.

---

## Customization

### Additional Article Types

Add directories like `people/`, `projects/`, `tools/` to `kb/knowledge/`. Define the article format in this file (AGENTS.md) and update `utils.py`'s `list_wiki_articles()` to include them.

### Obsidian Integration

The knowledge base is pure markdown with `[[wikilinks]]` - works natively in Obsidian. Point a vault at `kb/knowledge/` for graph view, backlinks, and search.

### Scaling Beyond Index-Guided Retrieval

At ~2,000+ articles / ~2M+ tokens, the index becomes too large for the context window. At that point, add hybrid RAG (keyword + semantic search) as a retrieval layer before the LLM. See Karpathy's recommendation of `qmd` by Tobi Lutke for search at scale.
