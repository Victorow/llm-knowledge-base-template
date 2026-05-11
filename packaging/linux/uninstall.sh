#!/usr/bin/env sh
# LLM Knowledge Base — Linux uninstaller
# Removes app files; never deletes your KB data.

set -eu

APP_DIR="${HOME}/Applications/llm-knowledge-base"
DESKTOP_FILE="${HOME}/.local/share/applications/llm-knowledge-base.desktop"
AUTOSTART_FILE="${HOME}/.config/autostart/llm-knowledge-base.desktop"
BIN_FILE="${HOME}/.local/bin/llm-knowledge-base"

echo ""
echo "  LLM Knowledge Base — Uninstaller"
echo "  =================================="
echo ""
echo "  This will remove the app, but NOT your KB data folder."
echo ""

# Remove MCP entries before deleting the exe
EXE="${APP_DIR}/LLMKnowledgeBase"
if [ -f "${EXE}" ]; then
    echo "  Removing MCP integrations..."
    "${EXE}" setup-mcp --remove --client both 2>/dev/null \
        && echo "  MCP entries removed." \
        || echo "  Warning: could not remove MCP entries automatically."
fi

echo "  Removing app files..."
rm -rf "${APP_DIR}"
rm -f "${DESKTOP_FILE}" "${AUTOSTART_FILE}" "${BIN_FILE}"

# Refresh desktop menu
command -v xdg-desktop-menu >/dev/null 2>&1 \
    && xdg-desktop-menu forceupdate 2>/dev/null || true

echo ""
echo "  ✓ LLM Knowledge Base removed."
echo "  Your KB data was not deleted."
echo ""
