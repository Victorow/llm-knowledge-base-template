# Detect external AI clients instead of bundling

The desktop app will not bundle Claude Code or Codex. It will package the KB application, detect existing AI client installations and credentials, validate them with smoke tests, and guide users to install or authenticate missing clients; this avoids taking ownership of external client licensing, updates, authentication, and security lifecycle.
