#!/bin/bash

set -euo pipefail

command -v uv >/dev/null 2>&1 || { echo "uv could not be found"; exit 1; }

if [ ! -d ".venv" ]; then
    echo "Creating project environment at .venv"
    UV_PROJECT_ENVIRONMENT=.venv uv venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

UV_PROJECT_ENVIRONMENT=.venv uv sync
