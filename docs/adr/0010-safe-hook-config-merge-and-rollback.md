# Safe hook config merge and rollback

The desktop app will not overwrite Claude Code or Codex configuration files blindly. Hook installation and repair will read existing config, create timestamped backups, apply structured merges when possible, validate JSON/TOML after writing, show a diff or summary in the UI, and provide rollback so user AI-client configuration is not destroyed by setup automation.
