#!/usr/bin/env bash
# Start the engine: local checkpoint (SGLANG_MODEL_PATH) or Hugging Face repo (SGLANG_MODEL_REPO).
set -euo pipefail

if [ -z "${SGLANG_API_KEY:-}" ]; then
    echo "error: SGLANG_API_KEY is empty — generate one with: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'" >&2
    exit 1
fi

if [ -n "$SGLANG_MODEL_PATH" ]; then
    dir="$(cd -- "$SGLANG_MODEL_PATH" && pwd -P)" || {
        echo "error: local model directory not found: $SGLANG_MODEL_PATH" >&2
        exit 1
    }
    export SGLANG_MODEL_MOUNT="$dir"
    docker compose --env-file .env -f docker/sglang/compose.yaml -f docker/sglang/compose.model.yaml up -d
else
    [ -n "$SGLANG_MODEL_REPO" ] || { echo "error: set SGLANG_MODEL_PATH or SGLANG_MODEL_REPO in .env" >&2; exit 1; }
    docker compose --env-file .env -f docker/sglang/compose.yaml up -d
fi
