#!/bin/bash

set -euo pipefail

UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-.venv} uv run --project . python hubspot-publish.py publish productivity --continue-by-scheduled
