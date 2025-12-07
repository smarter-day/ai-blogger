#!/bin/bash

set -euo pipefail

UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-.venv} uv run --project . python posts.py productivity --post-types=blog --languages=en