#!/usr/bin/env bash
# ABOUTME: Launch script for the BRO use case.
# ABOUTME: Starts Chainlit on port 1337 via the BRO custom UI entry point.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."
exec uv run chainlit run src/bro_chat/usecase_ui.py --host 0.0.0.0 --port 1337
