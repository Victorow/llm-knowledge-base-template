#!/usr/bin/env sh
set -eu

APP_DIR="${HOME}/Applications/llm-knowledge-base"
DESKTOP_DIR="${HOME}/.local/share/applications"
BIN_DIR="${HOME}/.local/bin"
SOURCE_DIR="${1:-dist/LLMKnowledgeBase}"

if [ ! -d "${SOURCE_DIR}" ]; then
  echo "Build output not found: ${SOURCE_DIR}" >&2
  exit 1
fi

mkdir -p "${APP_DIR}" "${DESKTOP_DIR}" "${BIN_DIR}"
cp -R "${SOURCE_DIR}/." "${APP_DIR}/"

cat "packaging/linux/llm-knowledge-base.desktop.template" \
  | sed "s|__APP_DIR__|${APP_DIR}|g" \
  > "${DESKTOP_DIR}/llm-knowledge-base.desktop"

cat > "${BIN_DIR}/llm-knowledge-base" <<EOF
#!/usr/bin/env sh
exec "${APP_DIR}/LLMKnowledgeBase" "\$@"
EOF
chmod +x "${BIN_DIR}/llm-knowledge-base"
chmod +x "${DESKTOP_DIR}/llm-knowledge-base.desktop"

echo "Installed to ${APP_DIR}"
