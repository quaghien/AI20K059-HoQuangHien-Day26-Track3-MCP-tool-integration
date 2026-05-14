#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONDA_DEFAULT_ENV:-}" != "aitclab" ]]; then
  echo "Please run 'conda activate aitclab' before starting MCP Inspector." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="$(command -v python)"
SERVER_PATH="${SCRIPT_DIR}/mcp_server.py"

mkdir -p "${REPO_ROOT}/.npm-cache"
NPM_CONFIG_CACHE="${REPO_ROOT}/.npm-cache" npx -y @modelcontextprotocol/inspector \
  "${PYTHON_BIN}" "${SERVER_PATH}" --db-path "${SCRIPT_DIR}/lab.db"
