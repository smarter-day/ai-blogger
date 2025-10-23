#!/bin/bash

# HubSpot Publishing Script
# Usage: ./publish-to-hubspot.sh [--dry-run] [--limit N]

.venv/bin/python hubspot-publish.py publish productivity "$@"

