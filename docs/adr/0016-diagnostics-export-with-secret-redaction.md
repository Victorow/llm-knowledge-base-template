# Diagnostics export with secret redaction

The desktop app will include diagnostics and a support bundle export in V1. The bundle will include app/platform metadata, configured paths, backend status, job history, logs, lint reports, and redacted hook/config state, while excluding credentials, API keys, full transcripts, and other sensitive content by default.
