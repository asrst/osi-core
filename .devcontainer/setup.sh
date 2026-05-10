#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$WORKSPACE_ROOT"

# Install opencode globally via npm
npm install -g opencode-ai

# Verify opencode
opencode --version

# Install uv if needed
if ! command -v uv &> /dev/null; then
    pip install uv
fi

# Sync workspace (dev deps included by default in sync)
uv sync

# Install osi-core to system Python so osi-core CLI is globally available
# --system installs to system Python instead of workspace venv
# --break-system-packages allows installing into the system environment
uv pip install --system --break-system-packages -e packages/core
uv pip install --system --break-system-packages -e .

# Verify osi-core CLI works without uv run
osi-core validate packages/core/tests/fixtures/osi/sample.yaml

echo "Dev environment ready."