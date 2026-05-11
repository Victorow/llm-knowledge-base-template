# User-session tray app over system service

The desktop control panel will run as a per-user Tray App with a Background Agent instead of a privileged Windows Service or Linux system daemon. This keeps access to `~/.codex`, `~/.claude`, user credentials, tray UI, autostart, logs, and per-user configuration straightforward; a true system service can be revisited only if the product later needs to operate before login or across multiple users on the same machine.
