set dotenv-load
set export

SGLANG_PORT := env_var_or_default("SGLANG_PORT", "8768")
SGLANG_BUILD_TAG := env_var_or_default("SGLANG_BUILD_TAG", "decisor-sglang:0.5.20")
SGLANG_MODEL_PATH := env_var_or_default("SGLANG_MODEL_PATH", "")
SGLANG_MODEL_REPO := env_var_or_default("SGLANG_MODEL_REPO", "")
SGLANG_MODEL_ARG := if SGLANG_MODEL_PATH != "" { "/model" } else { SGLANG_MODEL_REPO }
SGLANG_HF_CACHE := justfile_directory() / ".cache/huggingface"

# List commands.
default:
    @just --list

[private]
require-env:
    @[ -f .env ] || { echo ".env not found — cp .env.example .env and edit it"; exit 1; }

# Decide on a request file.
decide file:
    python3 sdks/python/decide.py {{ file }}

# Interactive demo: one decision through the SDK.
demo:
    python3 sdks/python/demo.py

# Build the SGLang image.
sglang-build:
    cd docker/sglang/image && sha256sum -c SHA256SUMS.txt
    docker build -t {{ SGLANG_BUILD_TAG }} -f docker/sglang/image/Containerfile docker/sglang/image
    docker/sglang/image/verify-image.sh {{ SGLANG_BUILD_TAG }}

# Stop SGLang.
sglang-down: require-env
    docker compose --env-file .env -f docker/sglang/compose.yaml down

# Follow SGLang logs.
sglang-logs: require-env
    docker compose --env-file .env -f docker/sglang/compose.yaml logs -f sglang

# Pull the published image.
sglang-pull: require-env
    docker compose --env-file .env -f docker/sglang/compose.yaml pull sglang

# Smoke-check the running engine.
sglang-smoke: require-env
    python3 scripts/sglang-smoke.py

# Check SGLang status and health.
sglang-status: require-env
    @docker compose --env-file .env -f docker/sglang/compose.yaml ps
    @curl -f -s -m 5 "http://127.0.0.1:{{ SGLANG_PORT }}/health" && echo "health: ok" || { echo "health: failed — engine not responding on 127.0.0.1:{{ SGLANG_PORT }}/health"; exit 1; }

# Start SGLang.
sglang-up: require-env
    bash scripts/sglang-up.sh
