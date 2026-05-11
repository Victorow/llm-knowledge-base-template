#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "${ROOT}"

uv run pyinstaller packaging/pyinstaller/llm-knowledge-base.spec --noconfirm
uv run python scripts/smoke-packaged.py --exe dist/LLMKnowledgeBase/LLMKnowledgeBase

echo "Build output: dist/LLMKnowledgeBase"
