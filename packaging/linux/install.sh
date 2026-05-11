#!/usr/bin/env sh
# LLM Knowledge Base — Linux installer
# Installs to user directories only; no sudo required.
#
# Usage:
#   sh install.sh [BUILD_DIR] [options]
#
#   BUILD_DIR        Path to PyInstaller output (default: dist/LLMKnowledgeBase)
#
# Options:
#   --kb-root DIR    Where to store your KB files
#                    (default: ~/Documents/LLM Knowledge Base, or $KB_ROOT env var)
#   --no-mcp         Skip Claude Code MCP integration
#   --no-autostart   Skip adding the app to system startup
#   --silent         Non-interactive: use defaults, do not prompt
#
# Environment variables:
#   KB_ROOT          Override the default KB root path

set -eu

# ---------------------------------------------------------------------------
# Resolve script directory so we can find packaging/ relative to project root
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
APP_DIR="${HOME}/Applications/llm-knowledge-base"
DESKTOP_DIR="${HOME}/.local/share/applications"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${HOME}/.config/autostart"
SOURCE_DIR="${1:-${PROJECT_ROOT}/dist/LLMKnowledgeBase}"

DEFAULT_KB_ROOT="${HOME}/Documents/LLM Knowledge Base"
KB_ROOT="${KB_ROOT:-${DEFAULT_KB_ROOT}}"

SKIP_MCP=0
SKIP_AUTOSTART=0
SILENT=0

# ---------------------------------------------------------------------------
# Parse arguments (skip first positional arg which is SOURCE_DIR)
# ---------------------------------------------------------------------------
shift_done=0
for arg in "$@"; do
    if [ "${shift_done}" = "0" ] && [ -d "${arg}" ]; then
        shift_done=1
        continue
    fi
    case "${arg}" in
        --kb-root=*) KB_ROOT="${arg#--kb-root=}" ;;
        --kb-root)   : ;;  # handled below — requires next arg
        --no-mcp)    SKIP_MCP=1 ;;
        --no-autostart) SKIP_AUTOSTART=1 ;;
        --silent)    SILENT=1 ;;
    esac
done

# Handle "--kb-root <value>" (two separate args)
prev=""
for arg in "$@"; do
    if [ "${prev}" = "--kb-root" ]; then
        KB_ROOT="${arg}"
    fi
    prev="${arg}"
done

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo "  LLM Knowledge Base — Installer"
echo "  ================================"
echo ""

# ---------------------------------------------------------------------------
# Validate build output
# ---------------------------------------------------------------------------
EXE="${SOURCE_DIR}/LLMKnowledgeBase"
if [ ! -f "${EXE}" ]; then
    echo "ERROR: Executable not found: ${EXE}"
    echo ""
    echo "Build it first:"
    echo "  sh scripts/build-linux.sh"
    exit 1
fi

# ---------------------------------------------------------------------------
# Ask for KB root (interactive mode only)
# ---------------------------------------------------------------------------
if [ "${SILENT}" = "0" ]; then
    echo "Where do you want to store your knowledge base files?"
    echo "(This is where your daily logs and wiki articles will be saved.)"
    echo ""
    printf "  Folder [%s]: " "${KB_ROOT}"
    # Read user input only if stdin is a terminal
    if [ -t 0 ]; then
        read -r user_input || true
        if [ -n "${user_input}" ]; then
            KB_ROOT="${user_input}"
        fi
    else
        echo ""
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Ask about MCP (interactive mode only)
# ---------------------------------------------------------------------------
if [ "${SILENT}" = "0" ] && [ "${SKIP_MCP}" = "0" ]; then
    echo "Connect to Claude Code automatically? (recommended)"
    echo "(The app will add itself to Claude Code so it can read your knowledge base.)"
    echo ""
    printf "  Configure MCP integration? [Y/n]: "
    if [ -t 0 ]; then
        read -r mcp_input || true
        case "${mcp_input}" in
            [nN]*) SKIP_MCP=1 ;;
        esac
    else
        echo ""
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Summary before installing
# ---------------------------------------------------------------------------
echo "  Installing to : ${APP_DIR}"
echo "  KB folder     : ${KB_ROOT}"
echo "  Claude MCP    : $([ "${SKIP_MCP}" = "0" ] && echo "yes (auto-configure)" || echo "no")"
echo "  Autostart     : $([ "${SKIP_AUTOSTART}" = "0" ] && echo "yes" || echo "no")"
echo ""

if [ "${SILENT}" = "0" ] && [ -t 0 ]; then
    printf "  Proceed? [Y/n]: "
    read -r confirm || true
    case "${confirm}" in
        [nN]*) echo "Cancelled."; exit 0 ;;
    esac
    echo ""
fi

# ---------------------------------------------------------------------------
# Create directories
# ---------------------------------------------------------------------------
mkdir -p "${APP_DIR}" "${DESKTOP_DIR}" "${BIN_DIR}"

# ---------------------------------------------------------------------------
# Copy app files
# ---------------------------------------------------------------------------
echo "  Copying app files..."
cp -R "${SOURCE_DIR}/." "${APP_DIR}/"
chmod +x "${APP_DIR}/LLMKnowledgeBase"

# ---------------------------------------------------------------------------
# Create KB directory structure
# ---------------------------------------------------------------------------
echo "  Creating KB folder structure..."
mkdir -p \
    "${KB_ROOT}/kb/daily" \
    "${KB_ROOT}/kb/knowledge/concepts" \
    "${KB_ROOT}/kb/knowledge/connections" \
    "${KB_ROOT}/kb/knowledge/qa"

# ---------------------------------------------------------------------------
# Write .desktop entry (application menu / file manager integration)
# ---------------------------------------------------------------------------
echo "  Registering application menu entry..."
sed "s|__APP_DIR__|${APP_DIR}|g" \
    "${SCRIPT_DIR}/llm-knowledge-base.desktop.template" \
    > "${DESKTOP_DIR}/llm-knowledge-base.desktop"
chmod +x "${DESKTOP_DIR}/llm-knowledge-base.desktop"
# Notify desktop environment if xdg-desktop-menu is available
command -v xdg-desktop-menu >/dev/null 2>&1 \
    && xdg-desktop-menu forceupdate 2>/dev/null || true

# ---------------------------------------------------------------------------
# Create CLI wrapper in ~/.local/bin
# ---------------------------------------------------------------------------
echo "  Creating CLI shortcut in ${BIN_DIR}..."
cat > "${BIN_DIR}/llm-knowledge-base" <<EOF
#!/usr/bin/env sh
exec "${APP_DIR}/LLMKnowledgeBase" "\$@"
EOF
chmod +x "${BIN_DIR}/llm-knowledge-base"

# ---------------------------------------------------------------------------
# Autostart entry (~/.config/autostart)
# ---------------------------------------------------------------------------
if [ "${SKIP_AUTOSTART}" = "0" ]; then
    echo "  Adding to system startup..."
    mkdir -p "${AUTOSTART_DIR}"
    cat > "${AUTOSTART_DIR}/llm-knowledge-base.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=LLM Knowledge Base
Exec=${APP_DIR}/LLMKnowledgeBase ui
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
fi

# ---------------------------------------------------------------------------
# Configure MCP in Claude Code
# ---------------------------------------------------------------------------
if [ "${SKIP_MCP}" = "0" ]; then
    echo "  Configuring Claude Code MCP integration..."
    "${APP_DIR}/LLMKnowledgeBase" \
        setup-mcp \
        --exe-path "${APP_DIR}/LLMKnowledgeBase" \
        --kb-root "${KB_ROOT}" \
        2>/dev/null && echo "  MCP configured." \
        || echo "  Warning: could not configure MCP automatically. Run 'llm-knowledge-base setup-mcp --kb-root \"${KB_ROOT}\"' manually after installation."
fi

# ---------------------------------------------------------------------------
# Save install config so uninstall.sh knows the KB root
# ---------------------------------------------------------------------------
cat > "${APP_DIR}/.install-config" <<EOF
KB_ROOT=${KB_ROOT}
SKIP_MCP=${SKIP_MCP}
SKIP_AUTOSTART=${SKIP_AUTOSTART}
EOF

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "  ✓ LLM Knowledge Base installed successfully!"
echo ""
echo "  App      : ${APP_DIR}/LLMKnowledgeBase"
echo "  KB folder: ${KB_ROOT}"
echo ""

if [ "${SKIP_MCP}" = "0" ]; then
    echo "  → Restart Claude Code to activate the MCP integration."
    echo ""
fi

if echo ":${PATH}:" | grep -q ":${BIN_DIR}:"; then
    echo "  Run from terminal: llm-knowledge-base ui"
else
    echo "  Note: add ${BIN_DIR} to your PATH to use the 'llm-knowledge-base' command."
    echo "  Add this to your ~/.bashrc or ~/.zshrc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo ""
