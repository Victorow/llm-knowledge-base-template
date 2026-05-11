# Hooks call packaged app entrypoint

Installed Claude Code and Codex hooks will call the packaged application entrypoint with subcommands such as `hook session-start` and `hook session-end`, not Python scripts inside a repository clone. The entrypoint reads App Data, resolves the Active KB Profile, and runs capture logic against that KB so hooks remain stable across app updates, KB moves, and removal of `uv` as a runtime dependency.
