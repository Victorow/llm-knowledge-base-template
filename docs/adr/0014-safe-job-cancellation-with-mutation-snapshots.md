# Safe job cancellation with mutation snapshots

The desktop app will support job cancellation, but mutable jobs will not be treated like read-only commands. Jobs that can write KB Data or AI-client configuration will record intended targets and create backups or snapshots when practical before execution, then mark cancellation/failure clearly and offer restore or repair flows if a process is killed after partial mutation.
