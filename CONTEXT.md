# Personal Knowledge Base

This context describes a client-neutral memory pipeline for AI coding sessions. It turns supported conversation transcripts into daily logs, then compiles those logs into a queryable markdown wiki.

## Language

**AI Client**:
The local coding assistant surface that owns a conversation lifecycle, such as Claude Code or Codex.
_Avoid_: provider, IDE, assistant

**Conversation Transcript**:
A JSONL session artifact emitted by an **AI Client** and used as immutable source material for memory extraction.
_Avoid_: chat log, raw dump

**Capture Hook**:
A lifecycle command that extracts recent **Conversation Transcript** turns without making LLM calls.
_Avoid_: ingestion job, compiler hook

**Flush**:
The background summarization step that turns captured conversation context into a **Daily Log** entry.
_Avoid_: compile, sync

**Daily Log**:
An append-only markdown source file containing structured memory from one calendar day.
_Avoid_: journal, article

**Compile**:
The LLM-owned transformation from **Daily Log** files into structured **Knowledge Articles**.
_Avoid_: flush, query

**Knowledge Article**:
A compiled markdown wiki page under `kb/knowledge/`.
_Avoid_: note, memory blob

**Manual Memory**:
A user-authored memory entry appended to a **Daily Log** so it can be incorporated through **Compile** instead of direct article editing.
_Avoid_: direct article edit, wiki edit

**Job Queue**:
A persistent local queue of long-running pipeline actions created by the **Control Panel UI** and executed by the **Background Agent**.
_Avoid_: direct blocking command, fire-and-forget script

**Job History**:
The persisted execution record for a **Job Queue** item, including status, timestamps, command metadata, logs, backend, and result.
_Avoid_: transient console output

**First-Run Setup Wizard**:
The guided onboarding flow in the **Control Panel UI** that validates prerequisites and configures hooks, backend, autostart, and scheduled compile.
_Avoid_: README-only setup, manual install checklist

**KB Data**:
The user-selected knowledge base content directory containing daily logs, compiled knowledge, schemas, and knowledge documentation.
_Avoid_: app config, packaged resources

**KB Profile**:
A named application record pointing to one **KB Data** directory and its per-KB settings, status, hooks, and schedules.
_Avoid_: clone, workspace

**Active KB Profile**:
The single **KB Profile** currently targeted by **Capture Hooks**, default jobs, dashboard status, and background automation.
_Avoid_: selected tab, recent folder

**App Data**:
The per-user application state directory containing UI config, SQLite state, job history, logs, cache, and diagnostics.
_Avoid_: knowledge base, install directory

**Agent Backend**:
The LLM execution engine used by **Flush**, **Compile**, and query operations.
_Avoid_: AI client, hook runtime

**KB Desktop App**:
A local cross-platform application that exposes the knowledge pipeline through a UI and runs companion background tasks.
_Avoid_: replacement client, standalone AI client

**Control Panel UI**:
The user-facing interface for configuring, triggering, monitoring, and inspecting the knowledge pipeline.
_Avoid_: main pipeline, hook UI

**Background Agent**:
The long-lived local process owned by the **KB Desktop App** that runs scheduled jobs, watches status, and coordinates commands without replacing **Capture Hooks**.
_Avoid_: capture hook, compiler, AI client

**Tray App**:
The user-session desktop process that exposes the **Control Panel UI**, system tray controls, and lifecycle management for the **Background Agent**.
_Avoid_: system service, daemon

## Relationships

- An **AI Client** emits one or more **Conversation Transcripts**.
- A **Capture Hook** reads exactly one **Conversation Transcript** and starts one **Flush**.
- A **Flush** appends to one **Daily Log**.
- A **Compile** reads one or more **Daily Logs** and creates or updates many **Knowledge Articles**.
- A **Manual Memory** is written to a **Daily Log** and becomes a **Knowledge Article** only after **Compile**.
- An **Agent Backend** may be different from the **AI Client** that produced the transcript.
- The **KB Desktop App** owns the **Control Panel UI** and may start a **Background Agent**.
- The **Background Agent** can trigger **Flush**, **Compile**, query, lint, and automation commands, but **Capture Hooks** remain the source of AI-client lifecycle capture.
- The **Tray App** runs inside the logged-in user's desktop session and is responsible for starting/stopping the **Background Agent** for that user.
- The **Control Panel UI** creates **Job Queue** entries for long-running operations.
- The **Background Agent** executes **Job Queue** entries and records **Job History**.
- The **First-Run Setup Wizard** configures the **KB Desktop App** for the current user before normal operation.
- **KB Data** and **App Data** are separate directories.
- The installed **KB Desktop App** writes to **App Data** and user-selected **KB Data**, never to its packaged executable directory.
- The **Control Panel UI** can manage multiple **KB Profiles**.
- Exactly one **Active KB Profile** is used for **Capture Hooks** and automatic capture at a time.

## Example Dialogue

> **Dev:** "Can Codex use this KB if the original hook was written for Claude Code?"
> **Domain expert:** "Yes, as long as the **Capture Hook** normalizes Codex's **Conversation Transcript** and the selected **Agent Backend** can run **Flush** and **Compile**."

> **Dev:** "Should the desktop app replace hooks?"
> **Domain expert:** "No. The **KB Desktop App** is a **Control Panel UI** over the existing pipeline; **Capture Hooks** still integrate with the AI clients."

> **Dev:** "Should this run as a system service?"
> **Domain expert:** "No. Use a **Tray App** in the user's session so it can access user credentials, tray UI, and per-user AI client configuration cleanly."

> **Dev:** "Can the control panel edit compiled articles directly?"
> **Domain expert:** "Not in the first version. Add a **Manual Memory** to a **Daily Log**, then run **Compile** so the LLM preserves sources, wikilinks, and index consistency."

> **Dev:** "Should compile block the UI while it runs?"
> **Domain expert:** "No. Create a **Job Queue** entry and let the **Background Agent** execute it while the **Control Panel UI** shows live status and **Job History**."

> **Dev:** "Should setup still happen by copying JSON from the README?"
> **Domain expert:** "No. The **First-Run Setup Wizard** should validate prerequisites and configure hooks, backend, autostart, and daily compile from the UI."

> **Dev:** "Can we store runtime state beside the packaged executable?"
> **Domain expert:** "No. Store UI config, job history, and logs in **App Data**; store daily logs and articles in **KB Data**."

> **Dev:** "Can hooks capture into several KBs at once?"
> **Domain expert:** "Not in V1. Users can manage multiple **KB Profiles**, but **Capture Hooks** target one **Active KB Profile**."

## Flagged Ambiguities

- "Codex support" can mean transcript capture from the Codex client, LLM execution through Codex CLI, or both. Resolved: support includes both surfaces through **AI Client** parsing and selectable **Agent Backend** execution.
- "Hook" was previously overloaded between Claude Code hooks and compilation behavior. Resolved: use **Capture Hook** only for client lifecycle commands and **Compile** for daily-log-to-wiki synthesis.
- "Application running in the background" can mean replacing hooks or supervising the existing pipeline. Resolved: the **KB Desktop App** is a control panel with a **Background Agent**; it does not replace **Capture Hooks**.
- "Background process" can mean a user-session **Tray App** or a privileged system service. Resolved: use a **Tray App** plus per-user **Background Agent**, not a system service.
- "Editing the KB" can mean direct **Knowledge Article** edits or adding source material. Resolved: first-version UI supports **Manual Memory** entries in **Daily Logs**, not direct article editing.
- "Run command from UI" can mean blocking the UI process or scheduling a durable job. Resolved: long-running operations use the **Job Queue** and persist **Job History**.
- "Setup through UI" means the **First-Run Setup Wizard** owns install/validation of runtime configuration, not a README-only checklist.
- "Project folder" can mean install directory, **KB Data**, or **App Data**. Resolved: these are separate locations with different ownership and permissions.
- "Cloud sync" does not exist in the current project and is out of scope for the first **KB Desktop App** version. Users may place **KB Data** in an external synced folder, but the app does not manage cloud login, merge conflicts, encryption, or remote storage.
- "Multiple KBs" means multiple **KB Profiles** in the app, not simultaneous multi-destination capture. Resolved: one **Active KB Profile** at a time for hooks and automation.
