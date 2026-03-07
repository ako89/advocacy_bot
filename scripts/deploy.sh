#!/usr/bin/env bash
# Pull latest and rebuild. Run from the repo root.
set -euo pipefail

git pull
docker compose up -d --build
