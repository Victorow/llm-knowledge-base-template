# Provider-neutral capture and agent backends

The project originally coupled transcript parsing and LLM execution to Claude Code conventions. We now normalize Claude Code and Codex JSONL transcripts before flushing, and select the LLM execution engine with `KB_AGENT_BACKEND=claude|codex`, because the knowledge pipeline should not care which AI client produced the session or which local agent runtime performs the summarization and compilation.
