#!/usr/bin/env sh
set -eu

APP_DIR="${HOME}/Applications/llm-knowledge-base"
DESKTOP_FILE="${HOME}/.local/share/applications/llm-knowledge-base.desktop"
BIN_FILE="${HOME}/.local/bin/llm-knowledge-base"

rm -rf "${APP_DIR}"
rm -f "${DESKTOP_FILE}" "${BIN_FILE}"

echo "Removed LLM Knowledge Base app files. KB data was not deleted."
