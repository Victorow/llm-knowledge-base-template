# Persistent job queue for long-running actions

The desktop UI will not run `flush`, `compile`, `query`, `lint`, hook setup, or automation setup as blocking UI calls. It will create persistent Job Queue entries in local SQLite, and the Background Agent will execute them while recording Job History with status, timing, backend, logs, and results; this keeps the Tray App responsive and makes failures auditable after the window is closed.
