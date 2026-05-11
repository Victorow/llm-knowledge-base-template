# Single packaged executable with subcommands

The desktop product will ship as one packaged executable with subcommands for UI, background agent, hooks, job execution, and diagnostics. This keeps PyInstaller and Inno Setup packaging simpler, gives hooks a stable entrypoint, and lets all execution modes share the same core modules and App Data paths.
