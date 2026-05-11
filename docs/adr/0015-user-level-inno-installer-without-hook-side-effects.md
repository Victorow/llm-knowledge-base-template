# User-level Inno installer without hook side effects

The Windows installer will be a user-level Inno Setup installer that installs the desktop app under a per-user program location, creates Start Menu entries, and optionally launches the app after install. It will not require admin rights and will not modify Claude Code, Codex, hooks, scheduled tasks, or user AI-client configuration during installation; those changes are handled later by the First-Run Setup Wizard with backup, validation, and rollback.
