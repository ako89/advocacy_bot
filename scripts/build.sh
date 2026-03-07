#!/usr/bin/env bash
# Build a multi-arch image locally and push to a registry.
# Usage: REGISTRY=ghcr.io/youruser ./scripts/build.sh
set -euo pipefail

REGISTRY="${REGISTRY:?Set REGISTRY to your image destination, e.g. ghcr.io/youruser/advocacy_bot}"
TAG="${TAG:-latest}"
IMAGE="$REGISTRY:$TAG"

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag "$IMAGE" \
  --push \
  .

echo "Pushed $IMAGE"
