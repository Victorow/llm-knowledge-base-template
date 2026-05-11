# Separate KB data from app data

The installed desktop app will keep KB Data separate from App Data. User knowledge content lives in a selected KB Data directory, while UI config, SQLite job history, logs, cache, and diagnostics live in per-user App Data locations such as `%APPDATA%\LLM Knowledge Base\` on Windows and XDG config/state paths on Linux; the packaged executable directory is treated as read-only.
